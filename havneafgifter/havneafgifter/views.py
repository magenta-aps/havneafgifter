from csp_helpers.mixins import CSPViewMixin
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    BACKEND_SESSION_KEY,
    REDIRECT_FIELD_NAME,
    authenticate,
    login,
    logout,
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.core.exceptions import PermissionDenied
from django.forms import formset_factory
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, RedirectView
from django.views.generic.edit import CreateView, FormView, UpdateView
from django_tables2 import SingleTableView

from havneafgifter.forms import (
    AuthenticationForm,
    DisembarkmentForm,
    HarborDuesFormForm,
    PassengersByCountryForm,
    PassengersTotalForm,
)
from havneafgifter.models import (
    CruiseTaxForm,
    Disembarkment,
    DisembarkmentSite,
    HarborDuesForm,
    Nationality,
    PassengersByCountry,
    PermissionsMixin,
    ShipType,
)
from havneafgifter.tables import HarborDuesFormTable


class HavneafgiftView:
    def get_context_data(self, **context):
        return super().get_context_data(
            **{
                **context,
                "version": settings.VERSION,
            }
        )

    def get_redirect_for_form(
        self,
        viewname: str,
        form: HarborDuesForm | CruiseTaxForm,
    ):
        return HttpResponseRedirect(reverse(viewname, kwargs={"pk": form.pk}))


class RootView(RedirectView):
    def get_redirect_url(self):
        if not self.request.user.is_authenticated:
            user = authenticate(
                request=self.request, saml_data=self.request.session.get("saml")
            )
            if user and user.is_authenticated:
                login(
                    request=self.request,
                    user=user,
                    backend="project.auth_backend.Saml2Backend",
                )
            if not self.request.user.is_authenticated:
                return reverse("havneafgifter:login")
        if "Ship" in self.request.user.group_names:
            return reverse("havneafgifter:harbor_dues_form_create")
        # TODO: redirect to a list view?
        return reverse("havneafgifter:harbor_dues_form_create")


class LoginView(HavneafgiftView, DjangoLoginView):
    template_name = "havneafgifter/login.html"
    form_class = AuthenticationForm

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        if self.back:
            response.set_cookie(
                "back", self.back, secure=True, httponly=True, samesite="None"
            )
        return response

    def get_context_data(self, **context):
        return super().get_context_data(
            **{
                **context,
                "back": self.back,
            }
        )

    @property
    def back(self):
        return self.request.GET.get("back") or self.request.GET.get(REDIRECT_FIELD_NAME)


class LogoutView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        if (
            self.request.session.get(BACKEND_SESSION_KEY)
            == "project.auth_backend.Saml2Backend"
            or "saml" in self.request.session
        ):
            return reverse("mitid:logout")
        else:
            logout(self.request)
            return settings.LOGOUT_REDIRECT_URL


class PostLoginView(RedirectView):
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.delete_cookie("back")
        return response

    def get_redirect_url(self, *args, **kwargs):
        if not self.request.user.is_authenticated:
            user = authenticate(
                request=self.request, saml_data=self.request.session.get("saml")
            )
            if user and user.is_authenticated:
                login(
                    request=self.request,
                    user=user,
                    backend="project.auth_backend.Saml2Backend",
                )
        if not self.request.user.is_authenticated:
            return reverse("havneafgifter:login-failed")
        backpage = self.request.COOKIES.get("back")
        if backpage:
            return backpage
        return reverse("havneafgifter:root")


class _SendEmailMixin:
    def _send_email(
        self,
        form: HarborDuesForm | CruiseTaxForm,
        request,
    ) -> None:
        email_message, status = form.send_email()
        messages.add_message(
            request,
            messages.SUCCESS if status == 1 else messages.ERROR,
            (
                self._get_success_message(form)
                if status == 1
                else _("Error when sending email")
            ),
        )

    def _get_success_message(self, form: HarborDuesForm | CruiseTaxForm):
        return _(
            "Thank you for submitting this form. "
            "Your harbour dues form has now been received by the port authority "
            "and the Greenlandic Tax Authority."
        )


class _SaveHarborDuesFormMixin(HavneafgiftView):
    def form_valid(self, form):
        harbor_dues_form = form.save(commit=False)
        if harbor_dues_form.vessel_type == ShipType.CRUISE:
            cruise_tax_form = self._handle_cruise_tax_form(harbor_dues_form)
            if cruise_tax_form.has_port_of_call:
                # Send user to next step - filling out passenger tax info
                return self.get_redirect_for_form(
                    "havneafgifter:passenger_tax_create",
                    cruise_tax_form,
                )
            else:
                # Send user to final step - filling out environmental tax info
                return self.get_redirect_for_form(
                    "havneafgifter:environmental_tax_create",
                    cruise_tax_form,
                )
        else:
            # User is all done filling out data for this vessel
            harbor_dues_form.save()
            # Go to detail view to display result.
            return self.get_redirect_for_form(
                "havneafgifter:receipt_detail_html",
                harbor_dues_form,
            )


class HarborDuesFormCreateView(
    LoginRequiredMixin,
    CSPViewMixin,
    _SaveHarborDuesFormMixin,
    CreateView,
):
    model = HarborDuesForm
    form_class = HarborDuesFormForm

    def get_initial(self):
        initial = {}
        # Attempting to call group_names on a User that is not logged in
        # will blow up, because that'd be an AnonymousUser,
        # not our own implementation
        if "Ship" in self.request.user.group_names:
            initial["vessel_imo"] = self.request.user.username
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user_is_ship"] = "Ship" in self.request.user.group_names
        return kwargs

    def _handle_cruise_tax_form(
        self, harbor_dues_form: HarborDuesForm
    ) -> CruiseTaxForm:
        # `CruiseTaxForm` inherits from `HarborDuesForm`, so we can create
        # a `CruiseTaxForm` based on the fields on `HarborDuesForm`.
        cruise_tax_form = CruiseTaxForm.objects.create(
            **{
                k: v
                for k, v in harbor_dues_form.__dict__.items()
                if not k.startswith("_")  # skip `_state`, etc.
            }
        )
        return cruise_tax_form


class HarborDuesFormUpdateView(
    LoginRequiredMixin,
    CSPViewMixin,
    _SaveHarborDuesFormMixin,
    UpdateView,
):
    model = HarborDuesForm
    form_class = HarborDuesFormForm

    def _handle_cruise_tax_form(
        self, harbor_dues_form: HarborDuesForm
    ) -> CruiseTaxForm:
        # `CruiseTaxForm` inherits from `HarborDuesForm`, so we can update
        # a `CruiseTaxForm` based on the fields on `HarborDuesForm`.
        cruise_tax_form = CruiseTaxForm.objects.get(pk=harbor_dues_form.pk)
        for k, v in harbor_dues_form.__dict__.items():
            if not k.startswith("_"):  # skip `_state`, etc.
                setattr(cruise_tax_form, k, v)
        cruise_tax_form.save()
        return cruise_tax_form


class _CruiseTaxFormSetView(LoginRequiredMixin, HavneafgiftView, FormView):
    """Shared base class for views that create a set of model objects related
    to a `CruiseTaxForm`, e.g. `PassengersByCountry` or `Disembarkment`.
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self._cruise_tax_form = CruiseTaxForm.objects.get(pk=kwargs["pk"])

    def get_form(self, form_class=None):
        factory = formset_factory(
            self.form_class,
            can_order=False,
            can_delete=False,
            extra=0,
        )
        return factory(**self.get_form_kwargs())


class PassengerTaxCreateView(_CruiseTaxFormSetView):
    template_name = "havneafgifter/passenger_tax_create.html"
    form_class = PassengersByCountryForm

    def post(self, request, *args, **kwargs):
        sum_passengers_by_country = sum(
            pbc.number_of_passengers
            for pbc in self._get_passengers_by_country_objects()
        )
        passengers_total_form = PassengersTotalForm(data=request.POST)
        passengers_total_form.validate_total(sum_passengers_by_country)
        if not passengers_total_form.is_valid():
            return self.render_to_response(
                self.get_context_data(passengers_total_form=passengers_total_form)
            )
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs["initial"] = self._get_initial_formset_data()
        return form_kwargs

    def get_context_data(self, **kwargs):
        total_num = self._cruise_tax_form.number_of_passengers
        context_data = super().get_context_data(**kwargs)
        context_data["passengers_total_form"] = kwargs.get(
            "passengers_total_form",
            PassengersTotalForm(
                initial={"total_number_of_passengers": total_num},
            ),
        )
        context_data["passengers_by_country_formset"] = self.get_form()
        return context_data

    def form_valid(self, form):
        # Populate `CruiseTaxForm.number_of_passengers`
        passengers_total_form = PassengersTotalForm(data=self.request.POST)
        assert passengers_total_form.is_valid()
        self._cruise_tax_form.number_of_passengers = passengers_total_form.cleaned_data[
            "total_number_of_passengers"
        ]
        self._cruise_tax_form.save(update_fields=("number_of_passengers",))

        # Create or update `PassengersByCountry` objects based on formset data
        passengers_by_country_objects = self._get_passengers_by_country_objects()
        PassengersByCountry.objects.bulk_create(
            passengers_by_country_objects,
            update_conflicts=True,
            unique_fields=["cruise_tax_form", "nationality"],
            update_fields=["number_of_passengers"],
        )

        # Remove any `PassengersByCountry` objects which have 0 passengers after the
        # "create or update" processing above.
        PassengersByCountry.objects.filter(
            cruise_tax_form=self._cruise_tax_form,
            number_of_passengers=0,
        ).delete()

        # Go to next step (environmental and maintenance fees)
        return self.get_redirect_for_form(
            "havneafgifter:environmental_tax_create",
            self._cruise_tax_form,
        )

    def _get_passengers_by_country_objects(self) -> list[PassengersByCountry]:
        formset = self.get_form()
        return [
            PassengersByCountry(
                cruise_tax_form=self._cruise_tax_form,
                **cleaned_data,  # type: ignore
            )
            for cleaned_data in formset.cleaned_data  # type: ignore
        ]

    def _get_initial_formset_data(self):
        def pk(val):
            if val is not None:
                return val[0]

        def number_of_passengers(val):
            if val is not None:
                return val[1]
            return 0

        current = {
            pbc.nationality: (pbc.pk, pbc.number_of_passengers)
            for pbc in PassengersByCountry.objects.filter(
                cruise_tax_form=self._cruise_tax_form,
            )
        }

        return [
            {
                "pk": pk(current.get(nationality)),
                "number_of_passengers": number_of_passengers(current.get(nationality)),
                "nationality": nationality,
            }
            for nationality in Nationality
        ]


class EnvironmentalTaxCreateView(_CruiseTaxFormSetView):
    template_name = "havneafgifter/environmental_tax_create.html"
    form_class = DisembarkmentForm

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs["initial"] = self._get_initial_formset_data()
        return form_kwargs

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data["disembarkment_formset"] = self.get_form()
        return context_data

    def form_valid(self, form):
        # Create or update `Disembarkment` objects based on formset data
        disembarkment_objects = self._get_disembarkment_objects()
        Disembarkment.objects.bulk_create(
            disembarkment_objects,
            update_conflicts=True,
            unique_fields=["cruise_tax_form", "disembarkment_site"],
            update_fields=["number_of_passengers"],
        )

        # Remove any `Disembarkment` objects which have 0 passengers after the
        # "create or update" processing above.
        Disembarkment.objects.filter(
            cruise_tax_form=self._cruise_tax_form,
            number_of_passengers=0,
        ).delete()

        # User is now all done filling out data for cruise ship.
        # Go to detail view to display result.
        return self.get_redirect_for_form(
            "havneafgifter:receipt_detail_html",
            self._cruise_tax_form,
        )

    def _get_disembarkment_objects(self) -> list[Disembarkment]:
        formset = self.get_form()
        disembarkment_objects = [
            Disembarkment(
                cruise_tax_form=self._cruise_tax_form,
                **cleaned_data,  # type: ignore
            )
            for cleaned_data in formset.cleaned_data  # type: ignore
        ]
        return disembarkment_objects

    def _get_initial_formset_data(self):
        def pk(val):
            if val is not None:
                return val[0]

        def number_of_passengers(val):
            if val is not None:
                return val[1]
            return 0

        current = {
            d.disembarkment_site: (d.pk, d.number_of_passengers)
            for d in Disembarkment.objects.filter(
                cruise_tax_form=self._cruise_tax_form,
            )
        }

        return [
            {
                "pk": pk(current.get(disembarkment_site)),
                "number_of_passengers": number_of_passengers(
                    current.get(disembarkment_site)
                ),
                "disembarkment_site": disembarkment_site.pk,
            }
            for disembarkment_site in DisembarkmentSite.objects.all()
        ]


class ReceiptDetailView(LoginRequiredMixin, HavneafgiftView, DetailView):
    def get(self, request, *args, **kwargs):
        form = self.get_object()
        if form is None:
            return HttpResponseNotFound(
                f"No form found for ID {self.kwargs.get(self.pk_url_kwarg)}"
            )

        if not form.has_permission(request.user, "view"):
            raise PermissionDenied

        form.calculate_tax(save=True)
        receipt = form.get_receipt(base="havneafgifter/base.html", request=request)

        return HttpResponse(receipt.html)

    def get_object(self, queryset=None):
        pk = self.kwargs.get(self.pk_url_kwarg)
        try:
            return CruiseTaxForm.objects.get(pk=pk)
        except CruiseTaxForm.DoesNotExist:
            try:
                return HarborDuesForm.objects.get(pk=pk)
            except HarborDuesForm.DoesNotExist:
                return None


class PreviewPDFView(ReceiptDetailView):
    def get(self, request, *args, **kwargs):
        form = self.get_object()
        if form is None:
            return HttpResponseNotFound(
                f"No form found for ID {self.kwargs.get(self.pk_url_kwarg)}"
            )
        else:
            receipt = form.get_receipt()
        return HttpResponse(
            receipt.pdf,
            content_type="application/pdf",
        )


class HarborDuesFormListView(
    LoginRequiredMixin, PermissionsMixin, HavneafgiftView, SingleTableView
):
    table_class = HarborDuesFormTable

    def get_queryset(self):
        return HarborDuesForm.filter_user_permissions(
            HarborDuesForm.objects.all(), self.request.user, "view"
        )
