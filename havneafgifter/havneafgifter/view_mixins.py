from csp_helpers.mixins import CSPViewMixin
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView

from havneafgifter.forms import HarborDuesFormForm
from havneafgifter.models import CruiseTaxForm, HarborDuesForm, ShipType, Status

# from havneafgifter.views import HavneAfgiftView


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
    _SendEmailMixin,  # HavneafgiftView
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

    def form_valid(self, form):
        harbor_dues_form = form.save(commit=False)
        if harbor_dues_form.vessel_type == ShipType.CRUISE:
            # `CruiseTaxForm` inherits from `HarborDuesForm`, so we can create
            # a `CruiseTaxForm` based on the fields on `HarborDuesForm`.
            cruise_tax_form, created = CruiseTaxForm.objects.update_or_create(
                **{
                    k: v
                    for k, v in harbor_dues_form.__dict__.items()
                    if not k.startswith("_")  # skip `_state`, etc.
                }
            )
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
            if harbor_dues_form.status != Status.DRAFT:
                # Send email to relevant recipients
                self._send_email(harbor_dues_form, self.request)
            # Go to detail view to display result.
            return self.get_redirect_for_form(
                "havneafgifter:receipt_detail_html",
                harbor_dues_form,
            )
