from django import template

from havneafgifter.models import CruiseTaxForm, HarborDuesForm, Status

register = template.Library()


@register.inclusion_tag("havneafgifter/bootstrap/status_badge.html")
def bootstrap_status_badge(form: HarborDuesForm | CruiseTaxForm) -> dict:
    mapping = {
        Status.DRAFT: "bg-secondary",
        Status.NEW: "bg-primary",
        Status.APPROVED: "bg-success",
        Status.REJECTED: "bg-danger",
        # Status.DONE: "bg-light",
    }
    return {"form": form, "bg": mapping[form.status]}
