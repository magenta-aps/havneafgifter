from decimal import Decimal

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
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.core.exceptions import PermissionDenied
from django.db.models import (
    Case,
    Count,
    F,
    IntegerField,
    OuterRef,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.forms import formset_factory
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseRedirect,
)
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, RedirectView
from django.views.generic.edit import CreateView, FormView, UpdateView
from django_tables2 import SingleTableMixin, SingleTableView

from havneafgifter.forms import (
    AuthenticationForm,
    DisembarkmentForm,
    HarborDuesFormForm,
    PassengersByCountryForm,
    PassengersTotalForm,
    ReasonForm,
    SignupVesselForm,
    StatisticsForm,
)
from havneafgifter.models import (
    CruiseTaxForm,
    Disembarkment,
    DisembarkmentSite,
    HarborDuesForm,
    Municipality,
    Nationality,
    PassengersByCountry,
    PermissionsMixin,
    Port,
    ShipType,
    Status,
)
from havneafgifter.tables import HarborDuesFormTable, StatistikTable
from havneafgifter.view_mixins import (
    GetFormView,
    HarborDuesFormMixin,
    HavneafgiftView,
    _SendEmailMixin,
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
            return reverse("havneafgifter:harbor_dues_form_list")
        return reverse("havneafgifter:harbor_dues_form_list")


class SignupVesselView(HavneafgiftView, CSPViewMixin, CreateView):
    template_name = "havneafgifter/signup_vessel.html"
    form_class = SignupVesselForm

    def form_valid(self, form):
        # Save `User` object - This also populates `self.object`
        response = super().form_valid(form)

        # Add `User` object to the `Group` called `Ship`, making the user a ship user
        ship_group = Group.objects.get(name="Ship")
        self.object.groups.add(ship_group)

        # Instruct user and then send them to the login page
        messages.success(
            self.request,
            _("Please sign in using the IMO number as username"),
        )
        return response

    def get_success_url(self):
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
                    backend="django_mitid_auth.saml.backend.Saml2Backend",
                )
        if not self.request.user.is_authenticated:
            return reverse("havneafgifter:login-failed")
        backpage = self.request.COOKIES.get("back")
        if backpage:
            return backpage
        return reverse("havneafgifter:root")


class HarborDuesFormCreateView(HarborDuesFormMixin, CreateView):
    model = HarborDuesForm
    form_class = HarborDuesFormForm


class _CruiseTaxFormSetView(LoginRequiredMixin, HavneafgiftView, FormView):
    """Shared base class for views that create a set of model objects related
    to a `CruiseTaxForm`, e.g. `PassengersByCountry` or `Disembarkment`.
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        pk = kwargs["pk"]
        qs = CruiseTaxForm.filter_user_permissions(
            CruiseTaxForm.objects.filter(pk=pk, status=Status.DRAFT),
            request.user,
            "view",
        )
        try:
            self._cruise_tax_form = qs.get(pk=pk)
        except CruiseTaxForm.DoesNotExist:
            self._cruise_tax_form = None

    def get(self, request, *args, **kwargs):
        response = self._check_permission() or super().get(request, *args, **kwargs)
        # Ensure that when/if users go back to this view from the receipt page,
        # their browser does not show a cached response (which may present them with a
        # seemingly "editable" form that cannot be submitted if the form status is NEW.
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, post-check=0, pre-check=0"
        )
        return response

    def post(self, request, *args, **kwargs):
        return self._check_permission() or super().post(request, *args, **kwargs)

    def get_form(self, form_class=None):
        factory = formset_factory(
            self.form_class,
            can_order=False,
            can_delete=False,
            extra=0,
        )
        return factory(**self.get_form_kwargs())

    def _check_permission(self):
        if self._cruise_tax_form is None:
            return HttpResponseForbidden(
                _("You do not have permission to edit this cruise tax form")
            )


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


class EnvironmentalTaxCreateView(_SendEmailMixin, _CruiseTaxFormSetView):
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
        # Handle `status` (DRAFT or NEW) and send email if NEW.
        self._handle_status()

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

    def _handle_status(self):
        status = self.request.POST.get("status")
        if status == Status.NEW.value:
            self._cruise_tax_form.submit_for_review()
            self._cruise_tax_form.save()
            self._send_email(self._cruise_tax_form, self.request)


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


class HarborDuesFormUpdateView(HarborDuesFormMixin, UpdateView):
    model = HarborDuesForm
    form_class = HarborDuesFormForm

    def get_object(self, queryset=None):
        pk = self.kwargs.get(self.pk_url_kwarg)
        try:
            return CruiseTaxForm.objects.get(pk=pk)
        except CruiseTaxForm.DoesNotExist:
            try:
                return HarborDuesForm.objects.get(pk=pk)
            except HarborDuesForm.DoesNotExist:
                return None

    def get(self, request, *args, **kwargs):
        form = self.get_object()
        if not form:
            return HttpResponseRedirect(
                reverse(
                    "havneafgifter:receipt_detail_html",
                    kwargs={"pk": self.kwargs.get(self.pk_url_kwarg)},
                )
            )
        if not form.has_permission(request.user, "change", False):
            return HttpResponseRedirect(
                reverse("havneafgifter:receipt_detail_html", kwargs={"pk": form.pk})
            )
        else:
            return super().get(self, request, *args, **kwargs)

    def get_template_names(self):
        return ["havneafgifter/harborduesform_form.html"]


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


class ApproveView(LoginRequiredMixin, HavneafgiftView, UpdateView):
    http_method_names = ["post"]

    def get_queryset(self):
        return HarborDuesForm.filter_user_permissions(
            HarborDuesForm.objects.filter(status=Status.NEW),
            self.request.user,
            "approve",
        )

    def post(self, request, *args, **kwargs):
        # If we cannot get the specified `HarborDuesForm` object, it is probably
        # because we don't have the required `approve` permission.
        try:
            harbor_dues_form = self.get_object()
        except Http404:
            return HttpResponseForbidden(
                _(
                    "You do not have the required permissions to approve "
                    "harbor dues forms"
                )
            )
        # There is no form to fill for "approve" actions, so it does not make sense to
        # implement `form_valid`. Instead, we just perform the object update here.
        harbor_dues_form.approve()
        harbor_dues_form.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("havneafgifter:harbor_dues_form_list")


class RejectView(LoginRequiredMixin, HavneafgiftView, UpdateView):
    form_class = ReasonForm
    http_method_names = ["post"]

    def get_queryset(self):
        return HarborDuesForm.filter_user_permissions(
            HarborDuesForm.objects.filter(status=Status.NEW),
            self.request.user,
            "reject",
        )

    def post(self, request, *args, **kwargs):
        # If we cannot get the specified `HarborDuesForm` object, it is probably
        # because we don't have the required `approve` permission.
        try:
            self.object = self.get_object()
        except Http404:
            return HttpResponseForbidden(
                _(
                    "You do not have the required permissions to reject "
                    "harbor dues forms"
                )
            )
        # Call `form_valid` if `ReasonForm` is indeed valid
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        harbor_dues_form = self.object
        harbor_dues_form.reject(reason=form.cleaned_data["reason"])
        harbor_dues_form.save()
        return response

    def get_success_url(self):
        return reverse("havneafgifter:harbor_dues_form_list")


class HarborDuesFormListView(
    LoginRequiredMixin, PermissionsMixin, HavneafgiftView, SingleTableView
):
    table_class = HarborDuesFormTable

    custom_order = [Status.DRAFT, Status.NEW, Status.DONE]
    ordering_criteria = Case(
        *[
            When(status=name, then=Value(index))
            for index, name in enumerate(custom_order)
        ],
        default=Value(
            len(custom_order)
        ),  # Default order value for names not in the custom_order list
        output_field=IntegerField(),
    )

    def get_queryset(self):
        return HarborDuesForm.filter_user_permissions(
            HarborDuesForm.objects.all(), self.request.user, "view"
        ).order_by(self.ordering_criteria, "-date")


class StatisticsView(
    LoginRequiredMixin, PermissionsMixin, CSPViewMixin, SingleTableMixin, GetFormView
):
    form_class = StatisticsForm
    template_name = "havneafgifter/statistik.html"
    table_class = StatistikTable

    def get_table_data(self):
        form = self.get_form()
        if form.is_valid():
            qs = HarborDuesForm.objects.filter(status=Status.DONE)
            group_fields = []
            shortcut_fields = {
                "municipality": F(
                    "cruisetaxform__disembarkment__disembarkment_site__municipality"
                ),
                "site": F("cruisetaxform__disembarkment__disembarkment_site"),
            }
            filter_fields = {}

            for action in ("arrival", "departure"):
                for op in ("gt", "lt"):
                    field_value = form.cleaned_data[f"{action}_{op}"]
                    if field_value:
                        filter_fields[f"datetime_of_{action}__{op}"] = field_value

            for field in ("municipality", "vessel_type", "port_of_call", "site"):
                field_value = form.cleaned_data[field]
                if field_value:
                    filter_fields[f"{field}__in"] = field_value
                    group_fields.append(field)

            qs = qs.annotate(**shortcut_fields)
            qs = qs.filter(**filter_fields)
            if group_fields:
                qs = qs.values(*group_fields).distinct()
            else:
                qs = qs.values().distinct()

            qs = qs.annotate(
                disembarkment_tax_sum=Coalesce(
                    Sum(
                        Subquery(
                            CruiseTaxForm.objects.filter(id=OuterRef("pk")).values(
                                "disembarkment_tax"
                            )
                        )
                    ),
                    Decimal("0.00"),
                ),
                harbour_tax_sum=Coalesce(Sum("harbour_tax"), Decimal("0.00")),
                count=Count("pk", distinct=True),
            )
            if not group_fields:
                qs = qs.values(
                    "id",
                    "municipality",
                    "vessel_type",
                    "port_of_call",
                    "site",
                    "disembarkment_tax_sum",
                    "harbour_tax_sum",
                    "count",
                )
            qs.order_by("municipality", "vessel_type", "port_of_call", "site")

            items = list(qs)
            for item in items:
                municipality = item.get("municipality")
                if municipality:
                    item["municipality"] = Municipality(municipality).label

                port_of_call = item.get("port_of_call")
                if port_of_call:
                    item["port_of_call"] = Port.objects.get(pk=port_of_call).name

                site = item.get("site")
                if site:
                    item["site"] = DisembarkmentSite.objects.get(pk=site).name

                vessel_type = item.get("vessel_type")
                if vessel_type:
                    item["vessel_type"] = ShipType(vessel_type).label
            return items
        return []
