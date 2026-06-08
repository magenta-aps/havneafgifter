import django_tables2 as tables
from django.urls import reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django_filters import (
    CharFilter,
    ChoiceFilter,
    DateTimeFilter,
    FilterSet,
    ModelChoiceFilter,
    NumberFilter,
)

from havneafgifter.forms import HTML5DateWidget
from havneafgifter.models import HarborDuesForm, Port, Status, TaxRates, User, Vessel


class HarborDuesFormFilter(FilterSet):

    class Meta:
        model = HarborDuesForm
        fields = ["id", "status", "vessel_name", "port_of_call"]

    id = NumberFilter(field_name="id")
    status = ChoiceFilter(choices=Status.choices, label=_("Status"))
    vessel_name = CharFilter(lookup_expr="icontains", label=_("Vessel name"))
    port_of_call = ModelChoiceFilter(
        field_name="port_of_call", queryset=Port.objects.all()
    )
    arrival_after = DateTimeFilter(
        field_name="datetime_of_arrival",
        lookup_expr="gte",
        label=_("Arrival after"),
        widget=HTML5DateWidget(),
    )
    arrival_before = DateTimeFilter(
        field_name="datetime_of_arrival",
        lookup_expr="lte",
        label=_("Arrival before"),
        widget=HTML5DateWidget(),
    )
    departure_after = DateTimeFilter(
        field_name="datetime_of_departure",
        lookup_expr="gte",
        label=_("Departure after"),
        widget=HTML5DateWidget(),
    )
    departure_before = DateTimeFilter(
        field_name="datetime_of_departure",
        lookup_expr="lte",
        label=_("Departure before"),
        widget=HTML5DateWidget(),
    )


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
        attrs = {"class": "table table-light"}

    def render_datetime_of_arrival(self, value):
        return value.strftime("%Y-%m-%d %H:%M") if value else "-"

    def render_datetime_of_departure(self, value):
        return value.strftime("%Y-%m-%d %H:%M") if value else "-"

    def render_status(self, record):
        cls_map = {
            Status.DRAFT: "badge-draft",
            Status.NEW: "badge-waiting",
            Status.APPROVED: "badge-approved",
            Status.REJECTED: "badge-rejected",
            Status.INVOICED: "badge-invoiced",
            Status.MISSING_CVR: "badge-missing-cvr",
        }
        cls = cls_map[record.status]
        return format_html(
            """<span class="badge rounded-pill {cls}">{status}</span>""",
            cls=cls,
            status=record.get_status_display(),
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
        return format_html(
            '<a href="{url}" class="btn btn-primary">{label}</a>',
            url=url,
            label=_("Show"),
        )


class TaxRateTable(tables.Table):
    id = TaxRateTableButtonColumn()
    end_datetime = tables.Column(default="∞")

    class Meta:
        model = TaxRates
        exclude = ("pax_tax_rate",)
        sequence = ("start_datetime", "end_datetime", "id")


class VesselExportTable(tables.Table):
    class Meta:
        model = Vessel

    cvr = tables.Column(accessor="user__cvr")
    ean = tables.Column(accessor="user__ean")
    gln = tables.Column(accessor="user__gln")


class UserExportTable(tables.Table):
    class Meta:
        model = User
        exclude = ("password",)
