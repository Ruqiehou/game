from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class Season(Enum):
    SPRING = auto()
    SUMMER = auto()
    AUTUMN = auto()
    WINTER = auto()


@dataclass(order=True, frozen=True)
class GameDate:
    year: int
    month: int
    day: int

    def season(self) -> Season:
        if 3 <= self.month <= 5:
            return Season.SPRING
        if 6 <= self.month <= 8:
            return Season.SUMMER
        if 9 <= self.month <= 11:
            return Season.AUTUMN
        return Season.WINTER

    def is_leap_year(self) -> bool:
        y = self.year
        return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)

    def days_in_month(self) -> int:
        if self.month in (1, 3, 5, 7, 8, 10, 12):
            return 31
        if self.month in (4, 6, 9, 11):
            return 30
        return 29 if self.is_leap_year() else 28

    def advance_days(self, days: int) -> GameDate:
        year, month, day = self.year, self.month, self.day
        remaining = days
        while remaining > 0:
            dim = GameDate(year, month, 1).days_in_month()
            left = dim - day + 1
            if remaining < left:
                day += remaining
                break
            remaining -= left
            month += 1
            day = 1
            if month > 12:
                month = 1
                year += 1
        return GameDate(year, month, day)

    def advance_one_day(self) -> GameDate:
        return self.advance_days(1)

    def is_month_start(self) -> bool:
        return self.day == 1

    def is_year_start(self) -> bool:
        return self.month == 1 and self.day == 1

    def to_ordinal(self) -> int:
        y, m, d = self.year, self.month, self.day
        return y * 365 + y // 4 - y // 100 + y // 400 + (m - 1) * 30 + d

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}-{self.day:02d}"
