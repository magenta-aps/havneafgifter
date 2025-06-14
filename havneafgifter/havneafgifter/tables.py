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
    total_tax = tables.Column(verbose_name=_("Total"))
    operation = tables.TemplateColumn(
        template_name="havneafgifter/bootstrap/open_details.html",
        verbose_name=_("Operation"),
    )

    status = tables.Column()

    class Meta:
        model = HarborDuesForm
        exclude = (
            "no_port_of_call",
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
    vessel_name = tables.Column(verbose_name=_("Skibsnavn"))
    port_of_call = tables.Column(verbose_name=_("Havn"))
    site = tables.Column(verbose_name=_("Landgangssted"))
    port_authority = tables.Column(verbose_name=_("Havnemyndighed"))
    gross_tonnage = tables.Column(verbose_name=_("Bruttoton"), visible=False)
    date_of_arrival = tables.Column(verbose_name=_("Ankomstdato"), visible=False)
    date_of_departure = tables.Column(verbose_name=_("Afsejlingsdato"), visible=False)
    number_of_passengers = tables.Column(verbose_name=_("Antal PAX"), visible=False)
    pax_tax = tables.Column(verbose_name=_("Paxtax"), visible=False)
    disembarkment_tax = tables.Column(verbose_name=_("Miljø- og vedligeholdelsesgebyr"))
    harbour_tax_sum = tables.Column(verbose_name=_("Havneafgift"))
    total_tax = tables.Column(verbose_name=_("Samlet afgift"), visible=False)
    status = tables.Column(verbose_name=_("Status"))
    id = tables.Column(verbose_name=_("Blanket ID"), visible=False)


class PassengerStatisticsTable(tables.Table):
    orderable = True
    nationality = tables.Column(verbose_name=_("Nationalitet"))
    month = tables.Column(verbose_name=_("Måned"))
    count = tables.Column(verbose_name=_("Antal afstigninger"))


class TaxRateTableButtonColumn(tables.Column):
    """
    Allows TaxRateTable to show a clickable button, instead of just a clickable ID
    """

    def render(self, value, record, bound_column, **kwargs):
        url = reverse_lazy("havneafgifter:tax_rate_details", args=[record.pk])
        return format_html(f'<a href="{url}" class="btn btn-primary">{_("Show")}</a>')


class TaxRateTable(tables.Table):
    id = TaxRateTableButtonColumn()
    end_datetime = tables.Column(default="∞")

    class Meta:
        model = TaxRates
        exclude = ("pax_tax_rate",)
        sequence = ("start_datetime", "end_datetime", "id")
