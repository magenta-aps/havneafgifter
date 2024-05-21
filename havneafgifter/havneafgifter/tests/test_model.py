from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import ANY, patch

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import translation
from unittest_parametrize import ParametrizedTestCase, parametrize

from havneafgifter.models import (
    DisembarkmentSite,
    EmailMessage,
    HarborDuesForm,
    MailRecipientList,
    Municipality,
    Port,
    PortAuthority,
    PortTaxRate,
    ShippingAgent,
    ShipType,
    TaxRates,
    imo_validator,
)
from havneafgifter.receipts import CruiseTaxFormReceipt, HarborDuesFormReceipt
from havneafgifter.tests.mixins import HarborDuesFormMixin


class ModelTest(ParametrizedTestCase, HarborDuesFormMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.port1 = Port.objects.create(name="Test1")
        cls.port2 = Port.objects.create(name="Test2")
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

    @parametrize(
        "vessel_type,expected_tax_per_gross_ton",
        [
            (ShipType.FISHER, Decimal("70")),
            (ShipType.FREIGHTER, Decimal("70")),
            (ShipType.PASSENGER, Decimal("70")),
            (ShipType.OTHER, Decimal("70")),
            (ShipType.CRUISE, Decimal("110")),
        ],
    )
    def test_tax_per_gross_ton(
        self, vessel_type: ShipType, expected_tax_per_gross_ton: Decimal
    ) -> None:
        """The `tax_per_gross_ton` returns the correct value for each vessel type."""
        if vessel_type is ShipType.CRUISE:
            instance = self.cruise_tax_form
        else:
            instance = self.harbor_dues_form
        instance.vessel_type = vessel_type
        self.assertEqual(instance.tax_per_gross_ton, expected_tax_per_gross_ton)


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


class TestHarborDuesForm(ParametrizedTestCase, HarborDuesFormMixin, TestCase):
    maxDiff = None

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

    def test_duration_in_days(self):
        self.assertEqual(self.harbor_dues_form.duration_in_days, 31)

    def test_duration_in_weeks(self):
        self.assertEqual(self.harbor_dues_form.duration_in_weeks, 5)

    def test_calculate_tax(self):
        self.harbor_dues_form.calculate_tax(save=True)
        self.assertIsNotNone(self.harbor_dues_form.harbour_tax)

    def test_get_receipt(self):
        self.assertIsInstance(
            self.harbor_dues_form.get_receipt(), HarborDuesFormReceipt
        )

    def test_send_email(self):
        instance = HarborDuesForm(**self.harbor_dues_form_data)
        instance.save()
        with patch.object(EmailMessage, "send") as mock_send:
            msg, status = instance.send_email()
            # Assert the basic email fields are populated
            self.assertEqual(msg.subject, instance.mail_subject)
            self.assertEqual(msg.body, instance.mail_body)
            self.assertEqual(msg.bcc, instance.mail_recipients)
            self.assertEqual(msg.from_email, settings.EMAIL_SENDER)
            # Assert that the receipt is attached as PDF, using the correct filename
            self.assertListEqual(
                msg.attachments,
                [(f"{instance.form_id}.pdf", ANY, "application/pdf")],
            )
            pdf_content: bytes = msg.attachments[0][1]
            self.assertIsInstance(pdf_content, bytes)
            self.assertGreater(len(pdf_content), 0)
            # Assert that `HarborDuesForm.send_mail` calls `EmailMessage.send` as
            # expected.
            mock_send.assert_called_once_with(fail_silently=False)

    @parametrize(
        "vessel_type,expected_text_1,expected_text_2,expected_text_3",
        [
            (
                ShipType.CRUISE,
                # English
                "Agent has Jan. 1, 2020 reported port taxes, cruise passenger taxes, "
                "as well as environmental and maintenance fees in relation to a ship's "
                "call at a Greenlandic port. See further details in the attached "
                "overview.",
                # Greenlandic
                "Umiarsuit takornariartaatit angisuut umiarsualivimmiinnerannut "
                "akitsuummik aamma avatangiisinut iluarsaassinermillu akiliummik "
                "Agent Jan. 1, 2020, umiarsuup Kalaallit Nunaanni "
                "umiarsualivimmut tulanneranut atatillugu nalunaaruteqarput. "
                "Paasissutissat ilaat ilanngussami takusinnaavatit.",
                # Danish
                "Agent har 1. januar 2020 indberettet havneafgift, "
                "krydstogtpassagerafgift samt miljø- og vedligeholdelsesgebyr i "
                "forbindelse med et skibs anløb i en grønlandsk havn. Se "
                "yderligere detaljer i vedhæftede oversigt.",
            ),
            (
                ShipType.OTHER,
                # English
                "Agent has Jan. 1, 2020 reported port taxes due to a ship's call at a "
                "Greenlandic port. See further details in the attached overview.",
                # Greenlandic
                "Agent Jan. 1, 2020 umiarsuup Kalaallit Nunaanni umiarsualivimmut "
                "tulanneranut atatillugu nalunaaruteqarput. Paasissutissat ilaat "
                "ilanngussami takusinnaavatit.",
                # Danish
                "Agent har 1. januar 2020 indberettet havneafgift i forbindelse med et "
                "skibs anløb i en grønlandsk havn. Se yderligere detaljer i vedhæftede "
                "oversigt.",
            ),
        ],
    )
    def test_mail_body(
        self, vessel_type, expected_text_1, expected_text_2, expected_text_3
    ):
        # Verify contents of mail body.
        # 1. The mail body must consist of the same text repeated in English,
        # Greenlandic, and Danish (in that order.)
        # 2. The text varies, depending on whether the vessel is a cruise ship or not.
        instance = HarborDuesForm(**self.harbor_dues_form_data)
        instance.date = date(2020, 1, 1)
        instance.vessel_type = vessel_type
        self.assertEqual(
            instance.mail_body,
            "\n\n".join((expected_text_1, expected_text_2, expected_text_3)),
        )

    @translation.override("da")
    def test_mail_subject(self):
        # Verify contents of mail subject, and verify that mail subject is always
        # rendered in English, as we do not know the which language(s) the
        # recipient(s) can read.
        instance = HarborDuesForm(**self.harbor_dues_form_data)
        instance.date = date(2020, 1, 1)
        instance.save()
        self.assertEqual(instance.mail_subject, f"{instance.form_id}")


class TestCruiseTaxForm(HarborDuesFormMixin, TestCase):
    def test_calculate_tax(self):
        self.cruise_tax_form.calculate_tax(save=True)
        self.assertIsNotNone(self.cruise_tax_form.harbour_tax)
        self.assertIsNotNone(self.cruise_tax_form.pax_tax)
        self.assertIsNotNone(self.cruise_tax_form.disembarkment_tax)

    def test_total_tax(self):
        self.assertEqual(self.cruise_tax_form.total_tax, 0)
        # Calculate the three different sub-totals, and compare their sum to `total_tax`
        harbour_tax = self.cruise_tax_form.calculate_harbour_tax(save=False)[
            "harbour_tax"
        ]
        passenger_tax = self.cruise_tax_form.calculate_passenger_tax()["passenger_tax"]
        disembarkment_tax = self.cruise_tax_form.calculate_disembarkment_tax(
            save=False
        )["disembarkment_tax"]
        self.assertEqual(
            self.cruise_tax_form.total_tax,
            harbour_tax + passenger_tax + disembarkment_tax,
        )

    def test_get_receipt(self):
        self.assertIsInstance(self.cruise_tax_form.get_receipt(), CruiseTaxFormReceipt)


class TestDisembarkmentSite(TestCase):
    def test_str(self):
        instance = DisembarkmentSite(
            name="Naturen",
            municipality=Municipality.AVANNAATA,
        )
        self.assertEqual(str(instance), "Naturen (Avannaata)")


class TestMailRecipientList(HarborDuesFormMixin, TestCase):
    @override_settings(EMAIL_ADDRESS_SKATTESTYRELSEN="skattestyrelsen@example.org")
    def test_mail_recipients(self):
        instance = self._get_instance()
        self.assertListEqual(
            instance.recipient_emails,
            [
                instance.form.port_of_call.portauthority.email,
                instance.form.shipping_agent.email,
                settings.EMAIL_ADDRESS_SKATTESTYRELSEN,
            ],
        )

    def test_mail_recipients_excludes_missing_port_authority(self):
        def clear_port_authority(form):
            form.port_of_call.portauthority = None
            return form

        self._assert_mail_recipients_property_logs_message(
            "is not linked to a port authority, excluding from mail recipients",
            clear_port_authority,
        )

    def test_mail_recipients_excludes_missing_shipping_agent(self):
        def clear_shipping_agent(form):
            form.shipping_agent = None
            return form

        self._assert_mail_recipients_property_logs_message(
            "is not linked to a shipping agent, excluding from mail recipients",
            clear_shipping_agent,
        )

    @override_settings(EMAIL_ADDRESS_SKATTESTYRELSEN=None)
    def test_mail_recipients_excludes_missing_skattestyrelsen_email(self):
        self._assert_mail_recipients_property_logs_message(
            "Skattestyrelsen email not configured, excluding from mail recipients",
        )

    def _get_instance(self, modifier=None):
        form = HarborDuesForm(**self.harbor_dues_form_data)
        if modifier:
            form = modifier(form)
        return MailRecipientList(form)

    def _assert_mail_recipients_property_logs_message(self, message, modifier=None):
        with self.assertLogs() as logged:
            self._get_instance(modifier=modifier)
            self.assertTrue(
                any(record.message.endswith(message) for record in logged.records)
            )
