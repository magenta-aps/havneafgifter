from django import template

from havneafgifter.forms import ReasonForm
from havneafgifter.models import CruiseTaxForm, HarborDuesForm, Vessel

register = template.Library()


@register.inclusion_tag(
    "havneafgifter/bootstrap/withdraw_form.html",
    takes_context=True,
)
def withdraw_form_modal(context, form: HarborDuesForm | CruiseTaxForm) -> dict:
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
    "havneafgifter/bootstrap/delete_form.html",
)
def delete_form_modal(form: HarborDuesForm | CruiseTaxForm) -> dict:
    return {"form": form}


@register.inclusion_tag(
    "havneafgifter/bootstrap/inform_ship_user_on_save_vessel_change.html",
    takes_context=True,
)
def inform_ship_user_on_save_vessel_change_modal(context, form: Vessel) -> dict:
    return {"form": form}


@register.inclusion_tag(
    "havneafgifter/bootstrap/inform_ship_user_on_save_shipping_agent.html",
    takes_context=True,
)
def inform_ship_user_on_save_shipping_agent_modal(
    context, form: HarborDuesForm | CruiseTaxForm
) -> dict:
    return {"form": form}


@register.inclusion_tag(
    "havneafgifter/bootstrap/inform_ship_user_on_save_no_shipping_agent.html",
    takes_context=True,
)
def inform_ship_user_on_save_no_shipping_agent_modal(
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
