import django_filters
import django_tables2 as tables
from django.urls import reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from havneafgifter.models import HarborDuesForm, Municipality, TaxRates


class HarborDuesFormFilter(django_filters.FilterSet):
    class Meta:
        model = HarborDuesForm
        fields = {"status": ["exact"]}

    municipality = django_filters.ChoiceFilter(
        label=_("Municipality"),
        field_name="cruisetaxform__disembarkment__disembarkment_site__municipality",
        choices=Municipality,
    )


class HarborDuesFormTable(tables.Table):
    view = tables.TemplateColumn(
        template_name="havneafgifter/bootstrap/open_details.html"
    )

    class Meta:
        model = HarborDuesForm
        exclude = (
            "vessel_master",
            "vessel_owner",
            "vessel_type",
            "nationality",
            "harbour_tax",
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
