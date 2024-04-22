from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from havneafgifter.models import (
    DisembarkmentSite,
    HarborDuesForm,
    Municipality,
    Port,
    PortAuthority,
    PortTaxRate,
    ShippingAgent,
    ShipType,
    TaxRates,
    imo_validator,
)


class ModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Port.objects.create(name="Test1")
        Port.objects.create(name="Test2")
        cls.tax_rates = TaxRates.objects.create(
            pax_tax_rate=0,
            start_date=None,
            end_date=None,
        )
        cls.tax_rates2 = TaxRates.objects.create(
            pax_tax_rate=0,
            start_date=date(2025, 1, 1),
            end_date=None,
        )
        cls.tax_rates.refresh_from_db()
        cls.tax_rates2.refresh_from_db()
        PortTaxRate.objects.create(
            tax_rates=cls.tax_rates,
            port=None,
            vessel_type=None,
            gt_start=0,
            gt_end=None,
            port_tax_rate=70,
        )
        PortTaxRate.objects.create(
            tax_rates=cls.tax_rates,
            port=None,
            vessel_type=ShipType.CRUISE,
            gt_start=0,
            gt_end=30_000,
            port_tax_rate=110,
        )
        PortTaxRate.objects.create(
            tax_rates=cls.tax_rates,
            port=None,
            vessel_type=ShipType.CRUISE,
            gt_start=30_000,
            gt_end=None,
            port_tax_rate=220,
        )
        PortTaxRate.objects.create(
            tax_rates=cls.tax_rates,
            port=Port.objects.get(name="Test2"),
            vessel_type=ShipType.CRUISE,
            gt_start=0,
            gt_end=30_000,
            port_tax_rate=0,
        )
        PortTaxRate.objects.create(
            tax_rates=cls.tax_rates,
            port=Port.objects.get(name="Test2"),
            vessel_type=ShipType.CRUISE,
            gt_start=30_000,
            gt_end=None,
            port_tax_rate=110,
        )

    def test_imo_validator(self):
        with self.assertRaises(ValidationError):
            imo_validator("1234")
        with self.assertRaises(ValidationError):
            imo_validator("abcdefg")
        with self.assertRaises(ValidationError):
            imo_validator("123456A")
        with self.assertRaises(ValidationError):
            imo_validator("9074721")
        try:
            imo_validator("9074729")
        except ValidationError:
            self.fail("Got validation error on correct IMO")

    def test_get_port_tax_rate(self):
        tax_rates = TaxRates.objects.all().first()
        self.assertEqual(
            tax_rates.get_port_tax_rate(
                Port.objects.get(name="Test1"), ShipType.FREIGHTER, 40_000
            ).port_tax_rate,
            70,
        )

        self.assertEqual(
            tax_rates.get_port_tax_rate(
                Port.objects.get(name="Test1"), ShipType.CRUISE, 20_000
            ).port_tax_rate,
            110,
        )

        self.assertEqual(
            tax_rates.get_port_tax_rate(
                Port.objects.get(name="Test1"), ShipType.CRUISE, 40_000
            ).port_tax_rate,
            220,
        )

        self.assertEqual(
            tax_rates.get_port_tax_rate(
                Port.objects.get(name="Test2"), ShipType.CRUISE, 20_000
            ).port_tax_rate,
            0,
        )

        self.assertEqual(
            tax_rates.get_port_tax_rate(
                Port.objects.get(name="Test2"), ShipType.CRUISE, 40_000
            ).port_tax_rate,
            110,
        )

        self.assertEqual(
            tax_rates.get_port_tax_rate(
                Port.objects.get(name="Test2"), ShipType.PASSENGER, 40_000
            ).port_tax_rate,
            70,
        )

    def test_tax_rates_time_update(self):
        self.assertEqual(self.tax_rates.end_date, date(2025, 1, 1))

    def test_tax_rates_last_date(self):
        self.assertEqual(self.tax_rates.last_date, date(2024, 12, 31))
        self.assertIsNone(
            self.tax_rates2.last_date,
        )
        self.assertEqual(
            TaxRates(start_date=date(2025, 1, 1), end_date=date(2025, 1, 1)).last_date,
            date(2025, 1, 1),
        )


class TestShippingAgent(TestCase):
    def test_str(self):
        name = "Some name"
        instance = ShippingAgent(name=name)
        self.assertEqual(str(instance), name)


class TestPortAuthority(TestCase):
    def test_str(self):
        name = "Some name"
        instance = PortAuthority(name=name)
        self.assertEqual(str(instance), name)


class TestPort(TestCase):
    def test_str_simple(self):
        name = "Some name"
        instance = Port(name=name)
        self.assertEqual(str(instance), name)

    def test_str_complex(self):
        authority_name = "Authority name"
        port_name = "Port name"
        instance = Port(
            name=port_name,
            portauthority=PortAuthority(name=authority_name),
        )
        self.assertEqual(str(instance), f"{authority_name} - {port_name}")


class TestHarborDuesForm(TestCase):
    def test_str(self):
        instance = HarborDuesForm(
            vessel_name="Mary",
            port_of_call=Port(name="Nordhavn"),
            date_of_arrival=date(2020, 1, 1),
            date_of_departure=date(2020, 1, 31),
        )
        self.assertEqual(str(instance), "Mary, Nordhavn (2020-01-01-2020-01-31)")


class TestDisembarkmentSite(TestCase):
    def test_str(self):
        instance = DisembarkmentSite(
            name="Naturen",
            municipality=Municipality.AVANNAATA,
        )
        self.assertEqual(str(instance), "Avannaata - Naturen")
