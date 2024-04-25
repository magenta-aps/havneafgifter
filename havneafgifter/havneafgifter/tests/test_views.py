from unittest.mock import ANY, patch

from django.contrib import messages
from django.forms import BaseFormSet
from django.http import HttpResponseRedirect
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from unittest_parametrize import ParametrizedTestCase, parametrize

from havneafgifter.models import (
    CruiseTaxForm,
    DisembarkmentSite,
    HarborDuesForm,
    Nationality,
    ShipType,
)
from havneafgifter.tests.mixins import HarborDuesFormMixin
from havneafgifter.views import (
    EnvironmentalTaxCreateView,
    PassengerTaxCreateView,
    _CruiseTaxFormSetView,
)


class TestHarborDuesFormCreateView(ParametrizedTestCase, HarborDuesFormMixin, TestCase):
    @parametrize(
        "vessel_type,model_class,next_view_name",
        [
            # Test 1: freighter, etc. creates harbor dues form and sends user
            # to the harbor dues form detail view.
            (
                ShipType.FREIGHTER,
                HarborDuesForm,
                "havneafgifter:harbor_dues_form_detail",
            ),
            # Test 2: cruise ship creates cruise tax form and sends user to the
            # passenger tax form.
            (
                ShipType.CRUISE,
                CruiseTaxForm,
                "havneafgifter:passenger_tax_create",
            ),
        ],
    )
    def test_creates_model_instance_depending_on_vessel_type(
        self, vessel_type, model_class, next_view_name
    ):
        self.harbor_dues_form_data_pk["vessel_type"] = vessel_type
        response = self.client.post(
            reverse("havneafgifter:harbor_dues_form_create"),
            data=self.harbor_dues_form_data_pk,
        )
        instance = model_class.objects.latest("pk")
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(
            response.url,
            reverse(next_view_name, kwargs={"pk": instance.pk}),
        )


class TestCruiseTaxFormSetView(HarborDuesFormMixin, TestCase):
    view_class = _CruiseTaxFormSetView

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.get_request = cls.request_factory.get("")
        cls.instance = cls.view_class()
        cls.instance._cruise_tax_form = cls.cruise_tax_form

    def test_setup(self):
        with patch.object(CruiseTaxForm.objects, "get") as mock_get:
            self.instance.setup(self.get_request, pk=0)
            mock_get.assert_called_once_with(pk=0)

    def _assert_get_form_returns_expected_formset(self):
        self.instance.request = self.get_request
        formset = self.instance.get_form()
        self.assertIsInstance(formset, BaseFormSet)
        self.assertIs(formset.form, self.view_class.form_class)
        self.assertFalse(formset.can_order)
        self.assertFalse(formset.can_delete)
        self.assertEqual(formset.extra, 0)

    def _assert_get_context_data_includes_formset(self, name):
        self.instance.request = self.get_request
        context_data = self.instance.get_context_data()
        self.assertIsInstance(context_data[name], BaseFormSet)

    def _post_formset(self, *form_items, prefix="form"):
        data = {
            "form-TOTAL_FORMS": len(form_items),
            "form-INITIAL_FORMS": len(form_items),
        }
        for idx, item in enumerate(form_items):
            for key, val in item.items():
                data[f"{prefix}-{idx}-{key}"] = val
        self.instance.request = self.request_factory.post("", data=data)


class TestPassengerTaxCreateView(TestCruiseTaxFormSetView):
    view_class = PassengerTaxCreateView

    def test_get_form_returns_expected_formset(self):
        self._assert_get_form_returns_expected_formset()

    def test_get_form_kwargs_populates_initial(self):
        self.instance.request = self.get_request
        form_kwargs = self.instance.get_form_kwargs()
        self.assertListEqual(
            form_kwargs["initial"],
            [
                {"nationality": nationality, "number_of_passengers": 0}
                for nationality in Nationality
            ],
        )

    def test_get_context_data_populates_formset(self):
        self._assert_get_context_data_includes_formset("passengers_by_country_formset")

    def test_form_valid_creates_objects(self):
        # Arrange
        self._post_formset({"number_of_passengers": 42})
        # Act: trigger DB insert logic
        self.instance.form_valid(self.instance.get_form())
        # Assert: verify that the specified `PassengersByCountry` objects are
        # created.
        self.assertQuerySetEqual(
            self.cruise_tax_form.passengers_by_country.values(
                "cruise_tax_form",
                "nationality",
                "number_of_passengers",
            ),
            [
                {
                    "cruise_tax_form": self.cruise_tax_form.pk,
                    "nationality": Nationality.AUSTRALIA.value,
                    "number_of_passengers": 42,
                }
            ],
        )


class TestEnvironmentalTaxCreateView(TestCruiseTaxFormSetView):
    view_class = EnvironmentalTaxCreateView

    def test_get_form_returns_expected_formset(self):
        self._assert_get_form_returns_expected_formset()

    def test_get_form_kwargs_populates_initial(self):
        self.instance.request = self.get_request
        form_kwargs = self.instance.get_form_kwargs()
        self.assertListEqual(
            form_kwargs["initial"],
            [
                {"disembarkment_site": ds.pk, "number_of_passengers": 0}
                for ds in DisembarkmentSite.objects.all()
            ],
        )

    def test_get_context_data_populates_formset(self):
        self._assert_get_context_data_includes_formset("disembarkment_formset")

    def test_form_valid_creates_objects(self):
        # Arrange
        self._post_formset(
            {
                "disembarkment_site": DisembarkmentSite.objects.first().pk,
                "number_of_passengers": 42,
            }
        )
        with patch("havneafgifter.views.messages.add_message") as mock_add_message:
            # Act: trigger DB insert logic
            self.instance.form_valid(self.instance.get_form())
            # Assert: verify that the specified `PassengersByCountry` objects are
            # created.
            self.assertQuerySetEqual(
                self.cruise_tax_form.disembarkment_set.values(
                    "cruise_tax_form",
                    "disembarkment_site",
                    "number_of_passengers",
                ),
                [
                    {
                        "cruise_tax_form": self.cruise_tax_form.pk,
                        "disembarkment_site": DisembarkmentSite.objects.first().pk,
                        "number_of_passengers": 42,
                    }
                ],
            )
            # Assert: verify that we displayed a "thank you" message
            mock_add_message.assert_called_once_with(ANY, messages.SUCCESS, _("Thanks"))
