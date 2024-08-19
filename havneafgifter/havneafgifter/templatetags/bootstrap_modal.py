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


@register.inclusion_tag(
    "havneafgifter/bootstrap/inform_ship_user_on_save.html",
    takes_context=True,
)
def inform_ship_user_on_save_modal(
    context, form: HarborDuesForm | CruiseTaxForm
) -> dict:
    return {"form": form}


@register.inclusion_tag(
    "havneafgifter/bootstrap/inform_ship_user_on_submit.html",
    takes_context=True,
)
def inform_ship_user_on_submit_modal(
    context, form: HarborDuesForm | CruiseTaxForm
) -> dict:
    return {"form": form}
