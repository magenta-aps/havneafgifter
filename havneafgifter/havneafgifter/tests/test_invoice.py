from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from prisme.client import Prisme
from prisme.exceptions import PrismeException

from havneafgifter.clients.prisme import (
    HavneafgiftInvoiceRequest,
    InvoiceCustomTableResponse,
    PrismeClient,
)
from havneafgifter.models import (
    CruiseTaxForm,
    Disembarkment,
    DisembarkmentSite,
    DisembarkmentTaxRate,
    Nationality,
    Port,
    PortAuthority,
    PortTaxRate,
    ShippingAgent,
    ShipType,
    Status,
    TaxRates,
)


class InvoiceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        current_timezone = datetime.now().astimezone().tzinfo

        cls.shipping_agent = ShippingAgent.objects.create(
            name="Smith",
            email="smith@matrix.net",
            cvr=12345678,
        )

        cls.port_authority = PortAuthority.objects.create(
            name="Royal Arctic Line A/S", email="ral@ral.dk"
        )
        cls.port = Port.objects.create(
            name="Upernavik", portauthority=cls.port_authority, prisme_code=1234
        )
        cls.site = DisembarkmentSite.objects.create(
            name="Hans Ø",
            municipality=960,
            prisme_code=10500,
        )
        cls.taxrates = TaxRates.objects.create(
            start_datetime=None, end_datetime=None, pax_tax_rate=10
        )
        cls.port_tax_rate = PortTaxRate.objects.create(
            tax_rates=cls.taxrates,
            port=cls.port,
            gt_start=0,
            gt_end=2000000,
            port_tax_rate=10,
        )
        cls.disembarkment_tax_rate = DisembarkmentTaxRate.objects.create(
            tax_rates=cls.taxrates,
            disembarkment_site=cls.site,
            municipality=960,
            disembarkment_tax_rate=20,
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
        cls.disembarkment = Disembarkment.objects.create(
            cruise_tax_form=cls.form,
            number_of_passengers=1000,
            disembarkment_site=cls.site,
        )

    @override_settings(PRISME={**settings.PRISME, "mock": True})
    def test_invoice(self):
        self.form.submit()
        self.form.invoice()
        self.assertEqual(self.form.status, Status.INVOICED)

    @override_settings(PRISME={**settings.PRISME, "mock": True})
    def test_submit(self):
        PrismeClient.instance = None
        self.form.submit()
        self.form.save()
        self.assertEqual(self.form.status, Status.NEW)
        call_command("send_invoices")
        form = CruiseTaxForm.objects.get(pk=self.form.pk)
        self.assertEqual(form.status, Status.INVOICED)

    @override_settings(PRISME={**settings.PRISME, "override_due_date": "2026-05-11"})
    def test_override_due_date(self):
        self.assertEqual(self.form.invoice_due_date, date(2026, 5, 11))

    @override_settings(
        PRISME={
            **settings.PRISME,
            "department_recid": "1000",
            "type_account": {
                "cruise_gte_30k": "1111",
                "landing_tax": "2222",
                "passenger_tax": "3333",
            },
        }
    )
    def test_invoice_lines(self):
        lines = self.form.invoice_lines
        self.assertEqual(len(lines), 3)

        harbor_tax_line = lines[0].dict
        self.assertEqual(harbor_tax_line["Description"], "Harbour tax")
        self.assertEqual(harbor_tax_line["Quantity"], 1)
        self.assertEqual(harbor_tax_line["UnitPrice"], "15500000.00")
        self.assertEqual(harbor_tax_line["AmountCur"], "15500000.00")
        self.assertEqual(
            harbor_tax_line["InvoiceTxt"],
            "Upernavik, 2024.05.01 12:00 - 2024.06.01 12:00",
        )
        self.assertEqual(
            harbor_tax_line["ledgerDimensionSegments"],
            {
                "ledgerDimensionSegment": [
                    {"Name": "Afdeling", "Value": "1000"},
                    {"Name": "Finanslov", "Value": 0},
                    {"Name": "Formaal", "Value": "0000000000"},
                    {
                        "Name": "ArtsKontoplan",
                        "Value": "000001111",
                    },
                    {"Name": "Sted", "Value": "001234"},
                ]
            },
        )

        passenger_tax_line = lines[1].dict
        self.assertEqual(passenger_tax_line["Description"], "Passenger tax")
        self.assertEqual(passenger_tax_line["Quantity"], 5000)
        self.assertEqual(passenger_tax_line["UnitPrice"], "10.00")
        self.assertEqual(passenger_tax_line["AmountCur"], "50000.00")
        self.assertEqual(passenger_tax_line["InvoiceTxt"], "5000 passengers")

        disembarkment_tax_line = lines[2].dict
        self.assertEqual(disembarkment_tax_line["Description"], "Disembarkment tax")
        self.assertEqual(disembarkment_tax_line["Quantity"], 1000)
        self.assertEqual(disembarkment_tax_line["UnitPrice"], "20.00")
        self.assertEqual(disembarkment_tax_line["AmountCur"], "20000.00")
        self.assertEqual(
            disembarkment_tax_line["InvoiceTxt"],
            "Hans Ø, 2024.05.01 12:00, 1000 passengers",
        )
        self.assertEqual(
            disembarkment_tax_line["ledgerDimensionSegments"],
            {
                "ledgerDimensionSegment": [
                    {"Name": "Afdeling", "Value": "1000"},
                    {"Name": "Finanslov", "Value": 0},
                    {"Name": "Formaal", "Value": "0000000000"},
                    {
                        "Name": "ArtsKontoplan",
                        "Value": "000002222",
                    },
                    {"Name": "Sted", "Value": "010500"},
                ]
            },
        )

    @override_settings(PRISME={**settings.PRISME, "mock": False})
    @patch.object(Prisme, "process_service")
    def test_send_invoice(self, mock_process_service):
        mock_return = MagicMock()
        mock_return.rec_id = 1
        mock_return.afgift_id = 1
        mock_return.invoice_id = 1
        mock_process_service.side_effect = [
            PrismeException(250, "Debitorkonto findes ikke", {}),
            mock_return,
            mock_return,
        ]
        self.form.submit()
        self.form.send_invoice()
        mock_process_service.assert_called()
        invoice_request = mock_process_service.call_args[0][0]
        self.assertIsInstance(invoice_request, HavneafgiftInvoiceRequest)
        data = invoice_request.dict
        self.assertEqual(data["HarborTaxIdFUJ"], self.form.pk)
        self.assertEqual(len(invoice_request.lines), 3)
        self.assertEqual(
            sum([line.quantity * line.unit_price for line in invoice_request.lines]),
            Decimal("15570000.00"),
        )

    @override_settings(PRISME={**settings.PRISME, "mock": False})
    @patch.object(Prisme, "process_service")
    def test_send_invoice_other_exception(self, mock_process_service):
        mock_process_service.side_effect = (
            PrismeException(250, "Prisme kan bare ikke lide dig i dag", {}),
        )
        self.form.submit()
        self.form.send_invoice()
        mock_process_service.assert_called()
        self.assertEqual(self.form.status, Status.NEW)

    def test_custtable_response(self):
        response = InvoiceCustomTableResponse(
            None,
            """
            <CustTable><AccountNum>1234</AccountNum></CustTable>
            """,
        )
        self.assertEqual(response.account_num, 1234)

    def test_custtable_response_none(self):
        response = InvoiceCustomTableResponse(None, None)
        self.assertFalse(hasattr(response, "account_num"))
