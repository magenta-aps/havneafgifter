import django_filters
import django_tables2 as tables
from django.urls import reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from havneafgifter.models import HarborDuesForm, TaxRates


class HarborDuesFormFilter(django_filters.FilterSet):
    class Meta:
        model = HarborDuesForm
        fields = {"status": ["exact"]}


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


class ButtonColumn(tables.Column):
    def render(self, value, record, bound_column, **kwargs):
        url = reverse_lazy("havneafgifter:tax_rate_details", args=[record.pk])
        return format_html('<a href="{}" class="btn btn-primary">Show</a>', url)

    # TODO: Make button text translateable


class TaxRateTable(tables.Table):
    # id = tables.Column(linkify=("havneafgifter:tax_rate_details", [tables.A("pk")]))
    id = ButtonColumn()

    class Meta:
        model = TaxRates
        exclude = ("pax_tax_rate",)
