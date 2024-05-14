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
from django.forms import formset_factory
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, RedirectView
from django.views.generic.edit import CreateView, FormView

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
    ShipType,
)


class HavneafgiftView:
    def get_context_data(self, **context):
        return super().get_context_data(
            **{
                **context,
                "version": settings.VERSION,
            }
        )


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


class HarborDuesFormCreateView(LoginRequiredMixin, HavneafgiftView, CreateView):
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

    def form_valid(self, form):
        harbor_dues_form = form.save(commit=False)
        if harbor_dues_form.vessel_type == ShipType.CRUISE:
            # `CruiseTaxForm` inherits from `HarborDuesForm`, so we can create
            # a `CruiseTaxForm` based on the fields on `HarborDuesForm`.
            cruise_tax_form = CruiseTaxForm.objects.create(
                **{
                    k: v
                    for k, v in harbor_dues_form.__dict__.items()
                    if not k.startswith("_")  # skip `_state`, etc.
                }
            )
            # Send user to next step - filling out passenger tax info
            return HttpResponseRedirect(
                reverse(
                    "havneafgifter:passenger_tax_create",
                    kwargs={"pk": cruise_tax_form.pk},
                )
            )
        else:
            # User is all done filling out data for this vessel
            # Go to detail view to display result.
            harbor_dues_form.save()
            messages.add_message(self.request, messages.SUCCESS, _("Thanks"))
            return HttpResponseRedirect(
                reverse(
                    "havneafgifter:receipt_detail_html",
                    kwargs={"pk": harbor_dues_form.pk},
                )
            )


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
        form_kwargs["initial"] = [
            {"nationality": nationality, "number_of_passengers": 0}
            for nationality in Nationality
        ]
        return form_kwargs

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data["passengers_total_form"] = kwargs.get(
            "passengers_total_form", PassengersTotalForm()
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

        # Create `PassengersByCountry` objects based on formset data
        passengers_by_country_objects = self._get_passengers_by_country_objects()
        PassengersByCountry.objects.bulk_create(passengers_by_country_objects)

        # Go to next step (environmental and maintenance fees)
        return HttpResponseRedirect(
            reverse(
                "havneafgifter:environmental_tax_create",
                kwargs={"pk": self._cruise_tax_form.pk},
            )
        )

    def _get_passengers_by_country_objects(self) -> list[PassengersByCountry]:
        formset = self.get_form()
        return [
            PassengersByCountry(
                cruise_tax_form=self._cruise_tax_form,
                **cleaned_data,  # type: ignore
            )
            for cleaned_data in formset.cleaned_data  # type: ignore
            if cleaned_data["number_of_passengers"] > 0  # type: ignore
        ]


class EnvironmentalTaxCreateView(_CruiseTaxFormSetView):
    template_name = "havneafgifter/environmental_tax_create.html"
    form_class = DisembarkmentForm

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs["initial"] = [
            {"disembarkment_site": disembarkment_site.pk, "number_of_passengers": 0}
            for disembarkment_site in DisembarkmentSite.objects.all()
        ]
        return form_kwargs

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data["disembarkment_formset"] = self.get_form()
        return context_data

    def form_valid(self, form):
        disembarkment_objects = [
            Disembarkment(cruise_tax_form=self._cruise_tax_form, **cleaned_data)
            for cleaned_data in self.get_form().cleaned_data
            if cleaned_data["number_of_passengers"] > 0
        ]
        Disembarkment.objects.bulk_create(disembarkment_objects)

        # User is all done filling out data for cruise ship.
        # Go to detail view to display result.
        messages.add_message(self.request, messages.SUCCESS, _("Thanks"))
        return HttpResponseRedirect(
            reverse(
                "havneafgifter:receipt_detail_html",
                kwargs={"pk": self._cruise_tax_form.pk},
            )
        )


class ReceiptDetailView(LoginRequiredMixin, HavneafgiftView, DetailView):
    def get(self, request, *args, **kwargs):
        form = self.get_object()
        if form is None:
            return HttpResponseNotFound(
                f"No form found for ID {self.kwargs.get(self.pk_url_kwarg)}"
            )
        else:
            form.calculate_tax(save=True)
            receipt = form.get_receipt(base="havneafgifter/base.html", request=request)
        return HttpResponse(receipt.html)

    def post(self, request, *args, **kwargs):
        form = self.get_object()
        if form is None:
            return HttpResponseNotFound(
                f"No form found for ID {self.kwargs.get(self.pk_url_kwarg)}"
            )
        else:
            email_message, status = form.send_email()
            messages.add_message(
                request,
                messages.SUCCESS if status == 1 else messages.ERROR,
                _("Email sent") if status == 1 else _("Error when sending email"),
            )
            return HttpResponseRedirect(
                reverse(
                    "havneafgifter:receipt_detail_html",
                    kwargs={"pk": form.pk},
                )
            )

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
