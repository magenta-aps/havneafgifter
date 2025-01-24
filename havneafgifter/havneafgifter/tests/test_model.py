from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase
from unittest_parametrize import ParametrizedTestCase, parametrize

from havneafgifter.models import (
    CruiseTaxForm,
    DisembarkmentSite,
    HarborDuesForm,
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
from havneafgifter.tests.mixins import HarborDuesFormTestMixin


class ModelTest(ParametrizedTestCase, HarborDuesFormTestMixin, TestCase):
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


class TestUser(ParametrizedTestCase, HarborDuesFormTestMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.other_port_authority = PortAuthority.objects.create(
            email="other@example.org"
        )

    def test_port_user_must_have_port_authority(self):
        instance = User(port=self.port, port_authority=None)
        with self.assertRaisesRegex(
            ValidationError, "specify a port authority if a port is specified"
        ):
            instance.clean()

    def test_port_must_belong_to_port_authority(self):
        instance = User(port=self.port, port_authority=self.other_port_authority)
        with self.assertRaisesRegex(
            ValidationError,
            "port specified must belong to the selected port authority",
        ):
            instance.clean()

    @parametrize(
        "username,expected_display_name",
        [
            # Ship user
            ("9074729", "9074729 / Mary"),
            # Shipping user
            ("shipping_agent", "shipping_agent / Agent"),
            # Port authority user
            ("port_auth", "Havnemyndighed 1 / admin"),
            # Port user
            ("port_user", "Nordhavn / Havnemyndighed 1"),
            # Tax authority user
            ("tax", "AKA - tax@example.org"),
        ],
    )
    def test_display_name(self, username, expected_display_name):
        user = User.objects.get(username=username)
        actual_display_name = user.display_name
        self.assertEqual(actual_display_name, expected_display_name)

    @parametrize(
        "username,can_create,can_view_list,can_view_statistics",
        [
            # User without user type
            ("unprivileged", False, True, False),
            # Ship user
            ("9074729", True, True, False),
            # Shipping user
            ("shipping_agent", True, True, False),
            # Port authority user
            ("port_auth", False, True, False),
            # Port user
            ("port_user", False, True, False),
            # Tax authority user
            ("tax", False, True, True),
            # Admin user
            ("admin", True, True, True),
        ],
    )
    def test_can_create_etc(
        self,
        username: str | None,
        can_create: bool,
        can_view_list: bool,
        can_view_statistics: bool,
    ):
        user = User.objects.get(username=username)
        self.assertEqual(can_create, user.can_create)
        self.assertEqual(can_view_list, user.can_view_list)
        self.assertEqual(can_view_statistics, user.can_view_statistics)


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


class TestHarborDuesForm(ParametrizedTestCase, HarborDuesFormTestMixin, TestCase):
    maxDiff = None

    @parametrize(
        "status,field,required",
        [
            (Status.NEW, "port_of_call", True),
            (Status.DRAFT, "port_of_call", False),
            (Status.NEW, "gross_tonnage", True),
            (Status.DRAFT, "gross_tonnage", False),
            (Status.DRAFT, "datetime_of_arrival", False),
            (Status.NEW, "datetime_of_departure", True),
            (Status.DRAFT, "datetime_of_departure", False),
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

    @parametrize(
        "status,action,username,expected_result",
        [
            # 1. "submit_for_review"
            #   Ship users can submit drafts for review
            (Status.DRAFT, "submit_for_review", "9074729", True),
            #   Shipping agents can submit drafts for review
            (Status.DRAFT, "submit_for_review", "shipping_agent", True),
            #   Port authority users cannot submit drafts for review
            (Status.DRAFT, "submit_for_review", "port_auth", False),
            # 2. "approve"
            #   Ship users cannot approve forms submitted for review
            (Status.NEW, "approve", "9074729", False),
            #   Shipping agents cannot approve forms submitted for review
            (Status.NEW, "approve", "shipping_agent", False),
            #   Port authority users can approve forms submitted for review
            (Status.NEW, "approve", "port_auth", True),
            # 3. "reject"
            #   Ship users cannot reject forms submitted for review
            (Status.NEW, "reject", "9074729", False),
            #   Shipping agents cannot reject forms submitted for review
            (Status.NEW, "reject", "shipping_agent", False),
            #   Port authority users can reject forms submitted for review
            (Status.NEW, "reject", "port_auth", True),
        ],
    )
    def test_transition_permissions(
        self,
        status: Status,
        action: str,
        username: str,
        expected_result: str,
    ):
        # Arrange
        user = User.objects.get(username=username)
        form = (
            self.harbor_dues_draft_form
            if status == Status.DRAFT
            else self.harbor_dues_form
        )
        # Act
        actual_result = form.has_permission(user, action, False)
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
        # Assert that the model property `latest_rejection` returns the expected
        # history entry.
        self.assertIsNotNone(self.harbor_dues_form.latest_rejection)
        self.assertEqual(self.harbor_dues_form.latest_rejection.reason_text, reason)

    def test_latest_rejection_is_none_if_no_rejection_has_reason(self):
        # Arrange
        self.harbor_dues_form.reject(reason=None)
        self.harbor_dues_form.save()
        # Act and assert
        self.assertIsNone(self.harbor_dues_form.latest_rejection)

    def test_latest_rejection_is_none_if_not_rejected(self):
        # A form whose status is not REJECTED returns None in `latest_rejection`
        self.assertIsNone(self.harbor_dues_form.latest_rejection)


class TestCruiseTaxForm(HarborDuesFormTestMixin, TestCase):
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

    def test_reject_transition(self):
        # Arrange
        reason = "Afvist fordi der mangler noget"
        # Retrieve the cruise tax form "as" a harbor dues form, as the `reject` logic
        # only updates the history in `HarborDuesForm.history`.
        harbor_dues_form = HarborDuesForm.objects.get(pk=self.cruise_tax_form.pk)
        # Act
        harbor_dues_form.reject(reason=reason)
        harbor_dues_form.save()
        # Refresh DB object
        self.cruise_tax_form = CruiseTaxForm.objects.get(pk=self.cruise_tax_form.pk)
        # Assert state changes on the modified `HarborDuesForm` object
        self.assertEqual(harbor_dues_form._change_reason, Status.REJECTED.label)
        # Assert that the rejection reason is saved as part of the `HarborDuesForm`
        # history.
        self.assertQuerySetEqual(
            harbor_dues_form.history.filter(status=Status.REJECTED),
            [reason],
            transform=lambda obj: obj.reason_text,
        )
        # Assert that `CruiseTaxForm.latest_rejection` returns the expected history
        # entry.
        self.assertIsNotNone(self.cruise_tax_form.latest_rejection)
        self.assertEqual(self.cruise_tax_form.latest_rejection.reason_text, reason)


class TestDisembarkmentSite(TestCase):
    def test_str(self):
        instance = DisembarkmentSite(
            name="Naturen",
            municipality=Municipality.AVANNAATA,
        )
        self.assertEqual(str(instance), "Naturen (Avannaata)")


class TestVessel(HarborDuesFormTestMixin, TestCase):
    def test_str(self):
        self.assertEqual(str(self.ship_user_vessel), self.ship_user_vessel.imo)


class TestTaxRates(TestCase):
    def test_can_delete(self):
        new_bad_tax_rate = TaxRates(
            start_datetime=datetime.now(timezone.utc) + timedelta(days=1)
        )
        new_good_tax_rate = TaxRates(
            start_datetime=datetime.now(timezone.utc) + timedelta(days=8)
        )

        self.assertTrue(new_good_tax_rate.is_within_editing_deadline())
        self.assertFalse(new_bad_tax_rate.is_within_editing_deadline())
