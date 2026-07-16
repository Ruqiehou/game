from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional

from ck_engine.core import NONE_ID, AttributeSet, GameDate


class Gender(Enum):
    MALE = auto()
    FEMALE = auto()


class LifeState(Enum):
    ALIVE = auto()
    DEAD = auto()


@dataclass
class Character:
    id: int
    name: str
    dynasty: int = NONE_ID
    gender: Gender = Gender.MALE
    birth: GameDate = field(default_factory=lambda: GameDate(1066, 1, 1))
    death: Optional[GameDate] = None
    life: LifeState = LifeState.ALIVE
    base_attrs: AttributeSet = field(default_factory=AttributeSet)
    traits: List[int] = field(default_factory=list)
    culture: int = 0
    faith: int = 0
    gold: float = 50.0
    prestige: float = 50.0
    piety: float = 50.0
    stress: int = 0
    health: float = 5.0
    fertility: float = 0.5
    father: int = NONE_ID
    mother: int = NONE_ID
    spouses: List[int] = field(default_factory=list)
    children: List[int] = field(default_factory=list)
    held_titles: List[int] = field(default_factory=list)
    primary_title: int = NONE_ID
    is_ruler: bool = False
    employer: int = NONE_ID
    opinion_cache: Dict[int, int] = field(default_factory=dict)

    def age_at(self, date: GameDate) -> int:
        age = date.year - self.birth.year
        if date.month < self.birth.month or (
            date.month == self.birth.month and date.day < self.birth.day
        ):
            age -= 1
        return max(0, age)

    def is_adult(self, date: GameDate) -> bool:
        return self.age_at(date) >= 16

    def is_alive(self) -> bool:
        return self.life == LifeState.ALIVE

    def is_married(self) -> bool:
        return bool(self.spouses)

    def effective_attrs(self, trait_bonus: AttributeSet) -> AttributeSet:
        return self.base_attrs.add(trait_bonus)

    def kill(self, date: GameDate) -> None:
        self.life = LifeState.DEAD
        self.death = date
        self.is_ruler = False

    def add_gold(self, amount: float) -> None:
        self.gold = max(0.0, self.gold + amount)

    def add_prestige(self, amount: float) -> None:
        self.prestige = max(0.0, self.prestige + amount)

    def add_stress(self, amount: int) -> None:
        self.stress = max(0, min(400, self.stress + amount))
