from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import ANY, patch

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management import call_command
from django.db import IntegrityError
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
    Status,
    TaxRates,
    User,
    UserType,
    imo_validator,
    imo_validator_bool,
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
        self.assertFalse(imo_validator_bool("1234"))
        self.assertFalse(imo_validator_bool("abcdefg"))
        self.assertFalse(imo_validator_bool("123456A"))
        self.assertFalse(imo_validator_bool("9074721"))
        self.assertTrue(imo_validator_bool("9074729"))

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


class TestUserType(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("create_groups", verbosity=1)

        cls.shipping_agent = ShippingAgent.objects.create(
            name="Smith", email="smith@matrix.net"
        )
        cls.port_authority = PortAuthority.objects.create(
            name="Royal Arctic Line A/S", email="ral@ral.dk"
        )
        cls.port = Port.objects.create(
            name="Upernavik", portauthority=cls.port_authority
        )

        cls.superuser_user = User.objects.create(
            username="superuser_user", is_superuser=True
        )
        cls.staff_user = User.objects.create(username="staff_user", is_staff=True)
        cls.agent_user = User.objects.create(
            username="agent_user", shipping_agent=cls.shipping_agent
        )
        cls.agent_user.groups.add(Group.objects.get(name="Shipping"))

        cls.port_manager_user = User.objects.create(
            username="manager", port_authority=cls.port_authority
        )
        cls.port_manager_user.groups.add(Group.objects.get(name="PortAuthority"))

        cls.tax_user = User.objects.create(username="skattefar")
        cls.tax_user.groups.add(Group.objects.get(name="TaxAuthority"))

    def test_admin(self):
        user = self.staff_user
        self.assertEqual(user.user_type, UserType.ADMIN)

    def test_superuser(self):
        user = self.superuser_user
        self.assertEqual(user.user_type, UserType.SUPERUSER)

    def test_port_authority(self):
        user = self.port_manager_user
        self.assertEqual(user.user_type, UserType.PORT_AUTHORITY)

    def test_shipping_agent(self):
        user = self.agent_user
        self.assertEqual(user.user_type, UserType.SHIPPING_AGENT)

    def test_tax_authority(self):
        user = self.tax_user
        self.assertEqual(user.user_type, UserType.TAX_AUTHORITY)

    def test_ship(self):
        user = self.agent_user
        self.assertEqual(user.user_type, UserType.SHIPPING_AGENT)


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

    @parametrize(
        "status,field,required",
        [
            (Status.NEW, "port_of_call", True),
            (Status.DRAFT, "port_of_call", False),
            (Status.DONE, "port_of_call", True),
            (Status.NEW, "gross_tonnage", True),
            (Status.DRAFT, "gross_tonnage", False),
            (Status.DONE, "gross_tonnage", True),
            (Status.DONE, "datetime_of_arrival", True),
            (Status.DRAFT, "datetime_of_arrival", False),
            (Status.DONE, "datetime_of_arrival", True),
            (Status.NEW, "datetime_of_departure", True),
            (Status.DRAFT, "datetime_of_departure", False),
            (Status.DONE, "datetime_of_departure", True),
        ],
    )
    def test_fields_only_nullable_for_drafts(self, status, field, required):
        instance = HarborDuesForm(status=status, vessel_type=ShipType.FISHER)
        setattr(instance, field, None)
        if required:
            with self.assertRaises(IntegrityError):
                instance.save()
        else:
            instance.save()

    @parametrize(
        "vessel_type,field,required",
        [
            (ShipType.FISHER, "port_of_call", True),
            (ShipType.CRUISE, "port_of_call", False),
            (ShipType.FISHER, "gross_tonnage", True),
            (ShipType.CRUISE, "gross_tonnage", False),
            (ShipType.FISHER, "datetime_of_arrival", True),
            (ShipType.CRUISE, "datetime_of_arrival", False),
            (ShipType.FISHER, "datetime_of_departure", True),
            (ShipType.CRUISE, "datetime_of_departure", False),
        ],
    )
    def test_fields_only_nullable_for_cruise_ships(self, vessel_type, field, required):
        instance = HarborDuesForm(vessel_type=vessel_type, status="done")
        setattr(instance, field, None)
        if required:
            with self.assertRaises(IntegrityError):
                instance.save()
        else:
            instance.save()

    @parametrize(
        "arrival,departure,should_fail",
        [
            (
                None,
                None,
                False,
            ),
            (
                datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2020, 1, 31, 0, 0, 0, tzinfo=timezone.utc),
                False,
            ),
            (
                datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                None,
                True,
            ),
            (
                None,
                datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                True,
            ),
        ],
    )
    def test_datetime_of_arrival_and_departure_constraints(
        self, arrival, departure, should_fail
    ):
        instance = HarborDuesForm(
            vessel_type=ShipType.CRUISE,
            datetime_of_arrival=arrival,
            datetime_of_departure=departure,
            status="done",
        )
        if should_fail:
            with self.assertRaises(IntegrityError):
                instance.save()
        else:
            instance.save()

    @parametrize(
        "port_of_call,expected_str",
        [
            (
                Port(name="Nordhavn"),
                "Mary, Nordhavn "
                "(2020-01-01 00:00:00+00:00 - 2020-01-31 00:00:00+00:00)",
            ),
            (
                None,
                "Mary, no port of call "
                "(2020-01-01 00:00:00+00:00 - 2020-01-31 00:00:00+00:00)",
            ),
        ],
    )
    def test_str(self, port_of_call, expected_str):
        instance = HarborDuesForm(
            vessel_name="Mary",
            port_of_call=port_of_call,
            datetime_of_arrival=datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            datetime_of_departure=datetime(2020, 1, 31, 0, 0, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(str(instance), expected_str)

    @parametrize(
        "has_datetime_data,expected_duration_in_days",
        [
            (True, 31),
            (False, None),
        ],
    )
    def test_duration_in_days(self, has_datetime_data, expected_duration_in_days):
        if has_datetime_data is False:
            self.harbor_dues_form.datetime_of_arrival = None
            self.harbor_dues_form.datetime_of_departure = None
        self.assertEqual(
            self.harbor_dues_form.duration_in_days, expected_duration_in_days
        )

    @parametrize(
        "has_datetime_data,expected_duration_in_days",
        [
            (True, 5),
            (False, None),
        ],
    )
    def test_duration_in_weeks(self, has_datetime_data, expected_duration_in_days):
        if has_datetime_data is False:
            self.harbor_dues_form.datetime_of_arrival = None
            self.harbor_dues_form.datetime_of_departure = None
        self.assertEqual(
            self.harbor_dues_form.duration_in_weeks, expected_duration_in_days
        )

    def test_has_port_of_call(self):
        self.assertTrue(self.harbor_dues_form.has_port_of_call)

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
            # Assert that the generated PDF is also saved locally
            instance = HarborDuesForm.objects.get(pk=instance.pk)  # refresh from DB
            self.assertIsInstance(instance.pdf, File)
            self.assertEqual(instance.pdf.name, instance.get_pdf_filename())

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
        self.assertEqual(
            instance.mail_subject, f"Talippoq: {instance.pk:05} ({instance.date})"
        )

    @parametrize(
        "action,username,expected_result",
        [
            # 1. "submit_for_review"
            #   Ship users can submit for review
            ("submit_for_review", "9074729", True),
            #   Shipping agents can submit for review
            ("submit_for_review", "shipping_agent", True),
            #   Port authority users cannot submit for review
            ("submit_for_review", "port_auth", False),
            # 2. "approve"
            #   Ship users cannot approve
            ("approve", "9074729", False),
            #   Shipping agents cannot approve
            ("approve", "shipping_agent", False),
            #   Port authority users can approve
            ("approve", "port_auth", True),
            # 3. "reject"
            #   Ship users cannot reject
            ("reject", "9074729", False),
            #   Shipping agents cannot reject
            ("reject", "shipping_agent", False),
            #   Port authority users can reject
            ("reject", "port_auth", True),
        ],
    )
    def test_transition_permissions(self, action, username, expected_result):
        # Arrange
        user = User.objects.get(username=username)
        # Act
        actual_result = self.harbor_dues_draft_form._has_permission(user, action, False)
        # Assert
        self.assertEqual(actual_result, expected_result)

    def test_approve_transition(self):
        # Act
        self.harbor_dues_form.approve()
        self.harbor_dues_form.save()
        # Assert
        self.assertEqual(self.harbor_dues_form._change_reason, Status.APPROVED.label)

    def test_reject_transition(self):
        # Arrange
        reason = "Afvist fordi der mangler noget"
        # Act
        self.harbor_dues_form.reject(reason=reason)
        self.harbor_dues_form.save()
        # Assert
        self.assertEqual(self.harbor_dues_form._change_reason, Status.REJECTED.label)
        # Assert that the rejection reason is saved as part of the history
        self.assertQuerySetEqual(
            self.harbor_dues_form.history.filter(status=Status.REJECTED),
            [reason],
            transform=lambda obj: obj.reason_text,
        )


class TestCruiseTaxForm(HarborDuesFormMixin, TestCase):
    def test_has_port_of_call(self):
        self.assertTrue(self.cruise_tax_form.has_port_of_call)
        self.assertFalse(self.cruise_tax_form_without_port_of_call.has_port_of_call)

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

    @override_settings(
        EMAIL_ADDRESS_SKATTESTYRELSEN="skattestyrelsen@example.org",
        EMAIL_ADDRESS_AUTHORITY_NO_PORT_OF_CALL="ral@example.org",
    )
    def test_mail_recipients_falls_back_if_no_port_of_call(self):
        instance = MailRecipientList(self.cruise_tax_form_without_port_of_call)
        self.assertListEqual(
            instance.recipient_emails,
            [
                settings.EMAIL_ADDRESS_AUTHORITY_NO_PORT_OF_CALL,
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
