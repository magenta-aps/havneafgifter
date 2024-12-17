import django_filters
import django_tables2 as tables
from django.urls import reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from havneafgifter.models import HarborDuesForm, Status, TaxRates


class HarborDuesFormFilter(django_filters.FilterSet):
    class Meta:
        model = HarborDuesForm
        fields = {"status": ["exact"]}


class HarborDuesFormTable(tables.Table):
    operation = tables.TemplateColumn(
        template_name="havneafgifter/bootstrap/open_details.html",
        verbose_name=_("Operation"),
    )

    status = tables.Column()

    class Meta:
        model = HarborDuesForm
        exclude = (
            "vessel_master",
            "vessel_owner",
            "vessel_type",
            "nationality",
            "harbour_tax",
            "pdf",
        )

    def render_status(self, record):
        cls_map = {
            Status.DRAFT: "badge-draft",
            Status.NEW: "badge-waiting",
            Status.APPROVED: "badge-approved",
            Status.REJECTED: "badge-rejected",
        }
        cls = cls_map[record.status]
        return format_html(
            f"""<span class="badge rounded-pill {cls}">{
                record.get_status_display()
            }</span>"""
        )


class StatistikTable(tables.Table):
    orderable = False
    municipality = tables.Column(verbose_name=_("Kommune"))
    vessel_type = tables.Column(verbose_name=_("Skibstype"))
    port_of_call = tables.Column(verbose_name=_("Havn"))
    site = tables.Column(verbose_name=_("Landgangssted"))
    disembarkment_tax_sum = tables.Column(verbose_name=_("Landgangsafgift"))
    harbour_tax_sum = tables.Column(verbose_name=_("Havneafgift"))
    count = tables.Column(verbose_name=_("Antal skibe"))
    status = tables.Column(verbose_name=_("Status"))


class TaxRateTableButtonColumn(tables.Column):
    """
    Allows TaxRateTable to show a clickable button, instead of just a clickable ID
    """

    def render(self, value, record, bound_column, **kwargs):
        url = reverse_lazy("havneafgifter:tax_rate_details", args=[record.pk])
        return format_html('<a href="{}" class="btn btn-primary">Show</a>', url)


class TaxRateTable(tables.Table):
    id = TaxRateTableButtonColumn()
    end_datetime = tables.Column(default="∞")

    class Meta:
        model = TaxRates
        exclude = ("pax_tax_rate",)
