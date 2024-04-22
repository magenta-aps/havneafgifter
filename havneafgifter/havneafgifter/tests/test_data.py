from datetime import date

from django.test import TestCase

from havneafgifter.data import DateRange


class DateRangeTest(TestCase):
    def test_last_date(self):
        self.assertEqual(
            DateRange(date(2025, 1, 1), date(2025, 2, 1)).last_date, date(2025, 1, 31)
        )
        self.assertEqual(
            DateRange(date(2025, 1, 1), date(2025, 1, 1)).last_date, date(2025, 1, 1)
        )
