from unittest.mock import patch

from django.forms import BaseFormSet
from django.http import HttpResponseRedirect
from django.test import RequestFactory, TestCase
from django.urls import reverse
from unittest_parametrize import ParametrizedTestCase, parametrize

from ..forms import PassengersByCountryForm
from ..models import CruiseTaxForm, HarborDuesForm, Nationality, ShipType
from ..views import PassengerTaxCreateView
from .mixins import HarborDuesFormMixin


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
        self.harbor_dues_form_data["vessel_type"] = vessel_type
        response = self.client.post(
            reverse("havneafgifter:harbor_dues_form_create"),
            data=self.harbor_dues_form_data,
        )
        instance = model_class.objects.latest("pk")
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(
            response.url,
            reverse(next_view_name, kwargs={"pk": instance.pk}),
        )


class TestPassengerTaxCreateView(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.get_request = cls.request_factory.get("")
        cls.instance = PassengerTaxCreateView()

    def test_setup(self):
        with patch.object(CruiseTaxForm.objects, "get") as mock_get:
            self.instance.setup(self.get_request, pk=0)
            mock_get.assert_called_once_with(pk=0)

    def test_get_form_returns_formset(self):
        self.instance.request = self.get_request
        formset = self.instance.get_form()
        self.assertIsInstance(formset, BaseFormSet)
        self.assertIs(formset.form, PassengersByCountryForm)
        self.assertFalse(formset.can_order)
        self.assertFalse(formset.can_delete)
        self.assertEqual(formset.extra, 0)

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
        self.instance.request = self.get_request
        context_data = self.instance.get_context_data()
        self.assertIsInstance(
            context_data["passengers_by_country_formset"],
            BaseFormSet,
        )
