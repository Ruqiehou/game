from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Iterable, List, Optional

from ck_engine.core import NONE_ID, GameDate
from ck_engine.military.army import Army, ArmyStatus, UnitType
from ck_engine.politics.diplomacy import CasusBelli


@dataclass
class WarParticipant:
    character: int
    is_attacker: bool
    joined: GameDate
    contribution: float = 0.0


class WarResult(Enum):
    ATTACKER_VICTORY = auto()
    DEFENDER_VICTORY = auto()
    WHITE_PEACE = auto()
    ONGOING = auto()


@dataclass
class War:
    id: int
    name: str
    cb: CasusBelli
    attacker_primary: int
    defender_primary: int
    start: GameDate
    participants: List[WarParticipant] = field(default_factory=list)
    warscore: int = 0
    active: bool = True
    result: WarResult = WarResult.ONGOING
    target_title: int = NONE_ID

    def involves(self, who: int) -> bool:
        return any(p.character == who for p in self.participants)

    def is_attacker(self, who: int) -> bool:
        return any(p.character == who and p.is_attacker for p in self.participants)

    def apply_warscore(self, delta: int) -> None:
        self.warscore = max(-100, min(100, self.warscore + delta))

    def can_enforce(self) -> bool:
        return self.warscore >= self.cb.warscore_goal()

    def can_surrender(self) -> bool:
        return self.warscore <= -self.cb.warscore_goal()

    def months_elapsed(self, now: GameDate) -> int:
        return max(0, (now.to_ordinal() - self.start.to_ordinal()) // 30)

    def can_white_peace(self, now: GameDate, atk_exh: float = 0.0, def_exh: float = 0.0) -> bool:
        """僵持或双方战争疲劳过高时可白和。"""
        from ck_engine.core.balance import (
            WHITE_PEACE_FATIGUE_SCORE,
            WHITE_PEACE_FATIGUE_THRESHOLD,
            WHITE_PEACE_MAX_MONTHS,
            WHITE_PEACE_MAX_SCORE,
            WHITE_PEACE_MIN_MONTHS,
            WHITE_PEACE_STALEMATE_MONTHS,
            WHITE_PEACE_STALEMATE_SCORE,
        )

        months = self.months_elapsed(now)
        if months < WHITE_PEACE_MIN_MONTHS:
            return False
        if abs(self.warscore) <= WHITE_PEACE_STALEMATE_SCORE and months >= WHITE_PEACE_STALEMATE_MONTHS:
            return True
        if (
            abs(self.warscore) <= WHITE_PEACE_FATIGUE_SCORE
            and atk_exh >= WHITE_PEACE_FATIGUE_THRESHOLD
            and def_exh >= WHITE_PEACE_FATIGUE_THRESHOLD
        ):
            return True
        if months >= WHITE_PEACE_MAX_MONTHS and abs(self.warscore) < WHITE_PEACE_MAX_SCORE:
            return True
        return False


@dataclass
class WarManager:
    wars: Dict[int, War] = field(default_factory=dict)
    armies: Dict[int, Army] = field(default_factory=dict)
    next_war: int = 1
    next_army: int = 1

    def declare_war(
        self,
        cb: CasusBelli,
        attacker: int,
        defender: int,
        date: GameDate,
        name: str,
        target_title: int = NONE_ID,
    ) -> int:
        wid = self.next_war
        self.next_war += 1
        war = War(
            id=wid,
            name=name,
            cb=cb,
            attacker_primary=attacker,
            defender_primary=defender,
            start=date,
            target_title=target_title,
            participants=[
                WarParticipant(character=attacker, is_attacker=True, joined=date),
                WarParticipant(character=defender, is_attacker=False, joined=date),
            ],
        )
        self.wars[wid] = war
        return wid

    def war(self, wid: int) -> Optional[War]:
        return self.wars.get(wid)

    def active_wars(self) -> Iterable[War]:
        return (w for w in self.wars.values() if w.active)

    def end_war(self, wid: int, result: WarResult) -> None:
        w = self.wars.get(wid)
        if not w:
            return
        w.active = False
        w.result = result

    def raise_army(self, owner: int, location: int, levies: int, name: str = "") -> int:
        aid = self.next_army
        self.next_army += 1
        army = Army(
            id=aid,
            owner=owner,
            name=name or f"军团#{aid}",
            location=location,
            commander=owner,
        )
        army.add_men(UnitType.LEVIES, levies)
        self.armies[aid] = army
        return aid

    def army(self, aid: int) -> Optional[Army]:
        return self.armies.get(aid)

    def armies_of(self, owner: int) -> List[int]:
        return [a.id for a in self.armies.values() if a.owner == owner and a.is_active()]

    def total_men_of(self, owner: int) -> int:
        return sum(a.total_men() for a in self.armies.values() if a.owner == owner and a.is_active())

    def tick_movement(self, move_chance_of=None) -> None:
        """move_chance_of: Optional[Callable[[Army], float]] 按军队返回移动成功率。"""
        for army in self.armies.values():
            if army.status == ArmyStatus.MOVING:
                chance = 1.0 if move_chance_of is None else float(move_chance_of(army))
                army.advance_move(move_chance=chance)

    def disband_empty(self) -> None:
        for army in self.armies.values():
            if army.total_men() <= 0:
                army.status = ArmyStatus.DISBANDED
