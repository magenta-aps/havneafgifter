from datetime import datetime
from decimal import Decimal

from django.contrib import auth
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase

from havneafgifter.models import (
    Country,
    CruiseTaxForm,
    Disembarkment,
    DisembarkmentSite,
    DisembarkmentTaxRate,
    Municipality,
    Nationality,
    PassengersByCountry,
    Port,
    PortAuthority,
    PortTaxRate,
    ShippingAgent,
    ShipType,
    TaxRates,
    User,
)
from havneafgifter.permissions import HavneafgiftPermissionBackend


class PermissionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("create_groups", verbosity=1)

        cls.shipping_agent = ShippingAgent.objects.create(
            name="Smith", email="smith@matrix.net"
        )
        cls.shipping_agent_other = ShippingAgent.objects.create(
            name="Jones", email="jones@matrix.net"
        )
        cls.port_authority = PortAuthority.objects.create(
            name="Royal Arctic Line A/S", email="ral@ral.dk"
        )
        cls.port = Port.objects.create(
            name="Upernavik", portauthority=cls.port_authority
        )
        cls.port_authority_other = PortAuthority.objects.create(
            name="KNI Pilersuisoq A/S", email="info@kni.gl"
        )
        cls.port_other = Port.objects.create(
            name="Qeqertarsuaq", portauthority=cls.port_authority_other
        )
        cls.taxrates = TaxRates.objects.create(
            pax_tax_rate=Decimal(1.0),
            start_datetime=datetime(2024, 1, 1, 0, 0, 0),
            end_datetime=datetime(2025, 1, 1, 0, 0, 0),
        )
        cls.port_taxrate = PortTaxRate.objects.create(
            tax_rates=cls.taxrates, gt_start=0, port_tax_rate=Decimal(1.0)
        )
        cls.disembarkment_taxrate = DisembarkmentTaxRate.objects.create(
            tax_rates=cls.taxrates,
            municipality=Municipality.SERMERSOOQ,
            disembarkment_tax_rate=Decimal(1.0),
        )

        cls.admin_user = User.objects.create(username="admin_user", is_superuser=True)
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

        cls.unprivileged_user = User.objects.create(username="trudy")
        cls.inactive_user = User.objects.create(
            username="lazy_bastard", is_active=False
        )
        cls.form = CruiseTaxForm.objects.create(
            port_of_call=cls.port,
            nationality=Country.DENMARK,
            vessel_name="Naglfar",
            vessel_imo="9074729",
            vessel_owner="Magenta ApS",
            vessel_master="Bent Handberg",
            shipping_agent=cls.shipping_agent,
            datetime_of_arrival=datetime(2024, 5, 1, 12, 0, 0),
            datetime_of_departure=datetime(2024, 6, 1, 12, 0, 0),
            gross_tonnage=50000,
            vessel_type=ShipType.CRUISE,
            number_of_passengers=5000,
        )
        cls.form_other = CruiseTaxForm.objects.create(
            port_of_call=cls.port_other,
            nationality=Country.DENMARK,
            vessel_name="Naglfar",
            vessel_imo="9074729",
            vessel_owner="Magenta ApS",
            vessel_master="Bent Handberg",
            shipping_agent=cls.shipping_agent_other,
            datetime_of_arrival=datetime(2024, 5, 1, 12, 0, 0),
            datetime_of_departure=datetime(2024, 6, 1, 12, 0, 0),
            gross_tonnage=50000,
            vessel_type=ShipType.CRUISE,
            number_of_passengers=5000,
        )
        cls.passengers_by_country = PassengersByCountry.objects.create(
            cruise_tax_form=cls.form,
            nationality=Nationality.DENMARK,
            number_of_passengers=5000,
        )
        cls.passengers_by_country_other = PassengersByCountry.objects.create(
            cruise_tax_form=cls.form_other,
            nationality=Nationality.DENMARK,
            number_of_passengers=5000,
        )
        cls.disembarkment_site = DisembarkmentSite.objects.create(
            name="TestSite", municipality=Municipality.SERMERSOOQ
        )
        cls.disembarkment = Disembarkment.objects.create(
            cruise_tax_form=cls.form,
            disembarkment_site=cls.disembarkment_site,
            number_of_passengers=50,
        )
        cls.disembarkment_other = Disembarkment.objects.create(
            cruise_tax_form=cls.form_other,
            disembarkment_site=cls.disembarkment_site,
            number_of_passengers=50,
        )
        cls.backend = [
            b
            for b in auth.get_backends()
            if isinstance(b, HavneafgiftPermissionBackend)
        ][0]

    def _test_access(self, user, item, action, access):
        cls = item.__class__
        perm_name = f"havneafgifter.{action}_{cls._meta.model_name}"
        classname = cls.__name__
        qs = cls.objects.all()
        filtered_qs = cls.filter_user_permissions(qs, user, action)
        if access:
            self.assertIn(
                item,
                filtered_qs,
                f"Filtering {classname} objects based on '{user}' "
                f"permissions for action '{action}' did not yield expected item",
            )
            self.assertTrue(
                item.has_permission(user, action, False),
                f"{classname}.has_permissions for user '{user}', "
                f"action '{action}' did not return True",
            )
            self.assertTrue(
                user.has_perm(perm_name, item),
                f"User.has_permissions for user '{user}' on object "
                f"'{item}', action '{action}' did not return True",
            )
            self.assertIn(
                perm_name,
                self.backend.get_all_permissions(user, item),
                f"{perm_name} not found in user permissions for "
                f"{user} | {item} | {action}",
            )
        else:
            self.assertNotIn(
                item,
                filtered_qs,
                f"Filtering {classname} objects based on '{user}' "
                f"permissions for action '{action}' yielded unexpected item",
            )
            self.assertFalse(
                item.has_permission(user, action, False),
                f"{classname}.has_permissions for user '{user}', "
                f"action '{action}' did not return False",
            )
            self.assertFalse(
                user.has_perm(perm_name, item),
                f"User.has_permissions for user '{user}' on object "
                f"'{item}', action '{action}' did not return False",
            )
            self.assertNotIn(
                perm_name,
                self.backend.get_all_permissions(user, item),
                f"{perm_name} unexpectedly found in user "
                f"permissions for {user} | {item} | {action}",
            )


class ShippingAgentPermissionTest(PermissionTest):
    @property
    def item(self):
        return self.shipping_agent

    @property
    def other_item(self):
        # Unassociated item
        return self.shipping_agent_other

    def test_admin(self):
        self._test_access(self.admin_user, self.item, "view", True)
        self._test_access(self.admin_user, self.item, "change", True)
        self._test_access(self.admin_user, self.item, "delete", True)
        self._test_access(self.admin_user, self.other_item, "view", True)
        self._test_access(self.admin_user, self.other_item, "change", True)
        self._test_access(self.admin_user, self.other_item, "delete", True)

    def test_portmanager(self):
        self._test_access(self.port_manager_user, self.item, "view", True)
        self._test_access(self.port_manager_user, self.item, "change", False)
        self._test_access(self.port_manager_user, self.item, "delete", False)
        self._test_access(self.port_manager_user, self.other_item, "view", True)
        self._test_access(self.port_manager_user, self.other_item, "change", False)
        self._test_access(self.port_manager_user, self.other_item, "delete", False)

    def test_agent(self):
        self._test_access(self.agent_user, self.item, "view", True)
        self._test_access(self.agent_user, self.item, "change", True)
        self._test_access(self.agent_user, self.item, "delete", False)
        self._test_access(self.agent_user, self.other_item, "view", True)
        self._test_access(self.agent_user, self.other_item, "change", False)
        self._test_access(self.agent_user, self.other_item, "delete", False)

    def test_tax(self):
        self._test_access(self.tax_user, self.item, "view", True)
        self._test_access(self.tax_user, self.item, "change", False)
        self._test_access(self.tax_user, self.item, "delete", False)
        self._test_access(self.tax_user, self.other_item, "view", True)
        self._test_access(self.tax_user, self.other_item, "change", False)
        self._test_access(self.tax_user, self.other_item, "delete", False)

    def test_unprivileged(self):
        self._test_access(self.unprivileged_user, self.item, "view", False)
        self._test_access(self.unprivileged_user, self.item, "change", False)
        self._test_access(self.unprivileged_user, self.item, "delete", False)
        self._test_access(self.unprivileged_user, self.other_item, "view", False)
        self._test_access(self.unprivileged_user, self.other_item, "change", False)
        self._test_access(self.unprivileged_user, self.other_item, "delete", False)

    def test_inactive(self):
        self._test_access(self.inactive_user, self.item, "view", False)
        self._test_access(self.inactive_user, self.item, "change", False)
        self._test_access(self.inactive_user, self.item, "delete", False)
        self._test_access(self.inactive_user, self.other_item, "view", False)
        self._test_access(self.inactive_user, self.other_item, "change", False)
        self._test_access(self.inactive_user, self.other_item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(self.inactive_user, self.item),
            set(),
        )
        self.assertEqual(
            self.backend.get_group_permissions(self.inactive_user, self.other_item),
            set(),
        )


class PortAuthorityPermissionTest(PermissionTest):
    @property
    def item(self):
        return self.port_authority

    @property
    def other_item(self):
        # Unassociated item
        return self.port_authority_other

    def test_admin(self):
        self._test_access(self.admin_user, self.item, "view", True)
        self._test_access(self.admin_user, self.item, "change", True)
        self._test_access(self.admin_user, self.item, "delete", True)
        self._test_access(self.admin_user, self.other_item, "view", True)
        self._test_access(self.admin_user, self.other_item, "change", True)
        self._test_access(self.admin_user, self.other_item, "delete", True)

    def test_portmanager(self):
        self._test_access(self.port_manager_user, self.item, "view", True)
        self._test_access(self.port_manager_user, self.item, "change", True)
        self._test_access(self.port_manager_user, self.item, "delete", False)
        # Portmanager may not change portauthority for another port
        self._test_access(self.port_manager_user, self.other_item, "view", True)
        self._test_access(self.port_manager_user, self.other_item, "change", False)
        self._test_access(self.port_manager_user, self.other_item, "delete", False)

    def test_agent(self):
        self._test_access(self.agent_user, self.item, "view", True)
        self._test_access(self.agent_user, self.item, "change", False)
        self._test_access(self.agent_user, self.item, "delete", False)
        self._test_access(self.agent_user, self.other_item, "view", True)
        self._test_access(self.agent_user, self.other_item, "change", False)
        self._test_access(self.agent_user, self.other_item, "delete", False)

    def test_tax(self):
        self._test_access(self.tax_user, self.item, "view", True)
        self._test_access(self.tax_user, self.item, "change", False)
        self._test_access(self.tax_user, self.item, "delete", False)
        self._test_access(self.tax_user, self.other_item, "view", True)
        self._test_access(self.tax_user, self.other_item, "change", False)
        self._test_access(self.tax_user, self.other_item, "delete", False)

    def test_unprivileged(self):
        self._test_access(self.unprivileged_user, self.item, "view", False)
        self._test_access(self.unprivileged_user, self.item, "change", False)
        self._test_access(self.unprivileged_user, self.item, "delete", False)
        self._test_access(self.unprivileged_user, self.other_item, "view", False)
        self._test_access(self.unprivileged_user, self.other_item, "change", False)
        self._test_access(self.unprivileged_user, self.other_item, "delete", False)

    def test_inactive(self):
        self._test_access(self.inactive_user, self.item, "view", False)
        self._test_access(self.inactive_user, self.item, "change", False)
        self._test_access(self.inactive_user, self.item, "delete", False)
        self._test_access(self.inactive_user, self.other_item, "view", False)
        self._test_access(self.inactive_user, self.other_item, "change", False)
        self._test_access(self.inactive_user, self.other_item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(self.inactive_user, self.item),
            set(),
        )
        self.assertEqual(
            self.backend.get_group_permissions(self.inactive_user, self.other_item),
            set(),
        )


class PortPermissionTest(PermissionTest):
    @property
    def item(self):
        return self.port

    @property
    def other_item(self):
        # Unassociated item
        return self.port_other

    def test_admin(self):
        self._test_access(self.admin_user, self.item, "view", True)
        self._test_access(self.admin_user, self.item, "change", True)
        self._test_access(self.admin_user, self.item, "delete", True)
        self._test_access(self.admin_user, self.other_item, "view", True)
        self._test_access(self.admin_user, self.other_item, "change", True)
        self._test_access(self.admin_user, self.other_item, "delete", True)

    def test_portmanager(self):
        self._test_access(self.port_manager_user, self.item, "view", True)
        self._test_access(self.port_manager_user, self.item, "change", False)
        self._test_access(self.port_manager_user, self.item, "delete", False)
        self._test_access(self.port_manager_user, self.other_item, "view", True)
        self._test_access(self.port_manager_user, self.other_item, "change", False)
        self._test_access(self.port_manager_user, self.other_item, "delete", False)

    def test_agent(self):
        self._test_access(self.agent_user, self.item, "view", True)
        self._test_access(self.agent_user, self.item, "change", False)
        self._test_access(self.agent_user, self.item, "delete", False)
        self._test_access(self.agent_user, self.other_item, "view", True)
        self._test_access(self.agent_user, self.other_item, "change", False)
        self._test_access(self.agent_user, self.other_item, "delete", False)

    def test_tax(self):
        self._test_access(self.tax_user, self.item, "view", True)
        self._test_access(self.tax_user, self.item, "change", False)
        self._test_access(self.tax_user, self.item, "delete", False)
        self._test_access(self.tax_user, self.other_item, "view", True)
        self._test_access(self.tax_user, self.other_item, "change", False)
        self._test_access(self.tax_user, self.other_item, "delete", False)

    def test_unprivileged(self):
        self._test_access(self.unprivileged_user, self.item, "view", False)
        self._test_access(self.unprivileged_user, self.item, "change", False)
        self._test_access(self.unprivileged_user, self.item, "delete", False)
        self._test_access(self.unprivileged_user, self.other_item, "view", False)
        self._test_access(self.unprivileged_user, self.other_item, "change", False)
        self._test_access(self.unprivileged_user, self.other_item, "delete", False)

    def test_inactive(self):
        self._test_access(self.inactive_user, self.item, "view", False)
        self._test_access(self.inactive_user, self.item, "change", False)
        self._test_access(self.inactive_user, self.item, "delete", False)
        self._test_access(self.inactive_user, self.other_item, "view", False)
        self._test_access(self.inactive_user, self.other_item, "change", False)
        self._test_access(self.inactive_user, self.other_item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(self.inactive_user, self.item),
            set(),
        )
        self.assertEqual(
            self.backend.get_group_permissions(self.inactive_user, self.other_item),
            set(),
        )


class CruiseTaxFormPermissionTest(PermissionTest):
    @property
    def item(self):
        return self.form

    @property
    def other_item(self):
        # Unassociated item
        return self.form_other

    def test_admin(self):
        self._test_access(self.admin_user, self.item, "view", True)
        self._test_access(self.admin_user, self.item, "change", True)
        self._test_access(self.admin_user, self.item, "delete", True)
        self._test_access(self.admin_user, self.other_item, "view", True)
        self._test_access(self.admin_user, self.other_item, "change", True)
        self._test_access(self.admin_user, self.other_item, "delete", True)

    def test_portmanager(self):
        self._test_access(self.port_manager_user, self.item, "view", True)
        self._test_access(self.port_manager_user, self.item, "change", True)
        self._test_access(self.port_manager_user, self.item, "delete", False)
        # Portmanager may not see or change form for another port
        self._test_access(self.port_manager_user, self.other_item, "view", False)
        self._test_access(self.port_manager_user, self.other_item, "change", False)
        self._test_access(self.port_manager_user, self.other_item, "delete", False)

    def test_agent(self):
        self._test_access(self.agent_user, self.item, "view", True)
        self._test_access(self.agent_user, self.item, "change", True)
        self._test_access(self.agent_user, self.item, "delete", False)
        # Shipping agent may not see or change form for another port
        self._test_access(self.agent_user, self.other_item, "view", False)
        self._test_access(self.agent_user, self.other_item, "change", False)
        self._test_access(self.agent_user, self.other_item, "delete", False)

    def test_tax(self):
        self._test_access(self.tax_user, self.item, "view", True)
        self._test_access(self.tax_user, self.item, "change", False)
        self._test_access(self.tax_user, self.item, "delete", False)
        self._test_access(self.tax_user, self.other_item, "view", True)
        self._test_access(self.tax_user, self.other_item, "change", False)
        self._test_access(self.tax_user, self.other_item, "delete", False)

    def test_unprivileged(self):
        self._test_access(self.unprivileged_user, self.item, "view", False)
        self._test_access(self.unprivileged_user, self.item, "change", False)
        self._test_access(self.unprivileged_user, self.item, "delete", False)
        self._test_access(self.unprivileged_user, self.other_item, "view", False)
        self._test_access(self.unprivileged_user, self.other_item, "change", False)
        self._test_access(self.unprivileged_user, self.other_item, "delete", False)

    def test_inactive(self):
        self._test_access(self.inactive_user, self.item, "view", False)
        self._test_access(self.inactive_user, self.item, "change", False)
        self._test_access(self.inactive_user, self.item, "delete", False)
        self._test_access(self.inactive_user, self.other_item, "view", False)
        self._test_access(self.inactive_user, self.other_item, "change", False)
        self._test_access(self.inactive_user, self.other_item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(self.inactive_user, self.item),
            set(),
        )
        self.assertEqual(
            self.backend.get_group_permissions(self.inactive_user, self.other_item),
            set(),
        )


class PassengersByCountryPermissionTest(PermissionTest):
    @property
    def item(self):
        return self.passengers_by_country

    @property
    def other_item(self):
        # Unassociated item
        return self.passengers_by_country_other

    def test_admin(self):
        self._test_access(self.admin_user, self.item, "view", True)
        self._test_access(self.admin_user, self.item, "change", True)
        self._test_access(self.admin_user, self.item, "delete", True)
        self._test_access(self.admin_user, self.other_item, "view", True)
        self._test_access(self.admin_user, self.other_item, "change", True)
        self._test_access(self.admin_user, self.other_item, "delete", True)

    def test_portmanager(self):
        self._test_access(self.port_manager_user, self.item, "view", True)
        self._test_access(self.port_manager_user, self.item, "change", True)
        self._test_access(self.port_manager_user, self.item, "delete", False)
        # Portmanager may not see or change form for another port
        self._test_access(self.port_manager_user, self.other_item, "view", False)
        self._test_access(self.port_manager_user, self.other_item, "change", False)
        self._test_access(self.port_manager_user, self.other_item, "delete", False)

    def test_agent(self):
        self._test_access(self.agent_user, self.item, "view", True)
        self._test_access(self.agent_user, self.item, "change", True)
        self._test_access(self.agent_user, self.item, "delete", False)
        # Shipping agent may not see or change form for another port
        self._test_access(self.agent_user, self.other_item, "view", False)
        self._test_access(self.agent_user, self.other_item, "change", False)
        self._test_access(self.agent_user, self.other_item, "delete", False)

    def test_tax(self):
        self._test_access(self.tax_user, self.item, "view", True)
        self._test_access(self.tax_user, self.item, "change", False)
        self._test_access(self.tax_user, self.item, "delete", False)
        self._test_access(self.tax_user, self.other_item, "view", True)
        self._test_access(self.tax_user, self.other_item, "change", False)
        self._test_access(self.tax_user, self.other_item, "delete", False)

    def test_unprivileged(self):
        self._test_access(self.unprivileged_user, self.item, "view", False)
        self._test_access(self.unprivileged_user, self.item, "change", False)
        self._test_access(self.unprivileged_user, self.item, "delete", False)
        self._test_access(self.unprivileged_user, self.other_item, "view", False)
        self._test_access(self.unprivileged_user, self.other_item, "change", False)
        self._test_access(self.unprivileged_user, self.other_item, "delete", False)

    def test_inactive(self):
        self._test_access(self.inactive_user, self.item, "view", False)
        self._test_access(self.inactive_user, self.item, "change", False)
        self._test_access(self.inactive_user, self.item, "delete", False)
        self._test_access(self.inactive_user, self.other_item, "view", False)
        self._test_access(self.inactive_user, self.other_item, "change", False)
        self._test_access(self.inactive_user, self.other_item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(self.inactive_user, self.item),
            set(),
        )
        self.assertEqual(
            self.backend.get_group_permissions(self.inactive_user, self.other_item),
            set(),
        )


class DisembarkmentPermissionTest(PermissionTest):
    @property
    def item(self):
        return self.disembarkment

    @property
    def other_item(self):
        # Unassociated item
        return self.disembarkment_other

    def test_admin(self):
        self._test_access(self.admin_user, self.item, "view", True)
        self._test_access(self.admin_user, self.item, "change", True)
        self._test_access(self.admin_user, self.item, "delete", True)
        self._test_access(self.admin_user, self.other_item, "view", True)
        self._test_access(self.admin_user, self.other_item, "change", True)
        self._test_access(self.admin_user, self.other_item, "delete", True)

    def test_portmanager(self):
        self._test_access(self.port_manager_user, self.item, "view", True)
        self._test_access(self.port_manager_user, self.item, "change", True)
        self._test_access(self.port_manager_user, self.item, "delete", False)
        # Portmanager may not see or change form for another port
        self._test_access(self.port_manager_user, self.other_item, "view", False)
        self._test_access(self.port_manager_user, self.other_item, "change", False)
        self._test_access(self.port_manager_user, self.other_item, "delete", False)

    def test_agent(self):
        self._test_access(self.agent_user, self.item, "view", True)
        self._test_access(self.agent_user, self.item, "change", True)
        self._test_access(self.agent_user, self.item, "delete", False)
        # Shipping agent may not see or change form for another port
        self._test_access(self.agent_user, self.other_item, "view", False)
        self._test_access(self.agent_user, self.other_item, "change", False)
        self._test_access(self.agent_user, self.other_item, "delete", False)

    def test_tax(self):
        self._test_access(self.tax_user, self.item, "view", True)
        self._test_access(self.tax_user, self.item, "change", False)
        self._test_access(self.tax_user, self.item, "delete", False)
        self._test_access(self.tax_user, self.other_item, "view", True)
        self._test_access(self.tax_user, self.other_item, "change", False)
        self._test_access(self.tax_user, self.other_item, "delete", False)

    def test_unprivileged(self):
        self._test_access(self.unprivileged_user, self.item, "view", False)
        self._test_access(self.unprivileged_user, self.item, "change", False)
        self._test_access(self.unprivileged_user, self.item, "delete", False)
        self._test_access(self.unprivileged_user, self.other_item, "view", False)
        self._test_access(self.unprivileged_user, self.other_item, "change", False)
        self._test_access(self.unprivileged_user, self.other_item, "delete", False)

    def test_inactive(self):
        self._test_access(self.inactive_user, self.item, "view", False)
        self._test_access(self.inactive_user, self.item, "change", False)
        self._test_access(self.inactive_user, self.item, "delete", False)
        self._test_access(self.inactive_user, self.other_item, "view", False)
        self._test_access(self.inactive_user, self.other_item, "change", False)
        self._test_access(self.inactive_user, self.other_item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(self.inactive_user, self.item),
            set(),
        )
        self.assertEqual(
            self.backend.get_group_permissions(self.inactive_user, self.other_item),
            set(),
        )


class TaxRatesPermissionTest(PermissionTest):
    @property
    def item(self):
        return self.taxrates

    def test_admin(self):
        self._test_access(self.admin_user, self.item, "view", True)
        self._test_access(self.admin_user, self.item, "change", True)
        self._test_access(self.admin_user, self.item, "delete", True)

    def test_portmanager(self):
        self._test_access(self.port_manager_user, self.item, "view", True)
        self._test_access(self.port_manager_user, self.item, "change", False)
        self._test_access(self.port_manager_user, self.item, "delete", False)

    def test_agent(self):
        self._test_access(self.agent_user, self.item, "view", True)
        self._test_access(self.agent_user, self.item, "change", False)
        self._test_access(self.agent_user, self.item, "delete", False)

    def test_tax(self):
        self._test_access(self.tax_user, self.item, "view", True)
        self._test_access(self.tax_user, self.item, "change", True)
        self._test_access(self.tax_user, self.item, "delete", False)

    def test_unprivileged(self):
        self._test_access(self.unprivileged_user, self.item, "view", False)
        self._test_access(self.unprivileged_user, self.item, "change", False)
        self._test_access(self.unprivileged_user, self.item, "delete", False)

    def test_inactive(self):
        self._test_access(self.inactive_user, self.item, "view", False)
        self._test_access(self.inactive_user, self.item, "change", False)
        self._test_access(self.inactive_user, self.item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(self.inactive_user, self.item),
            set(),
        )


class PortTaxRatesPermissionTest(PermissionTest):
    @property
    def item(self):
        return self.port_taxrate

    def test_admin(self):
        self._test_access(self.admin_user, self.item, "view", True)
        self._test_access(self.admin_user, self.item, "change", True)
        self._test_access(self.admin_user, self.item, "delete", True)

    def test_portmanager(self):
        self._test_access(self.port_manager_user, self.item, "view", True)
        self._test_access(self.port_manager_user, self.item, "change", False)
        self._test_access(self.port_manager_user, self.item, "delete", False)

    def test_agent(self):
        self._test_access(self.agent_user, self.item, "view", True)
        self._test_access(self.agent_user, self.item, "change", False)
        self._test_access(self.agent_user, self.item, "delete", False)

    def test_tax(self):
        self._test_access(self.tax_user, self.item, "view", True)
        self._test_access(self.tax_user, self.item, "change", True)
        self._test_access(self.tax_user, self.item, "delete", False)

    def test_unprivileged(self):
        self._test_access(self.unprivileged_user, self.item, "view", False)
        self._test_access(self.unprivileged_user, self.item, "change", False)
        self._test_access(self.unprivileged_user, self.item, "delete", False)

    def test_inactive(self):
        self._test_access(self.inactive_user, self.item, "view", False)
        self._test_access(self.inactive_user, self.item, "change", False)
        self._test_access(self.inactive_user, self.item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(self.inactive_user, self.item),
            set(),
        )


class DisembarkmentTaxRatesPermissionTest(PermissionTest):
    @property
    def item(self):
        return self.disembarkment_taxrate

    def test_admin(self):
        self._test_access(self.admin_user, self.item, "view", True)
        self._test_access(self.admin_user, self.item, "change", True)
        self._test_access(self.admin_user, self.item, "delete", True)

    def test_portmanager(self):
        self._test_access(self.port_manager_user, self.item, "view", True)
        self._test_access(self.port_manager_user, self.item, "change", False)
        self._test_access(self.port_manager_user, self.item, "delete", False)

    def test_agent(self):
        self._test_access(self.agent_user, self.item, "view", True)
        self._test_access(self.agent_user, self.item, "change", False)
        self._test_access(self.agent_user, self.item, "delete", False)

    def test_tax(self):
        self._test_access(self.tax_user, self.item, "view", True)
        self._test_access(self.tax_user, self.item, "change", True)
        self._test_access(self.tax_user, self.item, "delete", False)

    def test_unprivileged(self):
        self._test_access(self.unprivileged_user, self.item, "view", False)
        self._test_access(self.unprivileged_user, self.item, "change", False)
        self._test_access(self.unprivileged_user, self.item, "delete", False)

    def test_inactive(self):
        self._test_access(self.inactive_user, self.item, "view", False)
        self._test_access(self.inactive_user, self.item, "change", False)
        self._test_access(self.inactive_user, self.item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(self.inactive_user, self.item),
            set(),
        )


class UserPermissionTest(PermissionTest):
    def test_user(self):
        # self.inactive_user does not inherit from PermissionsMixin
        self.assertEqual(
            self.backend.get_instance_permissions(
                self.admin_user, self.inactive_user, False
            ),
            set(),
        )
