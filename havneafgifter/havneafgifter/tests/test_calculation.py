from datetime import datetime, timezone
from decimal import Decimal

from django.test import TestCase

from havneafgifter.data import DateTimeRange
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
    maxDiff = None

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
            start_datetime=None,
            end_datetime=None,
        )
        cls.tax_rates2 = TaxRates.objects.create(
            pax_tax_rate=70,
            start_datetime=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            end_datetime=None,
        )
        cls.tax_rates3 = TaxRates.objects.create(
            pax_tax_rate=90,
            start_datetime=datetime(2025, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
            end_datetime=None,
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
            port_tax_rate=Decimal("0.7"),
            round_gross_ton_up_to=70,
        )
        cls.port_tax2 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates1,
            port=None,
            vessel_type=ShipType.CRUISE,
            gt_start=0,
            gt_end=30_000,
            port_tax_rate=Decimal("1.1"),
            round_gross_ton_up_to=70,
        )
        cls.port_tax3 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates1,
            port=None,
            vessel_type=ShipType.CRUISE,
            gt_start=30_000,
            gt_end=None,
            port_tax_rate=Decimal("2.2"),
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
            port_tax_rate=Decimal("1.1"),
        )

        cls.port_tax6 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates2,
            port=None,
            vessel_type=None,
            gt_start=0,
            gt_end=None,
            port_tax_rate=Decimal("1.4"),
            round_gross_ton_up_to=70,
        )
        cls.port_tax7 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates2,
            port=None,
            vessel_type=ShipType.CRUISE,
            gt_start=0,
            gt_end=30_000,
            port_tax_rate=Decimal("2.2"),
            round_gross_ton_up_to=70,
        )
        cls.port_tax8 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates2,
            port=None,
            vessel_type=ShipType.CRUISE,
            gt_start=30_000,
            gt_end=None,
            port_tax_rate=Decimal("4.4"),
        )
        cls.port_tax9 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates2,
            port=Port.objects.get(name="Test1"),
            vessel_type=ShipType.CRUISE,
            gt_start=0,
            gt_end=30_000,
            port_tax_rate=0,
            round_gross_ton_up_to=70,
        )
        cls.port_tax10 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates2,
            port=Port.objects.get(name="Test1"),
            vessel_type=ShipType.CRUISE,
            gt_start=30_000,
            gt_end=None,
            port_tax_rate=Decimal("2.2"),
        )

        cls.port_tax11 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates3,
            port=None,
            vessel_type=None,
            gt_start=0,
            gt_end=None,
            port_tax_rate=Decimal("0.7"),
            round_gross_ton_up_to=70,
        )
        cls.port_tax12 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates3,
            port=None,
            vessel_type=ShipType.CRUISE,
            gt_start=0,
            gt_end=30_000,
            port_tax_rate=Decimal("1.1"),
            round_gross_ton_up_to=70,
        )
        cls.port_tax13 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates3,
            port=None,
            vessel_type=ShipType.CRUISE,
            gt_start=30_000,
            gt_end=None,
            port_tax_rate=Decimal("2.2"),
        )
        cls.port_tax14 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates3,
            port=Port.objects.get(name="Test1"),
            vessel_type=ShipType.CRUISE,
            gt_start=0,
            gt_end=30_000,
            port_tax_rate=0,
            round_gross_ton_up_to=70,
        )
        cls.port_tax15 = PortTaxRate.objects.create(
            tax_rates=cls.tax_rates3,
            port=Port.objects.get(name="Test1"),
            vessel_type=ShipType.CRUISE,
            gt_start=30_000,
            gt_end=None,
            port_tax_rate=Decimal("1.1"),
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
            datetime_of_arrival=datetime(2024, 12, 15, 8, 0, 0, tzinfo=timezone.utc),
            datetime_of_departure=datetime(2025, 2, 15, 16, 0, 0, tzinfo=timezone.utc),
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
            datetime_of_arrival=datetime(2024, 12, 15, 8, 0, 0, tzinfo=timezone.utc),
            datetime_of_departure=datetime(2025, 2, 15, 16, 0, 0, tzinfo=timezone.utc),
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
            datetime_of_arrival=datetime(2024, 12, 15, 8, 0, 0, tzinfo=timezone.utc),
            datetime_of_departure=datetime(2025, 2, 15, 16, 0, 0, tzinfo=timezone.utc),
            gross_tonnage=50_000,
            vessel_type=ShipType.FREIGHTER,
        )

        cls.harborduesform4 = HarborDuesForm.objects.create(
            port_of_call=Port.objects.get(name="Test2"),
            nationality=Nationality.DENMARK,
            vessel_name="M/S Baljen",
            vessel_owner="Kaj Fisher",
            vessel_master="Kaj Fisher",
            shipping_agent=None,
            # Lige lidt over en uge
            datetime_of_arrival=datetime(2025, 4, 17, 8, 0, 0, tzinfo=timezone.utc),
            datetime_of_departure=datetime(2025, 4, 24, 16, 0, 0, tzinfo=timezone.utc),
            gross_tonnage=10,
            vessel_type=ShipType.FISHER,
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
                datetime(2024, 12, 15, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 12, 24, 0, 0, 0, tzinfo=timezone.utc),
            ),  # 15. dec to 23. dec, both inclusive
            DateTimeRange(
                datetime(2024, 12, 15, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 12, 24, 0, 0, 0, tzinfo=timezone.utc),
            ),
        )
        self.assertEqual(
            self.tax_rates1.get_overlap(
                datetime(2024, 12, 15, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            ),  # 15. dec to 31. dec, both inclusive
            DateTimeRange(
                datetime(2024, 12, 15, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            ),
        )
        self.assertEqual(
            self.tax_rates2.get_overlap(
                datetime(2024, 12, 15, 0, 0, 0, tzinfo=timezone.utc),
                datetime(
                    2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc
                ),  # Midnight, so 14 whole days. The 15th day is not included
            ),  # 1. jan to 14. jan, both inclusive
            DateTimeRange(
                datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
            ),
        )

        self.assertEqual(
            self.tax_rates2.get_overlap(
                datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 10, 0, 0, 0, tzinfo=timezone.utc),
            ),  # 1. jan to 9. jan, both inclusive
            DateTimeRange(
                datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 1, 10, 0, 0, 0, tzinfo=timezone.utc),
            ),
        )
        self.assertEqual(
            self.tax_rates2.get_overlap(
                datetime(2025, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 2, 10, 0, 0, 0, tzinfo=timezone.utc),
            ),  # 20. jan to 31. jan, both inclusive
            DateTimeRange(
                datetime(2025, 1, 20, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
            ),
        )
        self.assertEqual(
            self.tax_rates2.get_overlap(
                datetime(2024, 12, 20, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 2, 10, 0, 0, 0, tzinfo=timezone.utc),
            ),  # 1. jan to 31. jan, both inclusive
            DateTimeRange(
                datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
            ),
        )

    def test_calculate_harbour_tax_1(self):
        calculation: dict = self.harborduesform1.calculate_harbour_tax()
        self.assertEqual(calculation["harbour_tax"], Decimal("4136000.00"))
        self.assertEqual(len(calculation["details"]), 3)
        self.assertDictEqual(
            calculation["details"][0],
            {
                "port_taxrate": self.port_tax5,
                "date_range": DateTimeRange(
                    datetime(2024, 12, 15, 8, 0, 0, tzinfo=timezone.utc),
                    datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                ),  # end_date not included in range
                "harbour_tax": Decimal("748000.00"),  # 17 days * 40000 tons * 1.10 kr
            },
        )
        self.assertDictEqual(
            calculation["details"][1],
            {
                "port_taxrate": self.port_tax10,
                "date_range": DateTimeRange(
                    datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                    datetime(2025, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
                ),
                "harbour_tax": Decimal("2728000.00"),  # 31 days * 40000 tons * 2.20 kr
            },
        )
        self.assertDictEqual(
            calculation["details"][2],
            {
                "port_taxrate": self.port_tax15,
                "date_range": DateTimeRange(
                    datetime(2025, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
                    datetime(2025, 2, 15, 16, 0, 0, tzinfo=timezone.utc),
                ),
                "harbour_tax": Decimal("660000.00"),  # 15 days * 40000 tons * 1.10 kr
            },
        )
        self.harborduesform1.refresh_from_db()
        self.assertEqual(self.harborduesform1.harbour_tax, Decimal("4136000.00"))

    def test_calculate_harbour_tax_2(self):
        calculation: dict = self.harborduesform2.calculate_harbour_tax()
        self.assertEqual(calculation["harbour_tax"], Decimal("8272000.00"))
        self.assertEqual(len(calculation["details"]), 3)
        self.assertDictEqual(
            calculation["details"][0],
            {
                "port_taxrate": self.port_tax3,
                "date_range": DateTimeRange(
                    datetime(2024, 12, 15, 8, 0, 0, tzinfo=timezone.utc),
                    datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                ),  # end_date not included in range
                "harbour_tax": Decimal("1496000.00"),  # 17 days * 40000 tons * 2.20 kr
            },
        )
        self.assertDictEqual(
            calculation["details"][1],
            {
                "port_taxrate": self.port_tax8,
                "date_range": DateTimeRange(
                    datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                    datetime(2025, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
                ),
                "harbour_tax": Decimal("5456000.00"),  # 31 days * 40000 tons * 4.40 kr
            },
        )
        self.assertDictEqual(
            calculation["details"][2],
            {
                "port_taxrate": self.port_tax13,
                "date_range": DateTimeRange(
                    datetime(2025, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
                    datetime(2025, 2, 15, 16, 0, 0, tzinfo=timezone.utc),
                ),
                "harbour_tax": Decimal("1320000.00"),  # 15 days * 40000 tons * 2.20 kr
            },
        )
        self.harborduesform2.refresh_from_db()
        self.assertEqual(self.harborduesform2.harbour_tax, Decimal("8272000.00"))

    def test_calculate_harbour_tax_3(self):
        calculation: dict = self.harborduesform3.calculate_harbour_tax()
        self.assertEqual(calculation["harbour_tax"], Decimal("560000.00"))
        self.assertEqual(len(calculation["details"]), 3)
        self.assertDictEqual(
            calculation["details"][0],
            {
                "port_taxrate": self.port_tax1,
                "date_range": DateTimeRange(
                    datetime(2024, 12, 15, 8, 0, 0, tzinfo=timezone.utc),
                    datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                ),  # end_date not included in range
                "harbour_tax": Decimal("105000"),  # 3 weeks * 50000 tons * 0.70 kr
            },
        )
        self.assertDictEqual(
            calculation["details"][1],
            {
                "port_taxrate": self.port_tax6,
                "date_range": DateTimeRange(
                    datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                    datetime(2025, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
                ),
                "harbour_tax": Decimal("350000.00"),  # 5 weeks * 50000 tons * 1.40 kr
            },
        )
        self.assertDictEqual(
            calculation["details"][2],
            {
                "port_taxrate": self.port_tax11,
                "date_range": DateTimeRange(
                    datetime(2025, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
                    datetime(2025, 2, 15, 16, 0, 0, tzinfo=timezone.utc),
                ),
                "harbour_tax": Decimal("105000.00"),  # 3 weeks * 50000 tons * 0.70 kr
            },
        )
        self.harborduesform3.refresh_from_db()
        self.assertEqual(self.harborduesform3.harbour_tax, Decimal("560000.00"))

    def test_calculate_harbor_tax4(self):
        calculation: dict = self.harborduesform4.calculate_harbour_tax()
        print(calculation)
        self.assertEqual(
            calculation["harbour_tax"], Decimal("392.00")
        )  # 8 days * 10 tons (round up to 70) * 0.70
        self.assertEqual(len(calculation["details"]), 1)
        self.assertEqual(
            calculation["details"][0],
            {
                "port_taxrate": self.port_tax11,
                "date_range": DateTimeRange(
                    start_datetime=datetime(2025, 4, 17, 8, 0, 0, tzinfo=timezone.utc),
                    end_datetime=datetime(2025, 4, 24, 16, 0, 0, tzinfo=timezone.utc),
                ),
                "harbour_tax": Decimal(
                    "392.00"
                ),  # 8 days * 10 tons (round up to 70) * 0.70
            },
        )

    def test_calculate_disembarkment_tax(self):
        calculation = self.harborduesform1.calculate_disembarkment_tax()
        self.assertEqual(calculation["disembarkment_tax"], Decimal("1000.00"))
        self.assertEqual(len(calculation["details"]), 2)
        self.assertDictEqual(
            calculation["details"][0],
            {
                "disembarkment": self.disembarkment2,
                "date": datetime(2024, 12, 15, 8, 0, 0, tzinfo=timezone.utc),
                "taxrate": self.disembarkment_tax2,
                "tax": Decimal("600.00"),  # 20 people * 30 kr
            },
        )
        self.assertDictEqual(
            calculation["details"][1],
            {
                "disembarkment": self.disembarkment1,
                "date": datetime(2024, 12, 15, 8, 0, 0, tzinfo=timezone.utc),
                "taxrate": self.disembarkment_tax1,
                "tax": Decimal("400.00"),  # 100 people * 40 kr
            },
        )
        self.harborduesform1.refresh_from_db()
        self.assertEqual(self.harborduesform1.disembarkment_tax, Decimal("1000.00"))

    def test_calculate_passenger_tax(self):
        calculation = self.harborduesform1.calculate_passenger_tax()
        self.assertEqual(calculation["passenger_tax"], Decimal("5000.00"))
        self.assertEqual(calculation["taxrate"], Decimal("50.00"))

    def test_calculate_taxes_for_cruise_ships_without_port_of_call(self):
        # Arrange: create object where nullable fields are not set
        instance = CruiseTaxForm(
            vessel_type=ShipType.CRUISE,
            port_of_call=None,
            gross_tonnage=None,
            datetime_of_arrival=None,
            datetime_of_departure=None,
            number_of_passengers=None,
        )
        # Arrange: populate `instance.date`, which is used as fallback value in
        # `calculate_disembarkment_tax`.
        instance.save()
        # Arrange: add disembarkments to this cruise tax form
        Disembarkment.objects.create(
            cruise_tax_form=instance,
            disembarkment_site=DisembarkmentSite.objects.first(),
            number_of_passengers=10,
        )
        # Act: calculate all three taxes and refresh object from DB
        instance.calculate_tax()
        instance.refresh_from_db()
        # Assert no harbour tax or pax tax is due
        self.assertIsNone(instance.harbour_tax)
        self.assertIsNone(instance.pax_tax)
        # Assert that disembarkment tax is due (10 passengers * 30 DKK == 300 DKK)
        self.assertEqual(instance.disembarkment_tax, Decimal("300"))
