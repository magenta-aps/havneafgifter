import os

from django.core.management import call_command

from ..models import CruiseTaxForm, HarborDuesForm, Port, ShippingAgent, ShipType


class HarborDuesFormMixin:
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls._load_initial_disembarkment_sites()

        cls.port = Port.objects.create(name="Nordhavn")
        cls.shipping_agent = ShippingAgent.objects.create(name="Agent")

        # Valid data for creating a `HarborDuesForm` (or `CruiseTaxForm`) instance
        cls.harbor_dues_form_data = {
            "port_of_call": cls.port,
            "nationality": HarborDuesForm.Country.DENMARK,
            "vessel_name": "Mary",
            "vessel_owner": "Ejer",
            "vessel_master": "Mester",
            "shipping_agent": cls.shipping_agent,
            "gross_tonnage": 0,
            "vessel_type": ShipType.FREIGHTER,
            "datetime_of_arrival": "2020-01-01",
            "datetime_of_departure": "2020-02-01",
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
