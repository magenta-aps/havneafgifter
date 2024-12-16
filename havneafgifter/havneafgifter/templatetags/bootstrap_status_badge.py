from django import template

from havneafgifter.models import CruiseTaxForm, HarborDuesForm, Status

register = template.Library()


@register.inclusion_tag("havneafgifter/bootstrap/status_badge.html")
def bootstrap_status_badge(form: HarborDuesForm | CruiseTaxForm) -> dict:
    mapping = {
        Status.DRAFT: "badge-draft",
        Status.NEW: "badge-waiting",
        Status.APPROVED: "badge-approved",
        Status.REJECTED: "badge-rejected",
    }
    return {"form": form, "bg": mapping[form.status]}
