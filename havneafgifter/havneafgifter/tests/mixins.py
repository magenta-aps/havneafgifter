from ..models import HarborDuesForm, Port, ShippingAgent, ShipType


class HarborDuesFormMixin:
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.port = Port.objects.create(name="Nordhavn")
        cls.shipping_agent = ShippingAgent.objects.create(name="Agent")
        cls.harbor_dues_form_data = {
            "port_of_call": cls.port,
            "nationality": HarborDuesForm.Country.DENMARK,
            "vessel_name": "Mary",
            "vessel_owner": "Ejer",
            "vessel_master": "Mester",
            "shipping_agent": cls.shipping_agent,
            "gross_tonnage": 0,
            "vessel_type": ShipType.FREIGHTER,
            "date_of_arrival": "2020-01-01",
            "date_of_departure": "2020-02-01",
        }
