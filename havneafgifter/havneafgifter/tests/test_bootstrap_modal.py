from django.test import SimpleTestCase

from havneafgifter.models import Vessel
from havneafgifter.templatetags.bootstrap_modal import (
    inform_ship_user_on_save_vessel_change_modal,
)


class TestInformShipUserOnSaveVesselChangeModal(SimpleTestCase):
    def test_context(self):
        vessel: Vessel = Vessel()
        context = inform_ship_user_on_save_vessel_change_modal({}, vessel)
        self.assertEqual(context["form"], vessel)
