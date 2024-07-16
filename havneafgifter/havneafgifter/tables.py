import django_tables2 as tables

from havneafgifter.models import HarborDuesForm, Municipality


class HarborDuesFormTable(tables.Table):
    id = tables.Column(linkify=("havneafgifter:receipt_detail_html", [tables.A("pk")]))

    class Meta:
        model = HarborDuesForm


class StatistikTable(tables.Table):
    municipality = tables.Column()
    vessel_type = tables.Column()
    port_of_call = tables.Column()
    site = tables.Column()
    disembarkment_tax_sum = tables.Column()
    harbour_tax_sum = tables.Column()
    count = tables.Column()

    # def render_municipality(self):
    #     if self.municipality:
    #         print(self.municipality)

    # def render_municipality(self):
    #     if self.municipality:
    #         return Municipality.objects.get(id=self.municipality).values("name")
