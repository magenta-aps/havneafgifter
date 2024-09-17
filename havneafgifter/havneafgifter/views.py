from datetime import datetime
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
from django.core.exceptions import PermissionDenied, ValidationError
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
from django.forms import formset_factory, model_to_dict
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, RedirectView
from django.views.generic.edit import CreateView, FormView, UpdateView
from django_fsm import can_proceed
from django_tables2 import SingleTableMixin, SingleTableView
from project.util import omit

from havneafgifter.forms import (
    AuthenticationForm,
    DisembarkmentForm,
    DisembarkmentTaxRateFormSet,
    HarborDuesFormForm,
    PassengersByCountryForm,
    PassengersTotalForm,
    PortTaxRateFormSet,
    ReasonForm,
    SignupVesselForm,
    StatisticsForm,
    TaxRateForm,
)
from havneafgifter.mails import OnApproveMail, OnRejectMail, OnSubmitForReviewMail
from havneafgifter.models import (
    CruiseTaxForm,
    Disembarkment,
    DisembarkmentSite,
    DisembarkmentTaxRate,
    HarborDuesForm,
    Municipality,
    Nationality,
    PassengersByCountry,
    Port,
    PortTaxRate,
    ShipType,
    Status,
    TaxRates,
    UserType,
)
from havneafgifter.responses import (
    HavneafgifterResponseBadRequest,
    HavneafgifterResponseForbidden,
    HavneafgifterResponseNotFound,
)
from havneafgifter.tables import (
    HarborDuesFormFilter,
    HarborDuesFormTable,
    StatistikTable,
    TaxRateTable,
)
from havneafgifter.view_mixins import (
    CacheControlMixin,
    GetFormView,
    HandleNotificationMailMixin,
    HarborDuesFormMixin,
    HavneafgiftView,
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


class HarborDuesFormCreateView(HarborDuesFormMixin, CacheControlMixin, CreateView):
    model = HarborDuesForm
    form_class = HarborDuesFormForm

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        return self.prevent_response_caching(response)


class _CruiseTaxFormSetView(
    LoginRequiredMixin, CacheControlMixin, HavneafgiftView, FormView
):
    """Shared base class for views that create a set of model objects related
    to a `CruiseTaxForm`, e.g. `PassengersByCountry` or `Disembarkment`.
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        pk = kwargs["pk"]
        qs = CruiseTaxForm.filter_user_permissions(
            CruiseTaxForm.objects.filter(
                pk=pk,
                status__in=[Status.DRAFT, Status.REJECTED],
            ),
            request.user,
            "view",
        )
        try:
            self._cruise_tax_form = qs.get(pk=pk)
        except CruiseTaxForm.DoesNotExist:
            self._cruise_tax_form = None

    def get(self, request, *args, **kwargs):
        response = self._check_permission() or super().get(request, *args, **kwargs)
        return self.prevent_response_caching(response)

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
            return HavneafgifterResponseForbidden(
                self.request,
                _("This form was already submitted and can no longer be edited"),
            )


class PassengerTaxCreateView(_CruiseTaxFormSetView):
    template_name = "havneafgifter/passenger_tax_create.html"
    form_class = PassengersByCountryForm

    def post(self, request, *args, **kwargs):
        try:
            sum_passengers_by_country = sum(
                pbc.number_of_passengers
                for pbc in self._get_passengers_by_country_objects()
            )
        except ValidationError as e:
            return HavneafgifterResponseBadRequest(request, e.message)
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
        if not formset.is_valid():
            raise ValidationError(_("Invalid data in passenger count list"))
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


class EnvironmentalTaxCreateView(HandleNotificationMailMixin, _CruiseTaxFormSetView):
    template_name = "havneafgifter/environmental_tax_create.html"
    form_class = DisembarkmentForm

    def get_form_kwargs(self):
        form_kwargs = super().get_form_kwargs()
        form_kwargs["initial"] = self._get_initial_formset_data()
        return form_kwargs

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data["object"] = self._cruise_tax_form
        context_data["disembarkment_formset"] = self.get_form()
        context_data["user_is_ship"] = self.request.user.user_type == UserType.SHIP
        return context_data

    def form_valid(self, form):
        # If user is submitting this cruise tax form for review, make sure we
        # validate it first, and send the user back to step 1 if the form is
        # not valid.
        try:
            submitted_for_review: bool = (
                self._validate_cruise_tax_form_submitted_for_review()
            )
        except ValidationError as error:
            return self._return_to_step_1_with_errors(error.message)

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
        if submitted_for_review:
            self._cruise_tax_form.save(update_fields=("status",))
            self.handle_notification_mail(OnSubmitForReviewMail, self._cruise_tax_form)

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

    def _validate_cruise_tax_form_submitted_for_review(self) -> bool:
        submitted_for_review = False

        # Determine if user selected "Submit" (status=NEW) or "Save as draft"
        # (status=DRAFT).
        status = self.request.POST.get("status")

        # Update cruise tax form status, if submitting for review
        if status == Status.NEW.value and can_proceed(
            self._cruise_tax_form.submit_for_review
        ):
            self._cruise_tax_form.submit_for_review()
            submitted_for_review = True

            # Validate the data on the cruise tax form, taking the new status into
            # account.
            form = HarborDuesFormForm(
                self.request.user,  # type: ignore
                status=Status.NEW,
                instance=self._cruise_tax_form,
                data=model_to_dict(self._cruise_tax_form),
            )

            if not form.is_valid():
                raise ValidationError(
                    _(
                        "Cruise tax form contains one or more errors. "
                        "Please correct them."
                    )
                )

        return submitted_for_review

    def _return_to_step_1_with_errors(self, message: str) -> HttpResponse:
        messages.error(self.request, message)
        return self.get_redirect_for_form(
            "havneafgifter:draft_edit",
            self._cruise_tax_form,
            status=Status.NEW.value,
        )


class ReceiptDetailView(LoginRequiredMixin, HavneafgiftView, DetailView):
    def get(self, request, *args, **kwargs):
        form = self.get_object()
        if form is None:
            return HavneafgifterResponseNotFound(
                request, f"No form found for ID {self.kwargs.get(self.pk_url_kwarg)}"
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


class HarborDuesFormUpdateView(HarborDuesFormMixin, CacheControlMixin, UpdateView):
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

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Pass `data` to form to ensure that validation errors are
        # re-evaluated and displayed.
        if self.request.method == "GET":
            kwargs["data"] = model_to_dict(self.object)
        return kwargs

    def get(self, request, *args, **kwargs):
        form: HarborDuesForm | CruiseTaxForm | None = self.get_object()
        if form is None:
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
            response = super().get(self, request, *args, **kwargs)
            return self.prevent_response_caching(response)

    def get_template_names(self):
        return ["havneafgifter/harborduesform_form.html"]


class PreviewPDFView(ReceiptDetailView):
    def get(self, request, *args, **kwargs):
        form = self.get_object()
        if form is None:
            return HavneafgifterResponseNotFound(
                request, f"No form found for ID {self.kwargs.get(self.pk_url_kwarg)}"
            )
        else:
            receipt = form.get_receipt()
        return HttpResponse(
            receipt.pdf,
            content_type="application/pdf",
        )


class ApproveView(
    LoginRequiredMixin, HavneafgiftView, HandleNotificationMailMixin, UpdateView
):
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
            return HavneafgifterResponseForbidden(
                self.request,
                _(
                    "You do not have the required permissions to approve "
                    "harbor dues forms"
                ),
            )
        # There is no form to fill for "approve" actions, so it does not make sense to
        # implement `form_valid`. Instead, we just perform the object update here.
        harbor_dues_form.approve()
        harbor_dues_form.save()
        self.handle_notification_mail(OnApproveMail, harbor_dues_form)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("havneafgifter:harbor_dues_form_list")


class RejectView(
    LoginRequiredMixin, HavneafgiftView, HandleNotificationMailMixin, UpdateView
):
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
            return HavneafgifterResponseForbidden(
                self.request,
                _(
                    "You do not have the required permissions to reject "
                    "harbor dues forms"
                ),
            )
        # Call `form_valid` if `ReasonForm` is indeed valid
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        harbor_dues_form = self.object
        harbor_dues_form.reject(reason=form.cleaned_data["reason"])
        harbor_dues_form.save()
        self.handle_notification_mail(OnRejectMail, harbor_dues_form)
        return response

    def get_success_url(self):
        return reverse("havneafgifter:harbor_dues_form_list")


class HarborDuesFormListView(LoginRequiredMixin, HavneafgiftView, SingleTableView):
    table_class = HarborDuesFormTable
    context_object_name = "harbordues"

    custom_order = [Status.DRAFT, Status.NEW, Status.APPROVED, Status.REJECTED]
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
        queryset = HarborDuesForm.filter_user_permissions(
            HarborDuesForm.objects.all(), self.request.user, "view"
        ).order_by(self.ordering_criteria, "-date")
        self.filterset = HarborDuesFormFilter(self.request.GET, queryset=queryset)
        return self.filterset.qs

    def get_context_data(self, **context):
        context = super().get_context_data(**context)
        context["form"] = self.filterset.form
        return context


class TaxRateListView(LoginRequiredMixin, SingleTableView):
    table_class = TaxRateTable

    def get_queryset(self):
        return TaxRates.filter_user_permissions(
            TaxRates.objects.all(), self.request.user, "view"
        ).order_by("start_datetime")


class TaxRateDetailView(LoginRequiredMixin, DetailView):
    model = TaxRates

    def post(self, request, *args, **kwargs):
        if "delete" in request.POST:
            self.object = self.get_object()
            if self.object.has_permission(self.request.user, "delete", False):
                self.object.delete()
                return redirect("havneafgifter:tax_rate_list")
            else:
                return HavneafgifterResponseForbidden(
                    self.request,
                    _("You do not have the required permissions to delete a tax rate"),
                )
        # return HavneafgifterResponseBadRequest(
        #    self.request, _("There is nothing to delete")
        # )

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            **{
                **kwargs,
                "port_tax_rates": self.object.port_tax_rates.order_by(
                    F("vessel_type").asc(nulls_first=True),
                    F("port").asc(nulls_first=True),
                ),
                "disembarkment_tax_rates": self.object.disembarkment_tax_rates.order_by(
                    F("municipality").asc(nulls_first=True),
                    F("disembarkment_site").asc(nulls_first=True),
                ),
                "can_edit": self.object.has_permission(
                    self.request.user, "change", False
                )
                and self.object.can_edit,
                "can_clone": self.object.has_permission(
                    self.request.user, "add", False
                ),
                "can_delete": self.object.has_permission(
                    self.request.user, "delete", False
                )
                and self.object.can_delete,
                "show_changing_buttons": self.request.user.groups.filter(
                    name="TaxAuthority"
                ).exists()
                or self.request.user.is_superuser,
            }
        )


class StatisticsView(LoginRequiredMixin, CSPViewMixin, SingleTableMixin, GetFormView):
    form_class = StatisticsForm
    template_name = "havneafgifter/statistik.html"
    table_class = StatistikTable

    def dispatch(self, request, *args, **kwargs):
        if (
            "havneafgifter.view_harborduesform"
            not in request.user.get_all_permissions()
        ):
            return HavneafgifterResponseForbidden(
                self.request,
                _("You do not have the required permissions to view statistics"),
            )
        return super().dispatch(request, *args, **kwargs)

    def get_table_data(self):
        form = self.get_form()
        if form.is_valid():
            qs = HarborDuesForm.objects.filter(status=Status.APPROVED)
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


class TaxRateFormView(LoginRequiredMixin, UpdateView):
    model = TaxRates
    form_class = TaxRateForm
    template_name = "havneafgifter/taxrateform.html"
    success_url = reverse_lazy("havneafgifter:tax_rate_list")
    clone = False

    def get_object(self, queryset=None):
        object = super().get_object(queryset)
        if object.has_permission(self.request.user, "add" if self.clone else "change"):
            return object
        else:
            raise PermissionDenied

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except PermissionDenied:
            return HavneafgifterResponseForbidden(
                request, _("Du har ikke rettighed til at se denne side.")
            )

    def get_initial(self):
        initial = super().get_initial()
        if self.clone:
            initial["start_datetime"] = datetime.now() + timezone.timedelta(weeks=1)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(
            **{
                **kwargs,
                "clone": self.clone,
                "vessel_type_choices": ShipType.choices,
                "port_choices": [
                    (port.pk, port.name) for port in Port.objects.order_by("name")
                ],
                "municipality_choices": DisembarkmentSite.municipality.field.choices,
                "disembarkmentsite_map": {
                    municipality.value: list(
                        DisembarkmentSite.objects.filter(
                            municipality=municipality
                        ).values_list("pk", "name")
                    )
                    for municipality in Municipality
                },
            }
        )
        if "port_formset" not in context:
            context["port_formset"] = self.get_port_formset()
        if "disembarkmentrate_formset" not in context:
            context["disembarkmentrate_formset"] = self.get_disembarkmentrate_formset()
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return kwargs

    def get_port_formset(self):
        if self.clone:
            initial = (
                [
                    omit(model_to_dict(item), "id", "tax_rates")
                    for item in self.object.port_tax_rates.all()
                ]
                if self.object and self.object.pk
                else []
            )
            extradata = [
                {
                    "name": item.name,
                    "can_delete": item.can_delete,
                }
                for item in PortTaxRate.objects.filter(tax_rates_id=self.kwargs["pk"])
            ]
            formset = PortTaxRateFormSet(
                data=self.request.POST or None, initial=initial, extradata=extradata
            )
            formset.extra = len(initial)
            return formset
        else:
            return PortTaxRateFormSet(self.request.POST or None, instance=self.object)

    def get_disembarkmentrate_formset(self):
        if self.clone:
            initial = (
                [
                    omit(model_to_dict(item), "id", "tax_rates")
                    for item in self.object.disembarkment_tax_rates.all()
                ]
                if self.object and self.object.pk
                else []
            )
            extradata = [
                {"name": item.name}
                for item in DisembarkmentTaxRate.objects.filter(
                    tax_rates_id=self.kwargs["pk"]
                )
            ]
            formset = DisembarkmentTaxRateFormSet(
                data=self.request.POST or None, initial=initial, extradata=extradata
            )
            formset.extra = len(initial)
            return formset
        else:
            return DisembarkmentTaxRateFormSet(
                self.request.POST or None, instance=self.object
            )

    def form_valid(self, form, formset1, formset2):
        self.object = form.save()

        if self.clone:
            formset1.instance = self.object
            formset2.instance = self.object

        formset1.save()
        formset2.save()
        return super().form_valid(form)

    def form_invalid(self, form, formset1, formset2):
        return self.render_to_response(
            self.get_context_data(
                form=form, port_formset=formset1, disembarkmentrate_formset=formset2
            )
        )

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        if self.clone:
            self.object.pk = None

        form = self.get_form()
        formset1 = self.get_port_formset()
        formset2 = self.get_disembarkmentrate_formset()

        if form.is_valid() and formset1.is_valid() and formset2.is_valid():
            return self.form_valid(form, formset1, formset2)
        else:
            return self.form_invalid(form, formset1, formset2)
