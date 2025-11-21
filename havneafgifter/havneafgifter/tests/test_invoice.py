from datetime import datetime

from django.core.management import call_command
from django.test import TestCase

from havneafgifter.models import (
    CruiseTaxForm,
    Nationality,
    Port,
    PortAuthority,
    ShippingAgent,
    ShipType,
    Status,
)


class InvoiceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        current_timezone = datetime.now().astimezone().tzinfo

        cls.shipping_agent = ShippingAgent.objects.create(
            name="Smith", email="smith@matrix.net"
        )

        cls.port_authority = PortAuthority.objects.create(
            name="Royal Arctic Line A/S", email="ral@ral.dk"
        )
        cls.port = Port.objects.create(
            name="Upernavik", portauthority=cls.port_authority
        )
        cls.form = CruiseTaxForm.objects.create(
            status=Status.DRAFT,
            port_of_call=cls.port,
            nationality=Nationality.DENMARK,
            vessel_name="Naglfar",
            vessel_imo="1234567",
            vessel_owner="Magenta ApS",
            vessel_master="Bent Handberg",
            shipping_agent=cls.shipping_agent,
            datetime_of_arrival=datetime(2024, 5, 1, 12, 0, 0, tzinfo=current_timezone),
            datetime_of_departure=datetime(
                2024, 6, 1, 12, 0, 0, tzinfo=current_timezone
            ),
            gross_tonnage=50000,
            vessel_type=ShipType.CRUISE,
            number_of_passengers=5000,
        )

    def test_invoice(self):
        self.form.submit()
        self.form.invoice()
        self.assertEqual(self.form.status, Status.INVOICED)

    def test_submit(self):
        self.form.submit()
        self.form.save()
        self.assertEqual(self.form.status, Status.NEW)
        call_command("send_invoices")
        form = CruiseTaxForm.objects.get(pk=self.form.pk)
        self.assertEqual(form.status, Status.INVOICED)
