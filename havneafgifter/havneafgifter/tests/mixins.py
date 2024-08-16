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
    Status,
    User,
)


class HarborDuesFormMixin:
    @classmethod
    def setUpTestData(cls):
        call_command("create_groups", verbosity=1)
        super().setUpTestData()

        cls._load_initial_disembarkment_sites()

        cls.port_authority = PortAuthority.objects.create(
            name="Havnemyndighed 1", email="portauthority@example.org"
        )
        cls.port = Port.objects.create(
            name="Nordhavn", portauthority=cls.port_authority
        )
        cls.shipping_agent = ShippingAgent.objects.create(
            name="Agent", email="shipping@example.org"
        )

        cls.tax_authority_user = User.objects.create(
            username="tax", email="tax@example.org"
        )
        cls.tax_authority_user.groups.add(Group.objects.get(name="TaxAuthority"))
        cls.port_authority_user = User.objects.create(
            username="port_auth", port_authority=cls.port_authority
        )
        cls.port_user = User.objects.create(
            username="port_user",
            port_authority=cls.port_authority,
            port=cls.port,
        )
        for user in (cls.port_authority_user, cls.port_user):
            user.groups.add(Group.objects.get(name="PortAuthority"))

        cls.shipping_agent_user = User.objects.create(
            username="shipping_agent", shipping_agent=cls.shipping_agent
        )
        cls.shipping_agent_user.groups.add(Group.objects.get(name="Shipping"))
        cls.ship_user = User.objects.create(username="9074729", organization="Mary")
        cls.ship_user.groups.add(Group.objects.get(name="Ship"))
        cls.unprivileged_user = User.objects.create(username="unprivileged")

        # Valid data for creating a "ship user" `User` instance
        cls.ship_user_form_data = {
            "username": "1234567",  # must be valid IMO number
            "password1": "hunter2_",  # must be suitably complex
            "password2": "hunter2_",  # must be identical to `password1`
            "organization": "Skibsnavn",  # contains vessel name
            "first_name": "Fornavn",
            "last_name": "Efternavn",
            "email": "contact@example.org",
        }

        # Valid data for creating a `HarborDuesForm` (or `CruiseTaxForm`) instance
        cls.harbor_dues_form_data = {
            "port_of_call": cls.port,
            "nationality": Nationality.DENMARK.value,
            "status": Status.NEW.value,
            "vessel_name": "Mary",
            "vessel_owner": "Ejer",
            "vessel_master": "Mester",
            "shipping_agent": cls.shipping_agent,
            "gross_tonnage": 0,
            "vessel_type": ShipType.FREIGHTER.value,
            "vessel_imo": "9074729",
            "datetime_of_arrival": cls._utc_datetime(2020, 1, 1),
            "datetime_of_departure": cls._utc_datetime(2020, 2, 1),
        }
        cls.harbor_dues_form_form_data = {
            **cls.harbor_dues_form_data,
            "no_port_of_call": False,
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
        # Harbor dues form objects (NEW and DRAFT)
        cls.harbor_dues_form = HarborDuesForm.objects.create(
            **cls.harbor_dues_form_data
        )
        cls.harbor_dues_draft_form = HarborDuesForm.objects.create(
            **{k: v for k, v in cls.harbor_dues_form_data.items() if k != "status"},
        )

        # Valid data for creating a `CruiseTaxForm` instance
        cls.cruise_tax_form_data = {
            **cls.harbor_dues_form_data,
            **{"vessel_type": ShipType.CRUISE.value},
        }
        # Cruise tax form objects (NEW and DRAFT, and NEW without port of call)
        cls.cruise_tax_form = CruiseTaxForm.objects.create(**cls.cruise_tax_form_data)
        cls.cruise_tax_draft_form = CruiseTaxForm.objects.create(
            **{k: v for k, v in cls.cruise_tax_form_data.items() if k != "status"},
        )
        cls.cruise_tax_form_without_port_of_call = CruiseTaxForm.objects.create(
            **{
                k: v
                for k, v in cls.cruise_tax_form_data.items()
                if k
                not in (
                    "port_of_call",
                    "datetime_of_arrival",
                    "datetime_of_departure",
                    "gross_tonnage",
                )
            },
        )

    @classmethod
    def _utc_datetime(self, *args) -> datetime:
        return datetime(*args, tzinfo=timezone.utc)

    @classmethod
    def _load_initial_disembarkment_sites(cls):
        # Load 73 disembarkment sites
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures",
            "initial_disembarkment_sites.json",
        )
        call_command("loaddata", path, verbosity=0)
