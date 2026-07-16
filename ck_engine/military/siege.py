from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ck_engine.core import GameDate


@dataclass
class Siege:
    id: int
    county: int
    attacker_army: int
    attacker: int
    defender: int
    progress: float = 0.0
    fort_level: int = 1
    garrison: int = 50
    started: Optional[GameDate] = None
    active: bool = True

    def required_progress(self) -> float:
        return 100.0 + self.fort_level * 40.0

    def is_complete(self) -> bool:
        return self.progress >= self.required_progress()

    def daily_tick(self, besieger_men: int, martial: int) -> float:
        if not self.active:
            return 0.0
        men_factor = max(0.2, min(3.0, besieger_men / max(50, self.garrison)))
        fort_penalty = 1.0 / (1.0 + self.fort_level * 0.25)
        martial_bonus = 1.0 + (martial - 8) * 0.03
        gain = 1.2 * men_factor * fort_penalty * martial_bonus
        self.progress = min(self.required_progress(), self.progress + gain)
        return gain


@dataclass
class SiegeEvent:
    kind: str  # progressed / captured / lifted
    siege_id: int
    county: int
    attacker: int = 0
    defender: int = 0
    progress: float = 0.0
    required: float = 0.0
    reason: str = ""


@dataclass
class SiegeManager:
    sieges: Dict[int, Siege] = field(default_factory=dict)
    next_id: int = 1

    def start(
        self,
        county: int,
        attacker_army: int,
        attacker: int,
        defender: int,
        fort_level: int,
        garrison: int,
        date: GameDate,
    ) -> int:
        for s in self.sieges.values():
            if s.active and s.county == county:
                return s.id
        sid = self.next_id
        self.next_id += 1
        self.sieges[sid] = Siege(
            id=sid,
            county=county,
            attacker_army=attacker_army,
            attacker=attacker,
            defender=defender,
            fort_level=fort_level,
            garrison=garrison,
            started=date,
        )
        return sid

    def active_at(self, county: int) -> Optional[Siege]:
        for s in self.sieges.values():
            if s.active and s.county == county:
                return s
        return None

    def active_sieges(self):
        return (s for s in self.sieges.values() if s.active)

    def tick_day(
        self,
        army_men: Dict[int, int],
        army_martial: Dict[int, int],
        army_location: Dict[int, int],
    ) -> List[SiegeEvent]:
        events: List[SiegeEvent] = []
        completed: List[int] = []
        for s in self.sieges.values():
            if not s.active:
                continue
            loc = army_location.get(s.attacker_army)
            men = army_men.get(s.attacker_army, 0)
            if loc != s.county or men <= 0:
                s.active = False
                events.append(
                    SiegeEvent(
                        kind="lifted",
                        siege_id=s.id,
                        county=s.county,
                        reason="攻城部队离开或溃散",
                    )
                )
                continue
            martial = army_martial.get(s.attacker_army, 8)
            s.daily_tick(men, martial)
            events.append(
                SiegeEvent(
                    kind="progressed",
                    siege_id=s.id,
                    county=s.county,
                    progress=s.progress,
                    required=s.required_progress(),
                )
            )
            if s.is_complete():
                completed.append(s.id)
        for sid in completed:
            s = self.sieges[sid]
            s.active = False
            events.append(
                SiegeEvent(
                    kind="captured",
                    siege_id=sid,
                    county=s.county,
                    attacker=s.attacker,
                    defender=s.defender,
                )
            )
        return events
