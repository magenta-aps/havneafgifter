import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from havneafgifter.models import HarborDuesForm


class HarborDuesFormTable(tables.Table):
    id = tables.Column(linkify=("havneafgifter:receipt_detail_html", [tables.A("pk")]))

    class Meta:
        model = HarborDuesForm
        exclude = ("vessel_master", "vessel_owner", "nationality", "harbour_tax")


class StatistikTable(tables.Table):
    orderable = False
    municipality = tables.Column(verbose_name=_("Kommune"))
    vessel_type = tables.Column(verbose_name=_("Skibstype"))
    port_of_call = tables.Column(verbose_name=_("Havn"))
    site = tables.Column(verbose_name=_("Landgangssted"))
    disembarkment_tax_sum = tables.Column(verbose_name=_("Landgangsafgift"))
    harbour_tax_sum = tables.Column(verbose_name=_("Havneafgift"))
    count = tables.Column(verbose_name=_("Antal skibe"))
