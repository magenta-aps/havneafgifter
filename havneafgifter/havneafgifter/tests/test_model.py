from datetime import date, datetime, timezone
from unittest.mock import ANY, patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from havneafgifter.models import (
    DisembarkmentSite,
    EmailMessage,
    HarborDuesForm,
    Municipality,
    Port,
    PortAuthority,
    PortTaxRate,
    ShippingAgent,
    ShipType,
    TaxRates,
    imo_validator,
)
from havneafgifter.tests.mixins import HarborDuesFormMixin


class ModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Port.objects.create(name="Test1")
        Port.objects.create(name="Test2")
        cls.tax_rates = TaxRates.objects.create(
            pax_tax_rate=0,
            start_datetime=None,
            end_datetime=None,
        )
        cls.tax_rates2 = TaxRates.objects.create(
            pax_tax_rate=0,
            start_datetime=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            end_datetime=None,
        )
        cls.tax_rates.refresh_from_db()
        cls.tax_rates2.refresh_from_db()
        PortTaxRate.objects.create(
            tax_rates=cls.tax_rates,
            port=None,
            vessel_type=None,
            gt_start=0,
            gt_end=None,
            port_tax_rate=70,
        )
        PortTaxRate.objects.create(
            tax_rates=cls.tax_rates,
            port=None,
            vessel_type=ShipType.CRUISE,
            gt_start=0,
            gt_end=30_000,
            port_tax_rate=110,
        )
        PortTaxRate.objects.create(
            tax_rates=cls.tax_rates,
            port=None,
            vessel_type=ShipType.CRUISE,
            gt_start=30_000,
            gt_end=None,
            port_tax_rate=220,
        )
        PortTaxRate.objects.create(
            tax_rates=cls.tax_rates,
            port=Port.objects.get(name="Test2"),
            vessel_type=ShipType.CRUISE,
            gt_start=0,
            gt_end=30_000,
            port_tax_rate=0,
        )
        PortTaxRate.objects.create(
            tax_rates=cls.tax_rates,
            port=Port.objects.get(name="Test2"),
            vessel_type=ShipType.CRUISE,
            gt_start=30_000,
            gt_end=None,
            port_tax_rate=110,
        )

    def test_imo_validator(self):
        with self.assertRaises(ValidationError):
            imo_validator("1234")
        with self.assertRaises(ValidationError):
            imo_validator("abcdefg")
        with self.assertRaises(ValidationError):
            imo_validator("123456A")
        with self.assertRaises(ValidationError):
            imo_validator("9074721")
        try:
            imo_validator("9074729")
        except ValidationError:
            self.fail("Got validation error on correct IMO")

    def test_get_port_tax_rate(self):
        tax_rates = TaxRates.objects.all().first()
        self.assertEqual(
            tax_rates.get_port_tax_rate(
                Port.objects.get(name="Test1"), ShipType.FREIGHTER, 40_000
            ).port_tax_rate,
            70,
        )

        self.assertEqual(
            tax_rates.get_port_tax_rate(
                Port.objects.get(name="Test1"), ShipType.CRUISE, 20_000
            ).port_tax_rate,
            110,
        )

        self.assertEqual(
            tax_rates.get_port_tax_rate(
                Port.objects.get(name="Test1"), ShipType.CRUISE, 40_000
            ).port_tax_rate,
            220,
        )

        self.assertEqual(
            tax_rates.get_port_tax_rate(
                Port.objects.get(name="Test2"), ShipType.CRUISE, 20_000
            ).port_tax_rate,
            0,
        )

        self.assertEqual(
            tax_rates.get_port_tax_rate(
                Port.objects.get(name="Test2"), ShipType.CRUISE, 40_000
            ).port_tax_rate,
            110,
        )

        self.assertEqual(
            tax_rates.get_port_tax_rate(
                Port.objects.get(name="Test2"), ShipType.PASSENGER, 40_000
            ).port_tax_rate,
            70,
        )

    def test_tax_rates_time_update(self):
        self.assertEqual(
            self.tax_rates.end_datetime,
            datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        )


class TestShippingAgent(TestCase):
    def test_str(self):
        name = "Some name"
        instance = ShippingAgent(name=name)
        self.assertEqual(str(instance), name)


class TestPortAuthority(TestCase):
    def test_str(self):
        name = "Some name"
        instance = PortAuthority(name=name)
        self.assertEqual(str(instance), name)


class TestPort(TestCase):
    def test_str_simple(self):
        name = "Some name"
        instance = Port(name=name)
        self.assertEqual(str(instance), name)

    def test_str_complex(self):
        authority_name = "Authority name"
        port_name = "Port name"
        instance = Port(
            name=port_name,
            portauthority=PortAuthority(name=authority_name),
        )
        self.assertEqual(str(instance), f"{port_name} ({authority_name})")


class TestHarborDuesForm(HarborDuesFormMixin, TestCase):
    def test_str(self):
        instance = HarborDuesForm(
            vessel_name="Mary",
            port_of_call=Port(name="Nordhavn"),
            datetime_of_arrival=datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            datetime_of_departure=datetime(2020, 1, 31, 0, 0, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            str(instance),
            "Mary, Nordhavn (2020-01-01 00:00:00+00:00 - 2020-01-31 00:00:00+00:00)",
        )

    def test_send_email(self):
        instance = HarborDuesForm(**self.harbor_dues_form_data)
        with patch.object(EmailMessage, "send") as mock_send:
            msg, status = instance.send_email()
            # Assert the basic email fields are populated
            self.assertEqual(msg.subject, instance.mail_subject)
            self.assertEqual(msg.body, instance.mail_body)
            self.assertEqual(msg.bcc, instance.mail_recipients)
            self.assertEqual(msg.from_email, settings.EMAIL_SENDER)
            # Assert that the receipt is attached as Receipt
            self.assertListEqual(
                msg.attachments,
                [(f"{instance.pk}.pdf", ANY, "application/pdf")],
            )
            pdf_content: bytes = msg.attachments[0][1]
            self.assertIsInstance(pdf_content, bytes)
            self.assertGreater(len(pdf_content), 0)
            # Assert that `HarborDuesForm.send_mail` calls `EmailMessage.send` as
            # expected.
            mock_send.assert_called_once_with(fail_silently=False)

    def test_mail_body(self):
        instance = HarborDuesForm(**self.harbor_dues_form_data)
        instance.date = date(2020, 1, 1)
        self.assertEqual(
            instance.mail_body,
            "On 1. januar 2020, Agent has reported harbor dues, cruise tax, "
            "and environmental and maintenance fees related to the entry of Mary "
            "in Nordhavn",
        )

    @override_settings(EMAIL_ADDRESS_SKATTESTYRELSEN="skattestyrelsen@example.org")
    def test_mail_recipients(self):
        instance = HarborDuesForm(**self.harbor_dues_form_data)
        self.assertListEqual(
            instance.mail_recipients,
            [
                instance.port_of_call.portauthority.email,
                instance.shipping_agent.email,
                settings.EMAIL_ADDRESS_SKATTESTYRELSEN,
            ],
        )

    def test_mail_recipients_excludes_missing_port_authority(self):
        instance = HarborDuesForm(**self.harbor_dues_form_data)
        instance.port_of_call.portauthority = None
        self._assert_mail_recipients_property_logs_message(
            instance,
            "is not linked to a port authority, excluding from mail recipients",
        )

    def test_mail_recipients_excludes_missing_shipping_agent(self):
        instance = HarborDuesForm(**self.harbor_dues_form_data)
        instance.shipping_agent = None
        self._assert_mail_recipients_property_logs_message(
            instance,
            "is not linked to a shipping agent, excluding from mail recipients",
        )

    @override_settings(EMAIL_ADDRESS_SKATTESTYRELSEN=None)
    def test_mail_recipients_excludes_missing_skattestyrelsen_email(self):
        instance = HarborDuesForm(**self.harbor_dues_form_data)
        self._assert_mail_recipients_property_logs_message(
            instance,
            "Skattestyrelsen email not configured, excluding from mail recipients",
        )

    def _assert_mail_recipients_property_logs_message(self, instance, message):
        with self.assertLogs() as logged:
            instance.mail_recipients
            self.assertTrue(
                any(record.message.endswith(message) for record in logged.records)
            )


class TestDisembarkmentSite(TestCase):
    def test_str(self):
        instance = DisembarkmentSite(
            name="Naturen",
            municipality=Municipality.AVANNAATA,
        )
        self.assertEqual(str(instance), "Naturen (Avannaata)")
