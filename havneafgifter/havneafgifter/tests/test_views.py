from django.http import HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse
from unittest_parametrize import ParametrizedTestCase, parametrize

from ..models import CruiseTaxForm, HarborDuesForm, ShipType
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
