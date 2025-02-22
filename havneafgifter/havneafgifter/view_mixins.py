from csp_helpers.mixins import CSPViewMixin
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView
from django_fsm import can_proceed, has_transition_perm

from havneafgifter.mails import (
    NotificationMail,
    OnSendToAgentMail,
    OnSubmitForReviewMail,
    OnSubmitForReviewReceipt,
)
from havneafgifter.models import (
    CruiseTaxForm,
    HarborDuesForm,
    ShipType,
    Status,
    UserType,
)
from havneafgifter.responses import HavneafgifterResponseForbidden


class HavneafgiftView:
    def get_context_data(self, **context):
        return super().get_context_data(
            **{
                **context,
                "version": settings.VERSION,
                "contact_email": settings.CONTACT_EMAIL,
                "landing_modal": HavneafgiftView.landing_modal(self.request),
            }
        )

    def get_redirect_for_form(
        self,
        viewname: str,
        form: HarborDuesForm | CruiseTaxForm,
        **query,
    ):
        return HttpResponseRedirect(
            reverse(viewname, kwargs={"pk": form.pk})
            + (f"?{urlencode(query)}" if query else "")
        )

    @staticmethod
    def landing_modal(request):
        return (
            hasattr(request, "user")
            and hasattr(request, "session")
            and request.user.is_authenticated
            and request.user.user_type == UserType.PORT_AUTHORITY
            and not request.session.get("harbor_user_modal")
        )


class HandleNotificationMailMixin:
    def handle_notification_mail(
        self,
        mail_class: type[NotificationMail],
        form: HarborDuesForm | CruiseTaxForm,
    ):
        mail = mail_class(form, self.request.user)  # type: ignore
        result = mail.send_email()
        messages.add_message(
            self.request,  # type: ignore
            messages.SUCCESS if result.succeeded else messages.ERROR,
            (
                result.mail.success_message
                if result.succeeded
                else result.mail.error_message
            ),
        )


class GetFormView(FormView):
    def get(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data())

    def get_form_kwargs(self):
        kwargs = {
            "initial": self.get_initial(),
            "prefix": self.get_prefix(),
        }
        if self.request.method in ("GET"):
            kwargs.update(
                {
                    "data": self.request.GET,
                    "files": self.request.FILES,
                }
            )
        return kwargs


class HarborDuesFormMixin(
    LoginRequiredMixin,
    CSPViewMixin,
    HandleNotificationMailMixin,
    HavneafgiftView,
):
    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data["user_is_ship"] = self.request.user.user_type == UserType.SHIP
        return context_data

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["status"] = self._get_desired_status()
        return kwargs

    def form_valid(self, form):
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

        if harbor_dues_form.vessel_type == ShipType.CRUISE:
            # `CruiseTaxForm` inherits from `HarborDuesForm`, so we can create
            # a `CruiseTaxForm` based on the fields on `HarborDuesForm`.
            cruise_tax_form = self._create_or_update_cruise_tax_form(harbor_dues_form)
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
            status = form.cleaned_data.get("status")
            if status == Status.NEW:
                harbor_dues_form.submit_for_review()
                harbor_dues_form.save()
                harbor_dues_form.calculate_tax(save=True)
                self.handle_notification_mail(OnSubmitForReviewMail, harbor_dues_form)
                self.handle_notification_mail(
                    OnSubmitForReviewReceipt, harbor_dues_form
                )
            elif status == Status.DRAFT:
                # Send notification to agent if saved by a ship user.
                harbor_dues_form.save()
                harbor_dues_form.calculate_tax(save=True)
                if (
                    self.request.user.user_type == UserType.SHIP
                    and harbor_dues_form.shipping_agent
                ):
                    self.handle_notification_mail(OnSendToAgentMail, harbor_dues_form)

            # Go to detail view to display result.
            return self.get_redirect_for_form(
                "havneafgifter:receipt_detail_html",
                harbor_dues_form,
            )

    def _create_or_update_cruise_tax_form(
        self, harbor_dues_form: HarborDuesForm
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
            return CruiseTaxForm.objects.create(**field_vals)
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
                return CruiseTaxForm.objects.create(
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
                cruise_tax_form.save()
                return cruise_tax_form

    def _get_desired_status(self) -> Status:
        status = self.request.POST.get("status") or self.request.GET.get("status")
        if status is not None:
            try:
                return Status[status]
            except KeyError:
                pass
        return Status.DRAFT


class CacheControlMixin:
    def prevent_response_caching(self, response: HttpResponse) -> HttpResponse:
        # Ensure that when/if users go back to this view from the receipt page,
        # their browser does not show a cached response (which may present them with a
        # seemingly "editable" form that cannot be submitted if the form status is NEW.
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, post-check=0, pre-check=0"
        )
        return response
