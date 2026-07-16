from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AttributeSet:
    diplomacy: int = 8
    martial: int = 8
    stewardship: int = 8
    intrigue: int = 8
    learning: int = 8
    prowess: int = 8

    @staticmethod
    def zero() -> AttributeSet:
        return AttributeSet(0, 0, 0, 0, 0, 0)

    def add(self, other: AttributeSet) -> AttributeSet:
        return AttributeSet(
            self.diplomacy + other.diplomacy,
            self.martial + other.martial,
            self.stewardship + other.stewardship,
            self.intrigue + other.intrigue,
            self.learning + other.learning,
            self.prowess + other.prowess,
        )

    def clamp(self, lo: int = 0, hi: int = 100) -> AttributeSet:
        return AttributeSet(
            max(lo, min(hi, self.diplomacy)),
            max(lo, min(hi, self.martial)),
            max(lo, min(hi, self.stewardship)),
            max(lo, min(hi, self.intrigue)),
            max(lo, min(hi, self.learning)),
            max(lo, min(hi, self.prowess)),
        )

    def total(self) -> int:
        return (
            self.diplomacy
            + self.martial
            + self.stewardship
            + self.intrigue
            + self.learning
            + self.prowess
        )
