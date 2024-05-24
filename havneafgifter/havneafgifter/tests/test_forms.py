import copy
from datetime import datetime, timezone

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.forms.utils import ErrorList
from django.test import SimpleTestCase, TestCase
from unittest_parametrize import ParametrizedTestCase, parametrize

from havneafgifter.forms import (
    DisembarkmentForm,
    HarborDuesFormForm,
    PassengersByCountryForm,
    PassengersTotalForm,
)
from havneafgifter.models import DisembarkmentSite, Nationality, Port
from havneafgifter.tests.mixins import HarborDuesFormMixin


class TestHarborDuesFormForm(ParametrizedTestCase, HarborDuesFormMixin, TestCase):
    @parametrize(
        "changes",
        [
            (
                {
                    "datetime_of_arrival": datetime(2020, 1, 1, tzinfo=timezone.utc),
                    "datetime_of_departure": None,
                },
            ),
            (
                {
                    "datetime_of_arrival": None,
                    "datetime_of_departure": datetime(2020, 1, 1, tzinfo=timezone.utc),
                },
            ),
        ],
    )
    def test_error_on_arrival_but_no_departure(self, changes):
        data = copy.copy(self.harbor_dues_form_data)
        data.update(changes)
        self._assert_form_has_error(
            data, "port_of_call_requires_arrival_and_departure_dates"
        )

    def test_error_on_departure_before_arrival(self):
        data = copy.copy(self.harbor_dues_form_data)
        # Swap date of arrival with date of departure
        data["datetime_of_arrival"], data["datetime_of_departure"] = (
            data["datetime_of_departure"],
            data["datetime_of_arrival"],
        )
        self._assert_form_has_error(
            data, "datetime_of_departure_before_datetime_of_arrival"
        )

    @parametrize(
        "port_of_call,no_port_of_call,expected_error_code",
        [
            # Provide "port of call" and set "no port of call" to True
            (
                "Nordhavn",
                True,
                "port_of_call_chosen_but_no_port_of_call_is_true",
            ),
            # Provide no "port of call" and set "no port of call" to False
            (
                None,
                False,
                "port_of_call_is_empty_and_no_port_of_call_is_false",
            ),
        ],
    )
    def test_error_on_port_of_call_vs_no_port_of_call(
        self,
        port_of_call,
        no_port_of_call,
        expected_error_code,
    ):
        data = copy.copy(self.harbor_dues_form_data)
        data["port_of_call"] = (
            Port.objects.get(name=port_of_call) if port_of_call else None
        )
        data["no_port_of_call"] = no_port_of_call
        self._assert_form_has_error(data, expected_error_code)

    def test_error_on_no_port_of_call_if_non_cruise_ship(self):
        # In `self.harbor_dues_form_data`, `vessel_type` is already set to
        # `VesselType.FREIGHTER`.
        data = copy.copy(self.harbor_dues_form_data)
        # Try to submit a "no port of call" form for a non-cruise ship
        data["no_port_of_call"] = True
        data["port_of_call"] = None
        self._assert_form_has_error(
            data, "no_port_of_call_cannot_be_true_for_non_cruise_ships"
        )

    def test_user_visible_non_field_errors(self):
        # Submit data that will lead to violating a database constraint
        data = copy.copy(self.harbor_dues_form_data)
        data["gross_tonnage"] = None
        form = HarborDuesFormForm(data=data)
        # We expect the `form.save(...)` to raise ValueError in this case
        try:
            form.save(commit=False)
        except ValueError:
            # Assert that the DB constraint violation produces the expected
            # non-field error.
            self.assertEqual(
                str(form.errors.get(NON_FIELD_ERRORS)[0]),
                "Constraint “gross_tonnage_cannot_be_null_for_non_cruise_ships” "
                "is violated.",
            )
            # Assert that the same non-field error is not visible to the user
            self.assertEqual(
                form.user_visible_non_field_errors(),
                ErrorList(),  # empty error list
            )

    def _assert_form_has_error(self, data, code):
        form = HarborDuesFormForm(data=data)
        # Trigger form validation
        form.is_valid()
        # Assert that our validation error is raised
        with self.assertRaises(ValidationError) as exc:
            form.clean()
            self.assertEqual(exc.code, code)


class TestPassengersByCountryForm(TestCase):
    def test_number_of_passengers_label(self):
        form = PassengersByCountryForm(initial={"nationality": Nationality.DENMARK})
        self.assertEqual(
            form.fields["number_of_passengers"].label,
            form.initial["nationality"].label,
        )


class TestDisembarkmentForm(HarborDuesFormMixin, TestCase):
    def test_disembarkment_site_initial(self):
        ds = DisembarkmentSite.objects.first()
        form = DisembarkmentForm(initial={"disembarkment_site": ds.pk})
        self.assertListEqual(
            form.fields["disembarkment_site"].choices,
            [(ds.pk, str(ds))],
        )

    def test_number_of_passengers_label(self):
        ds = DisembarkmentSite.objects.first()
        form = DisembarkmentForm(initial={"disembarkment_site": ds.pk})
        self.assertEqual(
            form.fields["number_of_passengers"].label,
            form.initial_disembarkment_site.name,
        )

    def test_number_of_passengers_label_outside_populated_areas(self):
        ds = DisembarkmentSite.objects.filter(is_outside_populated_areas=True).first()
        form = DisembarkmentForm(initial={"disembarkment_site": ds.pk})
        self.assertEqual(
            form.fields["number_of_passengers"].label,
            ds._meta.get_field("is_outside_populated_areas").verbose_name,
        )

    def test_clean_disembarkment_site(self):
        ds = DisembarkmentSite.objects.first()
        form = DisembarkmentForm(
            initial={"disembarkment_site": ds.pk},
            data={"disembarkment_site": ds.pk, "number_of_passengers": 0},
        )
        # Trigger form validation
        form.is_valid()
        # Assert that our clean method returns model instance
        self.assertEqual(form.clean_disembarkment_site(), ds)

    def test_get_municipality_display(self):
        ds = DisembarkmentSite.objects.first()
        form = DisembarkmentForm(initial={"disembarkment_site": ds.pk})
        self.assertEqual(form.get_municipality_display(), ds.get_municipality_display())


class TestPassengersTotalForm(SimpleTestCase):
    def test_validate_total(self):
        instance = PassengersTotalForm(data={"total_number_of_passengers": "100"})
        instance.validate_total(101)
        self.assertEqual(len(instance.errors), 1)
        self.assertIn("total_number_of_passengers", instance.errors)
