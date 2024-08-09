from django import template

from havneafgifter.forms import ReasonForm
from havneafgifter.models import CruiseTaxForm, HarborDuesForm

register = template.Library()


@register.inclusion_tag(
    "havneafgifter/bootstrap/approve_form.html",
    takes_context=True,
)
def approve_form_modal(context, form: HarborDuesForm | CruiseTaxForm) -> dict:
    return {"form": form}


@register.inclusion_tag(
    "havneafgifter/bootstrap/reject_form.html",
    takes_context=True,
)
def reject_form_modal(context, form: HarborDuesForm | CruiseTaxForm) -> dict:
    return {
        "form": form,
        "reason_form": ReasonForm(),
        # required to render `{{ request.csp_nonce }}`
        "request": context.get("request"),
    }
