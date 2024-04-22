from datetime import date
from decimal import Decimal

from django.test import TestCase

from havneafgifter.data import DateRange
from havneafgifter.models import (
    HarborDuesForm,
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
        cls.tax_rates1 = TaxRates.objects.create(
            pax_tax_rate=0,
            start_date=None,
            end_date=None,
        )
        cls.tax_rates2 = TaxRates.objects.create(
            pax_tax_rate=0,
            start_date=date(2025, 1, 1),
            end_date=None,
        )
        cls.tax_rates3 = TaxRates.objects.create(
            pax_tax_rate=0,
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
        ShippingAgent.objects.create(name="Birgers Bodega", email="birger@hotmail.com")
        cls.harborduesform1 = HarborDuesForm.objects.create(
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
        )

        cls.harborduesform2 = HarborDuesForm.objects.create(
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
