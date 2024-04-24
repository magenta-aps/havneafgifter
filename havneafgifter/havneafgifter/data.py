from dataclasses import dataclass
from datetime import date, datetime, timedelta


# A finite range of dates
@dataclass
class DateRange:
    start_date: date  # first day of range
    end_date: date  # first day out of range

    @property
    def last_date(self) -> date:
        last_date = self.end_date - timedelta(days=1)
        if self.start_date > last_date:
            return self.start_date
        return last_date

    @property
    def days(self) -> int:
        days: timedelta = self.end_date - self.start_date
        return days.days


# A finite range of dates
@dataclass
class DateTimeRange:
    start_datetime: datetime  # first day of range
    end_datetime: datetime  # first day out of range

    @property
    def timedelta(self) -> timedelta:
        return self.end_datetime - self.start_datetime

    @property
    def started_days(self) -> int:
        started_whole_days = (
            self.end_datetime.date() - self.start_datetime.date()
        ).days
        started_partial_day = (
            1 if self.end_datetime.time() > self.start_datetime.time() else 0
        )
        return started_whole_days + started_partial_day

    @property
    def started_weeks(self) -> int:
        delta = self.timedelta
        whole_days = delta.days
        whole_weeks = whole_days // 7
        extra_days = whole_days - (whole_weeks * 7)
        partial_day = 1 if delta.seconds > 0 else 0
        partial_week = 1 if extra_days or partial_day else 0
        return whole_weeks + partial_week
