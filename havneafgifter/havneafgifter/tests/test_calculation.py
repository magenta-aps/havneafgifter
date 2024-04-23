from datetime import date
from decimal import Decimal

from django.test import TestCase

from havneafgifter.data import DateRange
from havneafgifter.models import (
    CruiseTaxForm,
    Disembarkment,
    DisembarkmentSite,
    DisembarkmentTaxRate,
    HarborDuesForm,
    Municipality,
    Nationality,
    Port,
    PortTaxRate,
    ShippingAgent,
    ShipType,
    TaxRates,
)


class CalculationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Port.objects.create(name="Test1")
        Port.objects.create(name="Test2")
        DisembarkmentSite.objects.create(
            name="Klippeskær 5", municipality=Municipality.AVANNAATA
        )
        DisembarkmentSite.objects.create(
            name="Mågeø", municipality=Municipality.QEQQATA
        )
        cls.tax_rates1 = TaxRates.objects.create(
            pax_tax_rate=50,
            start_date=None,
            end_date=None,
        )
        cls.tax_rates2 = TaxRates.objects.create(
            pax_tax_rate=70,
            start_date=date(2025, 1, 1),
            end_date=None,
        )
        cls.tax_rates3 = TaxRates.objects.create(
            pax_tax_rate=90,
            start_date=date(2025, 2, 1),
            end_date=None,
        )
        cls.tax_rates1.refresh_from_db()
        cls.tax_rates2.refresh_from_db()
        cls.tax_rates3.refresh_from_db()
        cls.port_tax1 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates1,
            port=None,
            vessel_type=None,
            gt_start=0,
            gt_end=None,
            port_tax_rate=70,
        )
        cls.port_tax2 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates1,
            port=None,
            vessel_type=ShipType.CRUISE,
            gt_start=0,
            gt_end=30_000,
            port_tax_rate=110,
        )
        cls.port_tax3 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates1,
            port=None,
            vessel_type=ShipType.CRUISE,
            gt_start=30_000,
            gt_end=None,
            port_tax_rate=220,
        )
        cls.port_tax4 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates1,
            port=Port.objects.get(name="Test1"),
            vessel_type=ShipType.CRUISE,
            gt_start=0,
            gt_end=30_000,
            port_tax_rate=0,
        )
        cls.port_tax5 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates1,
            port=Port.objects.get(name="Test1"),
            vessel_type=ShipType.CRUISE,
            gt_start=30_000,
            gt_end=None,
            port_tax_rate=110,
        )

        cls.port_tax6 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates2,
            port=None,
            vessel_type=None,
            gt_start=0,
            gt_end=None,
            port_tax_rate=140,
        )
        cls.port_tax7 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates2,
            port=None,
            vessel_type=ShipType.CRUISE,
            gt_start=0,
            gt_end=30_000,
            port_tax_rate=220,
        )
        cls.port_tax8 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates2,
            port=None,
            vessel_type=ShipType.CRUISE,
            gt_start=30_000,
            gt_end=None,
            port_tax_rate=440,
        )
        cls.port_tax9 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates2,
            port=Port.objects.get(name="Test1"),
            vessel_type=ShipType.CRUISE,
            gt_start=0,
            gt_end=30_000,
            port_tax_rate=0,
        )
        cls.port_tax10 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates2,
            port=Port.objects.get(name="Test1"),
            vessel_type=ShipType.CRUISE,
            gt_start=30_000,
            gt_end=None,
            port_tax_rate=220,
        )

        cls.port_tax11 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates3,
            port=None,
            vessel_type=None,
            gt_start=0,
            gt_end=None,
            port_tax_rate=70,
        )
        cls.port_tax12 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates3,
            port=None,
            vessel_type=ShipType.CRUISE,
            gt_start=0,
            gt_end=30_000,
            port_tax_rate=110,
        )
        cls.port_tax13 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates3,
            port=None,
            vessel_type=ShipType.CRUISE,
            gt_start=30_000,
            gt_end=None,
            port_tax_rate=220,
        )
        cls.port_tax14 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates3,
            port=Port.objects.get(name="Test1"),
            vessel_type=ShipType.CRUISE,
            gt_start=0,
            gt_end=30_000,
            port_tax_rate=0,
        )
        cls.port_tax15 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates3,
            port=Port.objects.get(name="Test1"),
            vessel_type=ShipType.CRUISE,
            gt_start=30_000,
            gt_end=None,
            port_tax_rate=110,
        )
        cls.disembarkment_tax1 = DisembarkmentTaxRate.objects.create(
            tax_rates=cls.tax_rates1,
            municipality=Municipality.AVANNAATA,
            disembarkment_tax_rate=Decimal(40),
            disembarkment_site=DisembarkmentSite.objects.get(name="Klippeskær 5"),
        )
        cls.disembarkment_tax2 = DisembarkmentTaxRate.objects.create(
            tax_rates=cls.tax_rates1,
            municipality=Municipality.QEQQATA,
            disembarkment_tax_rate=Decimal(30),
            disembarkment_site=None,
        )
        ShippingAgent.objects.create(name="Birgers Bodega", email="birger@hotmail.com")
        cls.harborduesform1 = CruiseTaxForm.objects.create(
            port_of_call=Port.objects.get(name="Test1"),
            nationality=Nationality.DENMARK,
            vessel_name="Dødssejler of Luxury",
            vessel_owner="Cruises 'R' Us",
            vessel_master="Bjarne Drukkenbolt",
            shipping_agent=ShippingAgent.objects.get(name="Birgers Bodega"),
            date_of_arrival=date(2024, 12, 15),
            date_of_departure=date(2025, 2, 15),
            gross_tonnage=40_000,
            vessel_type=ShipType.CRUISE,
            number_of_passengers=100,
        )

        cls.harborduesform2 = CruiseTaxForm.objects.create(
            port_of_call=Port.objects.get(name="Test2"),
            nationality=Nationality.DENMARK,
            vessel_name="Dødssejler of Luxury",
            vessel_owner="Cruises 'R' Us",
            vessel_master="Bjarne Drukkenbolt",
            shipping_agent=ShippingAgent.objects.get(name="Birgers Bodega"),
            date_of_arrival=date(2024, 12, 15),
            date_of_departure=date(2025, 2, 15),
            gross_tonnage=40_000,
            vessel_type=ShipType.CRUISE,
            number_of_passengers=100,
        )

        cls.harborduesform3 = HarborDuesForm.objects.create(
            port_of_call=Port.objects.get(name="Test2"),
            nationality=Nationality.DENMARK,
            vessel_name="M/S Plimsoller",
            vessel_owner="Ærlige Judas",
            vessel_master="Bjarne Drukkenbolt",
            shipping_agent=ShippingAgent.objects.get(name="Birgers Bodega"),
            date_of_arrival=date(2024, 12, 15),
            date_of_departure=date(2025, 2, 15),
            gross_tonnage=50_000,
            vessel_type=ShipType.FREIGHTER,
        )

        cls.disembarkment1 = Disembarkment.objects.create(
            cruise_tax_form=cls.harborduesform1,
            number_of_passengers=10,
            disembarkment_site=DisembarkmentSite.objects.get(name="Klippeskær 5"),
        )
        cls.disembarkment2 = Disembarkment.objects.create(
            cruise_tax_form=cls.harborduesform1,
            number_of_passengers=20,
            disembarkment_site=DisembarkmentSite.objects.get(name="Mågeø"),
        )

    def test_taxrates_overlap(self):
        self.assertEqual(
            self.tax_rates1.get_overlap(
                date(2024, 12, 15), date(2024, 12, 24)
            ),  # 15. dec to 23. dec, both inclusive
            DateRange(date(2024, 12, 15), date(2024, 12, 24)),
        )
        self.assertEqual(
            self.tax_rates1.get_overlap(
                date(2024, 12, 15), date(2025, 1, 1)
            ),  # 15. dec to 31. dec, both inclusive
            DateRange(date(2024, 12, 15), date(2025, 1, 1)),
        )
        self.assertEqual(
            self.tax_rates2.get_overlap(
                date(2024, 12, 15),
                date(
                    2025, 1, 15
                ),  # Midnight, so 14 whole days. The 15th day is not included
            ),  # 1. jan to 14. jan, both inclusive
            DateRange(date(2025, 1, 1), date(2025, 1, 15)),
        )

        self.assertEqual(
            self.tax_rates2.get_overlap(
                date(2025, 1, 1), date(2025, 1, 10)
            ),  # 1. jan to 9. jan, both inclusive
            DateRange(date(2025, 1, 1), date(2025, 1, 10)),
        )
        self.assertEqual(
            self.tax_rates2.get_overlap(
                date(2025, 1, 20), date(2025, 2, 10)
            ),  # 20. jan to 31. jan, both inclusive
            DateRange(date(2025, 1, 20), date(2025, 2, 1)),
        )
        self.assertEqual(
            self.tax_rates2.get_overlap(
                date(2024, 12, 20), date(2025, 2, 10)
            ),  # 1. jan to 31. jan, both inclusive
            DateRange(date(2025, 1, 1), date(2025, 2, 1)),
        )

    def test_calculate_harbour_tax_1(self):
        calculation: dict = self.harborduesform1.calculate_harbour_tax()
        self.assertEqual(calculation["harbour_tax"], Decimal("10340.00"))
        self.assertEqual(len(calculation["details"]), 3)
        self.assertDictEqual(
            calculation["details"][0],
            {
                "port_taxrate": self.port_tax5,
                "date_range": DateRange(
                    date(2024, 12, 15), date(2025, 1, 1)
                ),  # end_date not included in range
                "harbour_tax": Decimal("1870.00"),  # 17 days * 110 kr
            },
        )
        self.assertDictEqual(
            calculation["details"][1],
            {
                "port_taxrate": self.port_tax10,
                "date_range": DateRange(date(2025, 1, 1), date(2025, 2, 1)),
                "harbour_tax": Decimal("6820.00"),  # 31 days * 220 kr
            },
        )
        self.assertDictEqual(
            calculation["details"][2],
            {
                "port_taxrate": self.port_tax15,
                "date_range": DateRange(date(2025, 2, 1), date(2025, 2, 16)),
                "harbour_tax": Decimal("1650.00"),  # 15 days * 110 kr
            },
        )
        self.harborduesform1.refresh_from_db()
        self.assertEqual(self.harborduesform1.harbour_tax, Decimal("10340.00"))

    def test_calculate_harbour_tax_2(self):
        calculation: dict = self.harborduesform2.calculate_harbour_tax()
        self.assertEqual(calculation["harbour_tax"], Decimal("20680.00"))
        self.assertEqual(len(calculation["details"]), 3)
        self.assertDictEqual(
            calculation["details"][0],
            {
                "port_taxrate": self.port_tax3,
                "date_range": DateRange(
                    date(2024, 12, 15), date(2025, 1, 1)
                ),  # end_date not included in range
                "harbour_tax": Decimal("3740.00"),  # 17 days * 220 kr
            },
        )
        self.assertDictEqual(
            calculation["details"][1],
            {
                "port_taxrate": self.port_tax8,
                "date_range": DateRange(date(2025, 1, 1), date(2025, 2, 1)),
                "harbour_tax": Decimal("13640.00"),  # 31 days * 440 kr
            },
        )
        self.assertDictEqual(
            calculation["details"][2],
            {
                "port_taxrate": self.port_tax13,
                "date_range": DateRange(date(2025, 2, 1), date(2025, 2, 16)),
                "harbour_tax": Decimal("3300.00"),  # 15 days * 220 kr
            },
        )
        self.harborduesform2.refresh_from_db()
        self.assertEqual(self.harborduesform2.harbour_tax, Decimal("20680.00"))

    def test_calculate_harbour_tax_3(self):
        calculation: dict = self.harborduesform3.calculate_harbour_tax()
        self.assertEqual(calculation["harbour_tax"], Decimal("6580.00"))
        self.assertEqual(len(calculation["details"]), 3)
        self.assertDictEqual(
            calculation["details"][0],
            {
                "port_taxrate": self.port_tax1,
                "date_range": DateRange(
                    date(2024, 12, 15), date(2025, 1, 1)
                ),  # end_date not included in range
                "harbour_tax": Decimal("1190.00"),  # 17 days * 70 kr
            },
        )
        self.assertDictEqual(
            calculation["details"][1],
            {
                "port_taxrate": self.port_tax6,
                "date_range": DateRange(date(2025, 1, 1), date(2025, 2, 1)),
                "harbour_tax": Decimal("4340.00"),  # 31 days * 140 kr
            },
        )
        self.assertDictEqual(
            calculation["details"][2],
            {
                "port_taxrate": self.port_tax11,
                "date_range": DateRange(date(2025, 2, 1), date(2025, 2, 16)),
                "harbour_tax": Decimal("1050.00"),  # 15 days * 70 kr
            },
        )
        self.harborduesform3.refresh_from_db()
        self.assertEqual(self.harborduesform3.harbour_tax, Decimal("6580.00"))

    def test_calculate_disembarkment_tax(self):
        calculation = self.harborduesform1.calculate_disembarkment_tax()
        self.assertEqual(calculation["disembarkment_tax"], Decimal("1000.00"))
        self.assertEqual(len(calculation["details"]), 2)
        self.assertDictEqual(
            calculation["details"][0],
            {
                "disembarkment": self.disembarkment1,
                "date": date(2024, 12, 15),
                "taxrate": self.disembarkment_tax1,
                "tax": Decimal("400.00"),  # 100 people * 40 kr
            },
        )
        self.assertDictEqual(
            calculation["details"][1],
            {
                "disembarkment": self.disembarkment2,
                "date": date(2024, 12, 15),
                "taxrate": self.disembarkment_tax2,
                "tax": Decimal("600.00"),  # 20 people * 30 kr
            },
        )
        self.harborduesform1.refresh_from_db()
        self.assertEqual(self.harborduesform1.disembarkment_tax, Decimal("1000.00"))

    def test_calculate_passenger_tax(self):
        calculation = self.harborduesform1.calculate_passenger_tax()
        self.assertEqual(calculation["passenger_tax"], Decimal("5000.00"))
        self.assertEqual(calculation["taxrate"], Decimal("50.00"))
