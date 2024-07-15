import django_tables2 as tables

from havneafgifter.models import HarborDuesForm


class HarborDuesFormTable(tables.Table):
    id = tables.Column(linkify=("havneafgifter:receipt_detail_html", [tables.A("pk")]))

    class Meta:
        model = HarborDuesForm


class StatistikTable(tables.Table):
    municipality = tables.Column()
    disembarkment_tax = tables.Column()
    harbour_tax = tables.Column()
