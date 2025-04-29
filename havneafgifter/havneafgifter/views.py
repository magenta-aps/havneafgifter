from datetime import datetime
from decimal import Decimal

from csp_helpers.mixins import CSPViewMixin
from dateutil.relativedelta import relativedelta
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
from django.db.models import Case, F, IntegerField, OuterRef, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.forms import inlineformset_factory, model_to_dict
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView, RedirectView
from django.views.generic.edit import CreateView, UpdateView
from django_fsm import can_proceed, has_transition_perm
from django_tables2 import SingleTableMixin, SingleTableView
from django_tables2.export.views import ExportMixin
from project.util import new_taxrate_start_datetime, omit

from havneafgifter.forms import (
    AuthenticationForm,
    DisembarkmentTaxRateFormSet,
    HarborDuesFormForm,
    PassengerStatisticsForm,
    PassengersTotalForm,
    PortTaxRateFormSet,
    ReasonForm,
    SignupVesselForm,
    StatisticsForm,
    TaxRateForm,
    UpdateVesselForm,
)
from havneafgifter.mails import (
    OnApproveMail,
    OnApproveReceipt,
    OnRejectMail,
    OnRejectReceipt,
    OnSendToAgentMail,
    OnSubmitForReviewMail,
    OnSubmitForReviewReceipt,
)
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
    PortAuthority,
    PortTaxRate,
    ShipType,
    Status,
    TaxRates,
    UserType,
    Vessel,
)
from havneafgifter.responses import (
    HavneafgifterResponseForbidden,
    HavneafgifterResponseNotFound,
)
from havneafgifter.tables import (
    HarborDuesFormFilter,
    HarborDuesFormTable,
    PassengerStatisticsTable,
    StatistikTable,
    TaxRateTable,
)
from havneafgifter.view_mixins import (
    CacheControlMixin,
    GetFormView,
    HandleNotificationMailMixin,
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


class UpdateVesselView(HavneafgiftView, CSPViewMixin, UpdateView):
    template_name = "havneafgifter/update_vessel.html"
    form_class = UpdateVesselForm

    def get_initial(self):
        initial = super().get_initial()
        initial["user"] = self.request.user
        initial["imo"] = self.request.user.username
        return initial

    def get_object(self, queryset=None):
        try:
            return Vessel.objects.get(imo=self.request.user.username)
        except Vessel.DoesNotExist:
            raise Http404(_("No vessel found"))

    def get_success_url(self):
        return reverse("havneafgifter:harbor_dues_form_list")


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
            print(f"saml data: {self.request.session.get('saml')}")
            user = authenticate(
                request=self.request, saml_data=self.request.session.get("saml")
            )
            print(f"user: {user}")
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


class HarborDuesFormCreateView(
    LoginRequiredMixin,
    CSPViewMixin,
    HandleNotificationMailMixin,
    HavneafgiftView,
    CacheControlMixin,
    DetailView,
):
    template_name = "havneafgifter/form_create.html"
    http_method_names = ["get", "post"]

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        return self.prevent_response_caching(response)

    def post(self, request, *args, **kwargs):
        base_form = self.get_base_form(
            instance=self.get_object(),
            data=self.request.POST,
        )

        passenger_total_form = None
        passenger_formset = None
        disembarkment_formset = None
        if base_form.is_valid():
            o = self.base_form_valid(base_form)
            # TODO: Kast exception i stedet
            if isinstance(o, HttpResponse):
                return o

            passenger_total_form = self.get_passenger_total_form(data=self.request.POST)
            passenger_formset = self.get_passenger_formset(data=self.request.POST)

            disembarkment_formset = self.get_disembarkment_formset(
                data=self.request.POST
            )
            if (
                passenger_formset.is_valid()
                and passenger_total_form.is_valid()
                and disembarkment_formset.is_valid()
            ):
                if isinstance(self.object, CruiseTaxForm):
                    user_total = passenger_total_form.cleaned_data[
                        "total_number_of_passengers"
                    ]
                    actual_total = 0
                    for item in passenger_formset.cleaned_data:
                        if not item.get("DELETE", True):
                            actual_total += item.get("number_of_passengers", 0)
                    # Save the total number of passengers entered by the user on the
                    # cruise tax form.
                    self.object.number_of_passengers = user_total
                    # Add form error if total number entered does not equal sum of
                    # nationalities.
                    # TODO: læg denne validering ind så den kaldes under full_clean
                    passenger_total_form.validate_total(actual_total)

                if passenger_total_form.is_valid():
                    status = self.object.status

                    if status == Status.NEW:
                        self.object.submit_for_review()
                        self.object.save()
                        self.object.calculate_tax(save=True, force_recalculation=True)
                        self.handle_notification_mail(
                            OnSubmitForReviewMail, self.object
                        )
                        self.handle_notification_mail(
                            OnSubmitForReviewReceipt, self.object
                        )
                    elif status == Status.DRAFT:
                        # Send notification to agent if saved by a ship user.
                        self.object.save()
                        self.object.calculate_tax(save=True, force_recalculation=True)

                    # Save related inline model formsets for
                    # passengers and disembarkments
                    passenger_formset.save()
                    disembarkment_formset.save()

                    if (
                        self.request.user.user_type == UserType.SHIP
                        and self.object.shipping_agent
                    ):
                        self.handle_notification_mail(OnSendToAgentMail, self.object)
                    return self.get_redirect_for_form(
                        "havneafgifter:receipt_detail_html",
                        self.object,
                    )
        return self.render_to_response(
            context={
                "base_form": base_form,
                "passenger_total_form": passenger_total_form
                or self.get_passenger_total_form(data=self.request.POST),
                "passenger_formset": passenger_formset
                or self.get_passenger_formset(data=self.request.POST),
                "disembarkment_formset": disembarkment_formset
                or self.get_disembarkment_formset(data=self.request.POST),
            }
        )

    def get_object(self, queryset=None):
        pk = self.kwargs.get(self.pk_url_kwarg)
        self.object = None

        if pk:
            try:
                self.object = CruiseTaxForm.objects.get(pk=pk)
            except CruiseTaxForm.DoesNotExist:
                self.object = (
                    HarborDuesForm.objects.get(pk=pk)
                    if HarborDuesForm.objects.filter(pk=pk).exists()
                    else None
                )
        return self.object

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["base_form"] = self.get_base_form(instance=self.get_object())
        context["passenger_formset"] = self.get_passenger_formset()
        context["disembarkment_formset"] = self.get_disembarkment_formset()

        if isinstance(self.object, CruiseTaxForm):
            total_num = self.object.number_of_passengers
        else:
            total_num = 0

        context["passenger_total_form"] = self.get_passenger_total_form(
            initial={"total_number_of_passengers": total_num}
        )

        return context

    def base_form_valid(self, form):
        harbor_dues_form = form.save(commit=False)

        if can_proceed(harbor_dues_form.submit_for_review) and not has_transition_perm(
            harbor_dues_form.submit_for_review,
            self.request.user,
        ):
            return HavneafgifterResponseForbidden(
                self.request,
                _(
                    "You do not have the required permissions to submit "
                    "harbor dues forms for review"
                ),
            )

        port_of_call = form.cleaned_data.get("port_of_call")

        if port_of_call is not None and port_of_call.name == "Blank":
            harbor_dues_form.port_of_call = None

        if harbor_dues_form.vessel_type == ShipType.CRUISE:
            # `CruiseTaxForm` inherits from `HarborDuesForm`, so we can create
            # a `CruiseTaxForm` based on the fields on `HarborDuesForm`.
            self.object = self._create_or_update_cruise_tax_form(harbor_dues_form)
        else:
            self.object = harbor_dues_form

        return self.object

    def _create_or_update_cruise_tax_form(
        self,
        harbor_dues_form: HarborDuesForm,
    ) -> CruiseTaxForm:
        field_vals = {
            k: v
            for k, v in harbor_dues_form.__dict__.items()
            if not k.startswith("_")  # skip `_state`, etc.
        }

        if harbor_dues_form.pk is None:
            # The `HarborDuesForm` has not yet been saved to the database.
            # If we create the corresponding `CruiseTaxForm`, the corresponding
            # `HarborDuesForm` will be created automatically.
            # return CruiseTaxForm.objects.create(**field_vals)  # pragma: no cover
            cruise_tax_form = CruiseTaxForm(**field_vals)
        else:
            # A `CruiseTaxForm` object may already exist for this PK.
            try:
                cruise_tax_form = CruiseTaxForm.objects.get(
                    harborduesform_ptr=harbor_dues_form.pk
                )
            except CruiseTaxForm.DoesNotExist:
                # A `CruiseTaxForm` does not exist, but the user is trying to save a
                # cruise tax form, i.e. they are editing a harbor dues form and have
                # changed the vessel type to `CRUISE`. Create the corresponding
                # `CruiseTaxForm`.
                cruise_tax_form = CruiseTaxForm(
                    harborduesform_ptr=harbor_dues_form,
                    # Copy all fields from `HarborDuesForm` except `status`
                    **{
                        k: v
                        for k, v in field_vals.items()
                        if k not in ("harborduesform_ptr", "status")
                    },
                )
            else:
                # A `CruiseTaxForm` exists for this PK.
                # Update all its fields, except `status`.
                for k, v in field_vals.items():
                    if k == "status":
                        continue
                    setattr(cruise_tax_form, k, v)
        return cruise_tax_form

    def get_base_form(self, **form_kwargs):
        status = self.request.POST.get("base-status")
        if status is not None:
            status = Status(status)

        return HarborDuesFormForm(
            self.request.user, status=status, prefix="base", **form_kwargs
        )

    def get_passenger_total_form(self, **form_kwargs):
        return PassengersTotalForm(prefix="passenger_total_form", **form_kwargs)

    def get_inlineformset_factory(self, model_class, fields):
        return inlineformset_factory(
            CruiseTaxForm,
            model_class,
            fields=fields,
            can_order=False,
            can_delete=True,
            extra=1,
        )

    def get_passenger_formset(self, **form_kwargs):
        factory = self.get_inlineformset_factory(
            PassengersByCountry,
            ["id", "nationality", "number_of_passengers"],
        )
        return factory(prefix="passengers", instance=self.object, **form_kwargs)

    def get_disembarkment_formset(self, **form_kwargs):
        factory = self.get_inlineformset_factory(
            Disembarkment,
            ["id", "disembarkment_site", "number_of_passengers"],
        )
        return factory(prefix="disembarkment", instance=self.object, **form_kwargs)


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
        receipt = form.get_receipt(
            base="havneafgifter/base_default.html", request=request
        )
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
            return HavneafgifterResponseNotFound(
                request, f"No form found for ID {self.kwargs.get(self.pk_url_kwarg)}"
            )
        else:
            receipt = form.get_receipt()
        return HttpResponse(
            receipt.pdf,
            content_type="application/pdf",
        )


class WithdrawView(
    LoginRequiredMixin, HavneafgiftView, HandleNotificationMailMixin, UpdateView
):
    http_method_names = ["post"]

    def get_queryset(self):
        return HarborDuesForm.filter_user_permissions(
            HarborDuesForm.objects.filter(status=Status.NEW),
            self.request.user,
            "withdraw_from_review",
        )

    def post(self, request, *args, **kwargs):
        # If we cannot get the specified `HarborDuesForm` object, it is probably
        # because we don't have the required `withdraw` permission.
        try:
            harbor_dues_form = self.get_object()
        except Http404:
            return HavneafgifterResponseForbidden(
                self.request,
                _(
                    "You do not have the required permissions to withdraw "
                    "harbor dues forms from review"
                ),
            )
        # There is no form to fill for "withdraw" actions, so it does not make sense to
        # implement `form_valid`. Instead, we just perform the object update here.
        harbor_dues_form.withdraw_from_review()
        harbor_dues_form.save()
        # The `OnWithdrawMail` does not exist and has not been requested by the customer
        # But if desired, it could be implemented and coupled to the "withdraw" action
        # like this:
        # self.handle_notification_mail(OnWithdrawMail, harbor_dues_form)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("havneafgifter:harbor_dues_form_list")


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
        self.handle_notification_mail(OnApproveReceipt, harbor_dues_form)
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
        self.handle_notification_mail(OnRejectReceipt, harbor_dues_form)
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
        context["count"] = self.get_queryset().count()
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
                "user_can_edit": self.object.has_permission(
                    self.request.user, "change", False
                ),
                "user_can_clone": self.object.has_permission(
                    self.request.user, "add", False
                ),
                "user_can_delete": self.object.has_permission(
                    self.request.user, "delete", False
                ),
            }
        )


class StatisticsView(
    LoginRequiredMixin, ExportMixin, CSPViewMixin, SingleTableMixin, GetFormView
):
    form_class = StatisticsForm
    template_name = "havneafgifter/statistik.html"
    table_class = StatistikTable
    export_name = "statistik"

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
            qs = HarborDuesForm.objects.all()
            shortcut_fields = {
                "municipality": F(
                    "cruisetaxform__disembarkment__disembarkment_site__municipality"
                ),
                "site": F("cruisetaxform__disembarkment__disembarkment_site"),
                "disembarkment": F("cruisetaxform__disembarkment"),
                "number_of_passengers": F(
                    "cruisetaxform__disembarkment__number_of_passengers"
                ),
                "pax_tax": F("cruisetaxform__pax_tax"),
                "port_authority": Coalesce(
                    F("port_of_call__portauthority"),
                    PortAuthority.objects.get(
                        name=settings.APPROVER_NO_PORT_OF_CALL
                    ).pk,
                ),
            }
            filter_fields = {}

            field_value = form.cleaned_data["arrival_gt"]
            if field_value:
                filter_fields["datetime_of_arrival__gt"] = field_value

            field_value = form.cleaned_data["arrival_lt"]
            if field_value:
                # Offset added to catch arrivals ON the date of the last chosen date
                filter_fields["datetime_of_arrival__lt"] = field_value + relativedelta(
                    days=1
                )

            for field in (
                "municipality",
                "vessel_type",
                "port_authority",
                "port_of_call",
                "site",
                "status",
            ):
                field_value = form.cleaned_data[field]
                if field_value:
                    filter_fields[f"{field}__in"] = field_value

            qs = qs.annotate(**shortcut_fields)
            qs = qs.filter(**filter_fields)

            qs = qs.values().distinct()
            qs = qs.annotate(
                disembarkment_tax_sum=Coalesce(
                    Sum(
                        Subquery(
                            CruiseTaxForm.objects.filter(id=OuterRef("pk")).values(
                                "disembarkment_tax"
                            )
                        ),
                    ),
                    Decimal("0.00"),
                ),
                harbour_tax_sum=Coalesce(Sum("harbour_tax"), Decimal("0.00")),
                total_tax=Coalesce(F("disembarkment_tax_sum"), Decimal("0.00"))
                + Coalesce(F("harbour_tax_sum"), Decimal("0.00"))
                + Coalesce(F("pax_tax"), Decimal("0.00")),
            )
            qs = qs.values(
                "municipality",
                "vessel_name",
                "vessel_type",
                "port_of_call",
                "site",
                "number_of_passengers",
                "disembarkment",
                "harbour_tax_sum",
                "pax_tax",
                "total_tax",
                "gross_tonnage",
                "status",
                "datetime_of_arrival",
                "datetime_of_departure",
                "port_authority",
                "id",
            )
            qs = qs.order_by(
                "datetime_of_arrival",
                "id",
                "municipality",
                "vessel_type",
                "port_of_call",
                "site",
                "status",
            )

            items = list(qs)
            form_ids = set(qs.values_list("id", flat=True))

            for item in items:
                datetime_of_arrival = item.pop("datetime_of_arrival")
                if datetime_of_arrival:
                    item["date_of_arrival"] = datetime_of_arrival.date().isoformat()

                datetime_of_departure = item.pop("datetime_of_departure")
                if datetime_of_departure:
                    item["date_of_departure"] = datetime_of_departure.date().isoformat()

                municipality = item.get("municipality")
                if municipality:
                    item["municipality"] = Municipality(municipality).label

                port_of_call = item.get("port_of_call")
                if port_of_call:
                    item["port_of_call"] = Port.objects.get(pk=port_of_call).name

                port_authority = item.get("port_authority")
                if port_authority:
                    item["port_authority"] = PortAuthority.objects.get(
                        pk=port_authority,
                    ).name

                site = item.get("site")
                if site:
                    item["site"] = DisembarkmentSite.objects.get(pk=site).name

                disembarkment = item.get("disembarkment")
                if disembarkment:
                    disembarkment = Disembarkment.objects.get(pk=disembarkment)
                    item["disembarkment_tax"] = disembarkment.get_disembarkment_tax(
                        save=True
                    )

                vessel_type = item.get("vessel_type")
                if vessel_type:
                    item["vessel_type"] = ShipType(vessel_type).label

                status = item.get("status")
                if status:
                    item["status"] = Status(status).label

                site = item.get("site")
                port_of_call = item.get("port_of_call")
                id = item.get("id")
                if (
                    site and port_of_call and site != port_of_call
                ) or id not in form_ids:
                    item["harbour_tax_sum"] = None
                    item["pax_tax"] = None
                    item["total_tax"] = None
                else:
                    form_ids.remove(id)

            return items
        return []


class PassengerStatisticsView(StatisticsView):
    form_class = PassengerStatisticsForm
    template_name = "havneafgifter/passengerstatistics.html"
    table_class = PassengerStatisticsTable
    export_name = "passagerstatistik"

    def dispatch(self, request, *args, **kwargs):
        if request.user.can_view_statistics:
            return super().dispatch(request, *args, **kwargs)
        else:
            return HavneafgifterResponseForbidden(
                self.request,
                _(
                    "You do not have the required permissions "
                    "to view passenger statistics"
                ),
            )

    def get_table_data(self):
        # Return list of items w. nationality, month and count
        form = self.get_form()
        if form.is_valid():
            qs = PassengersByCountry.objects.filter(
                cruise_tax_form__status=Status.APPROVED,
            )
            nationalities = form.cleaned_data["nationality"]
            if nationalities:
                qs = qs.filter(nationality__in=nationalities)

            first_month = form.cleaned_data["first_month"]
            if qs and first_month:
                qs = qs.filter(cruise_tax_form__datetime_of_arrival__gte=first_month)
            elif qs:
                first_month = (
                    qs.exclude(cruise_tax_form__datetime_of_arrival__isnull=True)
                    .order_by("cruise_tax_form__datetime_of_arrival")
                    .first()
                    .cruise_tax_form.datetime_of_arrival
                )
            else:
                return []

            last_month = form.cleaned_data["last_month"]
            if qs and last_month:
                qs = qs.filter(
                    cruise_tax_form__datetime_of_arrival__lt=last_month
                    + relativedelta(months=1)
                )
            elif qs:
                last_month = (
                    qs.exclude(cruise_tax_form__datetime_of_arrival__isnull=True)
                    .order_by("cruise_tax_form__datetime_of_arrival")
                    .last()
                    .cruise_tax_form.datetime_of_arrival
                )
            else:
                return []

            months = self.month_list(first_month, last_month)

            items = []
            for month in months:
                month_filter = {
                    "cruise_tax_form__datetime_of_arrival__month": month.month,
                    "cruise_tax_form__datetime_of_arrival__year": month.year,
                }
                month_qs = qs.filter(**month_filter)
                for (nation,) in set(month_qs.values_list("nationality")):
                    item = {"month": month.strftime("%B, %Y")}
                    item["count"] = month_qs.filter(nationality=nation).aggregate(
                        Sum("number_of_passengers")
                    )["number_of_passengers__sum"]
                    item["nationality"] = self.nationality_dict[nation]
                    items.append(item)
            return items

        return []

    @classmethod
    def month_list(self, start_date, end_date):
        start_month = datetime(start_date.year, start_date.month, 1)
        end_month = datetime(end_date.year, end_date.month, 1)
        ith_month = start_month
        month_list = []
        while ith_month <= end_month:
            month_list.append(ith_month)
            ith_month += relativedelta(months=1)

        return month_list

    nationality_dict = dict(Nationality.choices)


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
            initial["start_datetime"] = new_taxrate_start_datetime(datetime.now())
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


class LandingModalOkView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        request.session["harbor_user_modal"] = True
        return HttpResponse(status=204)
