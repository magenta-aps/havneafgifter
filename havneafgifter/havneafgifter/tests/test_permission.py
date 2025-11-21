from datetime import datetime
from decimal import Decimal

from django.contrib import auth
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase

from havneafgifter.models import (
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
    Status,
    TaxRates,
    User,
)
from havneafgifter.permissions import HavneafgiftPermissionBackend


class PermissionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        current_timezone = datetime.now().astimezone().tzinfo
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
            start_datetime=datetime(2024, 1, 1, 0, 0, 0, tzinfo=current_timezone),
            end_datetime=datetime(2025, 1, 1, 0, 0, 0, tzinfo=current_timezone),
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

        # Ship user (username must be a valid IMO)
        cls.ship_user = User.objects.create(username="1234567")
        cls.ship_user.groups.add(Group.objects.get(name="Ship"))

        # Shipping agent user
        cls.agent_user = User.objects.create(
            username="agent_user", shipping_agent=cls.shipping_agent
        )
        cls.agent_user.groups.add(Group.objects.get(name="Shipping"))

        # Port authority user which can access all forms related to *all* ports managed
        # by this port authority.
        cls.port_manager_user = User.objects.create(
            username="manager", port_authority=cls.port_authority
        )
        cls.port_manager_user.groups.add(Group.objects.get(name="PortAuthority"))

        # Port authority user which can access all forms related to *all* ports managed
        # by this port authority.
        cls.port_user = User.objects.create(
            username="port",
            port_authority=cls.port_authority,
            port=cls.port,
        )
        cls.port_user.groups.add(Group.objects.get(name="PortAuthority"))

        cls.tax_user = User.objects.create(username="skattefar")
        cls.tax_user.groups.add(Group.objects.get(name="TaxAuthority"))

        cls.unprivileged_user = User.objects.create(username="trudy")
        cls.inactive_user = User.objects.create(
            username="lazy_bastard", is_active=False
        )
        cls.form = CruiseTaxForm.objects.create(
            status=Status.NEW,
            port_of_call=cls.port,
            nationality=Nationality.DENMARK,
            vessel_name="Naglfar",
            vessel_imo="1234567",
            vessel_owner="Magenta ApS",
            vessel_master="Bent Handberg",
            shipping_agent=cls.shipping_agent,
            datetime_of_arrival=datetime(2024, 5, 1, 12, 0, 0, tzinfo=current_timezone),
            datetime_of_departure=datetime(
                2024, 6, 1, 12, 0, 0, tzinfo=current_timezone
            ),
            gross_tonnage=50000,
            vessel_type=ShipType.CRUISE,
            number_of_passengers=5000,
        )
        cls.form_other = CruiseTaxForm.objects.create(
            status=Status.NEW,
            port_of_call=cls.port_other,
            nationality=Nationality.DENMARK,
            vessel_name="Naglfar",
            vessel_imo="9074729",
            vessel_owner="Magenta ApS",
            vessel_master="Bent Handberg",
            shipping_agent=cls.shipping_agent_other,
            datetime_of_arrival=datetime(2024, 5, 1, 12, 0, 0, tzinfo=current_timezone),
            datetime_of_departure=datetime(
                2024, 6, 1, 12, 0, 0, tzinfo=current_timezone
            ),
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

    def _test_access(self, user, item, action, access, specific: bool = False):
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
                f"{classname}.has_permission for user '{user}', "
                f"action '{action}' did not return True",
            )
            if not specific:
                self.assertTrue(
                    user.has_perm(perm_name, item),
                    f"User.has_perm for user '{user}' on object "
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
                f"{classname}.has_permission for user '{user}', "
                f"action '{action}' did not return False",
            )
            if not specific:
                self.assertFalse(
                    user.has_perm(perm_name, item),
                    f"User.has_perm for user '{user}' on object "
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
        user = self.admin_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", True)
        self._test_access(user, self.other_item, "delete", True)

    def test_portmanager(self):
        user = self.port_manager_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)

    def test_agent(self):
        user = self.agent_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)

    def test_tax(self):
        user = self.tax_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", True)
        self._test_access(user, self.other_item, "delete", True)

    def test_unprivileged(self):
        user = self.unprivileged_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)

    def test_inactive(self):
        user = self.inactive_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(user, self.item),
            set(),
        )
        self.assertEqual(
            self.backend.get_group_permissions(user, self.other_item),
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
        user = self.admin_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", True)
        self._test_access(user, self.other_item, "delete", True)

    def test_portmanager(self):
        user = self.port_manager_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", False)
        # Portmanager may not change portauthority for another port
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)

    def test_agent(self):
        user = self.agent_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)

    def test_tax(self):
        user = self.tax_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", True)
        self._test_access(user, self.other_item, "delete", True)

    def test_unprivileged(self):
        user = self.unprivileged_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)

    def test_inactive(self):
        user = self.inactive_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(user, self.item),
            set(),
        )
        self.assertEqual(
            self.backend.get_group_permissions(user, self.other_item),
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
        user = self.admin_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", True)
        self._test_access(user, self.other_item, "delete", True)

    def test_portmanager(self):
        user = self.port_manager_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)

    def test_agent(self):
        user = self.agent_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)

    def test_tax(self):
        user = self.tax_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", True)
        self._test_access(user, self.other_item, "delete", True)

    def test_unprivileged(self):
        user = self.unprivileged_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)

    def test_inactive(self):
        user = self.inactive_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(user, self.item),
            set(),
        )
        self.assertEqual(
            self.backend.get_group_permissions(user, self.other_item),
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
        user = self.admin_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)
        self._test_access(user, self.item, "invoice", True)
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", True)
        self._test_access(user, self.other_item, "delete", True)
        self._test_access(user, self.other_item, "invoice", True)

    def test_portmanager(self):
        user = self.port_manager_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.item, "invoice", False)
        # Portmanager may not see or change form from another port authority
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)
        self._test_access(user, self.other_item, "invoice", False)

    def test_ship(self):
        user = self.ship_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.item, "invoice", False)
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)
        self._test_access(user, self.other_item, "invoice", False)

    def test_agent(self):
        user = self.agent_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True, specific=True)
        self._test_access(user, self.item, "invoice", False)
        # Shipping agent may not see or change form for another port
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", True, specific=True)
        self._test_access(user, self.other_item, "invoice", False)

    def test_tax(self):
        user = self.tax_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)
        self._test_access(user, self.item, "invoice", False)
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", True)
        self._test_access(user, self.other_item, "delete", True)
        self._test_access(user, self.other_item, "invoice", False)

    def test_unprivileged(self):
        user = self.unprivileged_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.item, "invoice", False)
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)
        self._test_access(user, self.other_item, "invoice", False)

    def test_inactive(self):
        user = self.inactive_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.item, "invoice", False)
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)
        self._test_access(user, self.other_item, "invoice", False)
        self.assertEqual(
            self.backend.get_group_permissions(user, self.item),
            set(),
        )
        self.assertEqual(
            self.backend.get_group_permissions(user, self.other_item),
            set(),
        )

    def test_has_port_authority_permission_handles_nullable_fields(self):
        # 1. Test `User` without `PortAuthority`
        user_without_port_authority = User(port_authority=None)
        self.assertFalse(
            self.item._has_port_authority_permission(user_without_port_authority)
        )
        # 2. Test form without a port of call
        form_without_port_of_call = CruiseTaxForm(port_of_call=None)
        self.assertFalse(
            form_without_port_of_call._has_port_authority_permission(
                self.port_manager_user
            )
        )
        # 3. Test form whose port of call has no `PortAuthority`
        form_without_port_authority = CruiseTaxForm(
            port_of_call=Port(name="Port", portauthority=None)
        )
        self.assertFalse(
            form_without_port_authority._has_port_authority_permission(
                self.port_manager_user
            )
        )

    def test_has_port_authority_permission_excludes_draft(self):
        draft = CruiseTaxForm(status=Status.DRAFT, port_of_call=self.port)
        self.assertFalse(draft._has_port_authority_permission(self.port_manager_user))

    def test_get_ship_user_filter_uses_vessel_imo(self):
        # `_get_ship_user_filter` always returns a filter which filters on
        # `HarborDuesForm.vessel_imo == User.username` - in other words, ship users can
        # see all forms whose IMO match their own username.
        filter = CruiseTaxForm._get_ship_user_filter(self.ship_user)
        self.assertListEqual(filter.children, [("vessel_imo", self.ship_user.username)])


class CruiseTaxFormPortUserPermissionTest(PermissionTest):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.port_other.portauthority = cls.port_authority
        cls.port_other.save()

    @property
    def item(self):
        return self.form

    @property
    def other_item(self):
        # This form has the same port authority, but a different port than `self.item`
        return self.form_other

    def test_port_user(self):
        user = self.port_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.item, "invoice", False)
        # Port user may not see or change form from another port within the same
        # port authority.
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)
        self._test_access(user, self.other_item, "invoice", False)


class PassengersByCountryPermissionTest(PermissionTest):
    @property
    def item(self):
        return self.passengers_by_country

    @property
    def other_item(self):
        # Unassociated item
        return self.passengers_by_country_other

    def test_admin(self):
        user = self.admin_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", True)
        self._test_access(user, self.other_item, "delete", True)

    def test_portmanager(self):
        user = self.port_manager_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", False)
        # Portmanager may not see or change form for another port
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)

    def test_agent(self):
        user = self.agent_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)
        # Shipping agent may not see or change form for another port
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", True)

    def test_tax(self):
        user = self.tax_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", True)
        self._test_access(user, self.other_item, "delete", True)

    def test_unprivileged(self):
        user = self.unprivileged_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)

    def test_inactive(self):
        user = self.inactive_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(user, self.item),
            set(),
        )
        self.assertEqual(
            self.backend.get_group_permissions(user, self.other_item),
            set(),
        )


class DisembarkmentSitePermissionTest(PermissionTest):
    @property
    def item(self):
        return self.disembarkment_site

    def test_admin(self):
        user = self.admin_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)

    def test_portmanager(self):
        user = self.port_manager_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)

    def test_agent(self):
        user = self.agent_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", True)

    def test_tax(self):
        user = self.tax_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)

    def test_unprivileged(self):
        user = self.unprivileged_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)

    def test_inactive(self):
        user = self.inactive_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(user, self.item),
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
        user = self.admin_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", True)
        self._test_access(user, self.other_item, "delete", True)

    def test_portmanager(self):
        user = self.port_manager_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", False)
        # Portmanager may not see or change form for another port
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)

    def test_agent(self):
        user = self.agent_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)
        # Shipping agent may not see or change form for another port
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", True)

    def test_tax(self):
        user = self.tax_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)
        self._test_access(user, self.other_item, "view", True)
        self._test_access(user, self.other_item, "change", True)
        self._test_access(user, self.other_item, "delete", True)

    def test_unprivileged(self):
        user = self.unprivileged_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)

    def test_inactive(self):
        user = self.inactive_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self._test_access(user, self.other_item, "view", False)
        self._test_access(user, self.other_item, "change", False)
        self._test_access(user, self.other_item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(user, self.item),
            set(),
        )
        self.assertEqual(
            self.backend.get_group_permissions(user, self.other_item),
            set(),
        )


class TaxRatesPermissionTest(PermissionTest):
    @property
    def item(self):
        return self.taxrates

    def test_admin(self):
        user = self.admin_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)

    def test_portmanager(self):
        user = self.port_manager_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)

    def test_agent(self):
        user = self.agent_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)

    def test_tax(self):
        user = self.tax_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)

    def test_unprivileged(self):
        user = self.unprivileged_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)

    def test_inactive(self):
        user = self.inactive_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(user, self.item),
            set(),
        )


class PortTaxRatesPermissionTest(PermissionTest):
    @property
    def item(self):
        return self.port_taxrate

    def test_admin(self):
        user = self.admin_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)

    def test_portmanager(self):
        user = self.port_manager_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)

    def test_agent(self):
        user = self.agent_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)

    def test_tax(self):
        user = self.tax_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)

    def test_unprivileged(self):
        user = self.unprivileged_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)

    def test_inactive(self):
        user = self.inactive_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(user, self.item),
            set(),
        )


class DisembarkmentTaxRatesPermissionTest(PermissionTest):
    @property
    def item(self):
        return self.disembarkment_taxrate

    def test_admin(self):
        user = self.admin_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)

    def test_portmanager(self):
        user = self.port_manager_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)

    def test_agent(self):
        user = self.agent_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)

    def test_tax(self):
        user = self.tax_user
        self._test_access(user, self.item, "view", True)
        self._test_access(user, self.item, "change", True)
        self._test_access(user, self.item, "delete", True)

    def test_unprivileged(self):
        user = self.unprivileged_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)

    def test_inactive(self):
        user = self.inactive_user
        self._test_access(user, self.item, "view", False)
        self._test_access(user, self.item, "change", False)
        self._test_access(user, self.item, "delete", False)
        self.assertEqual(
            self.backend.get_group_permissions(user, self.item),
            set(),
        )


class UserPermissionTest(PermissionTest):
    def test_user(self):
        # user does not inherit from PermissionsMixin
        self.assertEqual(
            self.backend.get_instance_permissions(
                self.admin_user, self.inactive_user, False
            ),
            set(),
        )
