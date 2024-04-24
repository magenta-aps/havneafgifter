from datetime import date, datetime, timezone

from django.test import TestCase

from havneafgifter.data import DateRange, DateTimeRange


class DateRangeTest(TestCase):
    def test_last_date(self):
        self.assertEqual(
            DateRange(date(2025, 1, 1), date(2025, 2, 1)).last_date, date(2025, 1, 31)
        )
        self.assertEqual(
            DateRange(date(2025, 1, 1), date(2025, 1, 1)).last_date, date(2025, 1, 1)
        )

    def test_days(self):
        self.assertEqual(DateRange(date(2025, 1, 1), date(2025, 2, 1)).days, 31)
        self.assertEqual(DateRange(date(2025, 1, 1), date(2025, 1, 1)).days, 0)


class DateTimeRangeTest(TestCase):
    def test_started_days(self):
        # Mandag formiddag til lørdag eftermiddag i samme uge
        self.assertEqual(
            DateTimeRange(
                datetime(2024, 4, 1, 8, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 6, 16, 0, 0, tzinfo=timezone.utc),
            ).started_days,
            6,
        )
        # Mandag eftermiddag til lørdag formiddag i samme uge
        self.assertEqual(
            DateTimeRange(
                datetime(2024, 4, 1, 16, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 6, 8, 0, 0, tzinfo=timezone.utc),
            ).started_days,
            5,
        )
        # Mandag formiddag til lørdag eftermiddag i ugen efter
        self.assertEqual(
            DateTimeRange(
                datetime(2024, 4, 1, 8, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 13, 16, 0, 0, tzinfo=timezone.utc),
            ).started_days,
            13,
        )
        # Mandag after til tirsdag morgen
        self.assertEqual(
            DateTimeRange(
                datetime(2024, 4, 1, 22, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 2, 8, 0, 0, tzinfo=timezone.utc),
            ).started_days,
            1,
        )

    def test_started_weeks(self):
        # Mandag til lørdag i samme uge
        self.assertEqual(
            DateTimeRange(
                datetime(2024, 4, 1, 8, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 6, 12, 0, 0, tzinfo=timezone.utc),
            ).started_weeks,
            1,
        )
        # Onsdag til tirsdag
        self.assertEqual(
            DateTimeRange(
                datetime(2024, 4, 3, 8, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
            ).started_weeks,
            1,
        )
        # Onsdag til torsdag ugen efter
        self.assertEqual(
            DateTimeRange(
                datetime(2024, 4, 3, 8, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 11, 12, 0, 0, tzinfo=timezone.utc),
            ).started_weeks,
            2,
        )
        # Mandag eftermiddag til mandag formiddag ugen efter,
        self.assertEqual(
            DateTimeRange(
                datetime(2024, 4, 1, 16, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 8, 9, 0, 0, tzinfo=timezone.utc),
            ).started_weeks,
            1,
        )
        # Mandag formiddag til mandag eftermiddag ugen efter,
        self.assertEqual(
            DateTimeRange(
                datetime(2024, 4, 1, 9, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 4, 8, 16, 0, 0, tzinfo=timezone.utc),
            ).started_weeks,
            2,
        )
