from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional

from ck_engine.core import NONE_ID


class UnitType(Enum):
    LEVIES = auto()
    LIGHT_INFANTRY = auto()
    HEAVY_INFANTRY = auto()
    PIKEMEN = auto()
    ARCHERS = auto()
    LIGHT_CAVALRY = auto()
    HEAVY_CAVALRY = auto()
    KNIGHTS = auto()

    def damage(self) -> float:
        return {
            UnitType.LEVIES: 5.0,
            UnitType.LIGHT_INFANTRY: 8.0,
            UnitType.HEAVY_INFANTRY: 14.0,
            UnitType.PIKEMEN: 12.0,
            UnitType.ARCHERS: 10.0,
            UnitType.LIGHT_CAVALRY: 12.0,
            UnitType.HEAVY_CAVALRY: 20.0,
            UnitType.KNIGHTS: 28.0,
        }[self]

    def toughness(self) -> float:
        return {
            UnitType.LEVIES: 4.0,
            UnitType.LIGHT_INFANTRY: 6.0,
            UnitType.HEAVY_INFANTRY: 12.0,
            UnitType.PIKEMEN: 14.0,
            UnitType.ARCHERS: 5.0,
            UnitType.LIGHT_CAVALRY: 8.0,
            UnitType.HEAVY_CAVALRY: 14.0,
            UnitType.KNIGHTS: 18.0,
        }[self]

    def maintenance(self) -> float:
        return {
            UnitType.LEVIES: 0.05,
            UnitType.LIGHT_INFANTRY: 0.1,
            UnitType.HEAVY_INFANTRY: 0.25,
            UnitType.PIKEMEN: 0.2,
            UnitType.ARCHERS: 0.15,
            UnitType.LIGHT_CAVALRY: 0.3,
            UnitType.HEAVY_CAVALRY: 0.5,
            UnitType.KNIGHTS: 0.8,
        }[self]


class ArmyStatus(Enum):
    IDLE = auto()
    MOVING = auto()
    SIEGING = auto()
    IN_BATTLE = auto()
    RETREATING = auto()
    DISBANDED = auto()


@dataclass
class UnitStack:
    unit_type: UnitType
    men: int
    max_men: int

    def strength_ratio(self) -> float:
        return 0.0 if self.max_men == 0 else self.men / self.max_men

    def combat_power(self) -> float:
        return self.men * self.unit_type.damage() * self.strength_ratio()

    def take_casualties(self, amount: int) -> int:
        killed = min(self.men, amount)
        self.men -= killed
        return killed


@dataclass
class Army:
    id: int
    owner: int
    name: str
    location: int
    stacks: List[UnitStack] = field(default_factory=list)
    commander: int = NONE_ID
    path: List[int] = field(default_factory=list)
    status: ArmyStatus = ArmyStatus.IDLE
    morale: float = 100.0
    supply: float = 100.0

    def total_men(self) -> int:
        return sum(s.men for s in self.stacks)

    def combat_power(self) -> float:
        supply_mod = 0.55 + 0.45 * (max(0.0, min(100.0, self.supply)) / 100.0)
        return sum(s.combat_power() for s in self.stacks) * (self.morale / 100.0) * supply_mod

    def monthly_maintenance(self) -> float:
        return sum(s.men * s.unit_type.maintenance() for s in self.stacks)

    def is_active(self) -> bool:
        return self.status != ArmyStatus.DISBANDED and self.total_men() > 0

    def add_men(self, unit_type: UnitType, men: int) -> None:
        for s in self.stacks:
            if s.unit_type == unit_type:
                s.men += men
                s.max_men += men
                return
        self.stacks.append(UnitStack(unit_type=unit_type, men=men, max_men=men))

    def set_path(self, path: List[int]) -> None:
        self.path = path
        self.status = ArmyStatus.MOVING if path else ArmyStatus.IDLE

    def advance_move(self, move_chance: float = 1.0, rng=None) -> Optional[int]:
        """前进一格；move_chance < 1 时可能因季节/补给停滞。"""
        if not self.path:
            self.status = ArmyStatus.IDLE
            return None
        if move_chance < 1.0:
            import random as _random

            r = rng or _random
            if r.random() > move_chance:
                return None  # 本步停滞，路径保留
        nxt = self.path.pop(0)
        self.location = nxt
        if not self.path:
            self.status = ArmyStatus.IDLE
        return nxt

    def apply_supply_tick(self, in_friendly: bool, winter: bool) -> None:
        """日补给：友方恢复，敌境消耗，冬季额外损耗。"""
        from ck_engine.core.balance import (
            MORALE_DRAIN_LOW_SUPPLY,
            MORALE_RECOVER_FRIENDLY,
            SUPPLY_DRAIN_ENEMY,
            SUPPLY_DRAIN_WINTER,
            SUPPLY_LOW_THRESHOLD,
            SUPPLY_RECOVER_FRIENDLY,
        )

        if in_friendly:
            self.supply = min(100.0, self.supply + SUPPLY_RECOVER_FRIENDLY)
            self.morale = min(100.0, self.morale + MORALE_RECOVER_FRIENDLY)
        else:
            drain = SUPPLY_DRAIN_WINTER if winter else SUPPLY_DRAIN_ENEMY
            self.supply = max(0.0, self.supply - drain)
            if self.supply < SUPPLY_LOW_THRESHOLD:
                self.morale = max(5.0, self.morale - MORALE_DRAIN_LOW_SUPPLY)
            if self.supply <= 0.0 and self.stacks:
                for s in self.stacks:
                    if s.men > 0:
                        s.take_casualties(max(1, s.men // 80))
