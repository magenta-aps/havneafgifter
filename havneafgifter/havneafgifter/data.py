from dataclasses import dataclass
from datetime import date, timedelta


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
