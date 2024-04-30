import copy

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from havneafgifter.forms import (
    DisembarkmentForm,
    HarborDuesFormForm,
    PassengersTotalForm,
)
from havneafgifter.models import DisembarkmentSite
from havneafgifter.tests.mixins import HarborDuesFormMixin


class TestHarborDuesFormForm(HarborDuesFormMixin, TestCase):
    def test_date_validation(self):
        data = copy.copy(self.harbor_dues_form_data)
        # Swap date of arrival with date of departure
        data["datetime_of_arrival"], data["datetime_of_departure"] = (
            data["datetime_of_departure"],
            data["datetime_of_arrival"],
        )
        form = HarborDuesFormForm(data=data)
        # Trigger form validation
        form.is_valid()
        # Assert that our validation error is raised
        with self.assertRaises(ValidationError):
            form.clean()


class TestPassengersByDisembarkmentSiteForm(HarborDuesFormMixin, TestCase):
    def test_disembarkment_site_choices(self):
        form = DisembarkmentForm()
        self.assertListEqual(
            form.fields["disembarkment_site"].choices,
            [(ds.pk, str(ds)) for ds in DisembarkmentSite.objects.all()],
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


class TestPassengersTotalForm(SimpleTestCase):
    def test_validate_total(self):
        instance = PassengersTotalForm(data={"total_number_of_passengers": "100"})
        instance.validate_total(101)
        self.assertEqual(len(instance.errors), 1)
        self.assertIn("total_number_of_passengers", instance.errors)
