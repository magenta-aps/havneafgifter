import os
from datetime import datetime, timezone

from django.contrib.auth.models import Group
from django.core.management import call_command

from havneafgifter.models import (
    CruiseTaxForm,
    HarborDuesForm,
    Nationality,
    Port,
    PortAuthority,
    ShippingAgent,
    ShipType,
    User,
)


class HarborDuesFormMixin:
    @classmethod
    def setUpTestData(cls):
        call_command("create_groups", verbosity=1)
        super().setUpTestData()

        cls._load_initial_disembarkment_sites()

        cls.port_authority = PortAuthority.objects.create(
            email="portauthority@example.org"
        )
        cls.port = Port.objects.create(
            name="Nordhavn", portauthority=cls.port_authority
        )
        cls.shipping_agent = ShippingAgent.objects.create(
            name="Agent", email="shipping@example.org"
        )

        cls.port_authority_user = User.objects.create(
            username="port_auth", port_authority=cls.port_authority
        )
        cls.port_authority_user.groups.add(Group.objects.get(name="PortAuthority"))

        cls.shipping_agent_user = User.objects.create(
            username="shipping_agent", shipping_agent=cls.shipping_agent
        )
        cls.shipping_agent_user.groups.add(Group.objects.get(name="Shipping"))

        cls.ship_user = User.objects.create(username="9074729")
        cls.ship_user.groups.add(Group.objects.get(name="Ship"))

        # Valid data for creating a `HarborDuesForm` (or `CruiseTaxForm`) instance
        cls.harbor_dues_form_data = {
            "port_of_call": cls.port,
            "nationality": Nationality.DENMARK,
            "vessel_name": "Mary",
            "vessel_owner": "Ejer",
            "vessel_master": "Mester",
            "shipping_agent": cls.shipping_agent,
            "gross_tonnage": 0,
            "vessel_type": ShipType.FREIGHTER,
            "vessel_imo": "9074729",
            "datetime_of_arrival": datetime(2020, 1, 1, tzinfo=timezone.utc),
            "datetime_of_departure": datetime(2020, 2, 1, tzinfo=timezone.utc),
        }
        # The same data, but with related objects replaced by their primary keys.
        # Suitable for testing form POSTs.
        cls.harbor_dues_form_data_pk = {
            "port_of_call": cls.port.pk,
            "shipping_agent": cls.shipping_agent.pk,
            **{
                k: v
                for k, v in cls.harbor_dues_form_data.items()
                if k not in ("port_of_call", "shipping_agent")
            },
        }

        cls.harbor_dues_form = HarborDuesForm.objects.create(
            **cls.harbor_dues_form_data
        )
        cls.cruise_tax_form = CruiseTaxForm.objects.create(**cls.harbor_dues_form_data)

    @classmethod
    def _load_initial_disembarkment_sites(cls):
        # Load 73 disembarkment sites
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures",
            "initial_disembarkment_sites.json",
        )
        call_command("loaddata", path, verbosity=0)
