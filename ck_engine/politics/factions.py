from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional


class FactionKind(Enum):
    INDEPENDENCE = auto()
    LOWER_CROWN_AUTHORITY = auto()
    CLAIMANT = auto()
    LIBERTY = auto()
    POPULAR = auto()

    def name_zh(self) -> str:
        return {
            FactionKind.INDEPENDENCE: "独立派系",
            FactionKind.LOWER_CROWN_AUTHORITY: "降低王权派系",
            FactionKind.CLAIMANT: "拥立派系",
            FactionKind.LIBERTY: "自由派系",
            FactionKind.POPULAR: "民变派系",
        }[self]

    def ultimatum_text(self) -> str:
        return {
            FactionKind.INDEPENDENCE: "要求独立",
            FactionKind.LOWER_CROWN_AUTHORITY: "要求降低王权",
            FactionKind.CLAIMANT: "要求更换君主",
            FactionKind.LIBERTY: "要求恢复自由权利",
            FactionKind.POPULAR: "要求改革苛政",
        }[self]


@dataclass
class Faction:
    id: int
    kind: FactionKind
    target_liege: int
    members: List[int] = field(default_factory=list)
    power: float = 0.0
    discontent: float = 0.0
    ultimatum_sent: bool = False
    claimant: Optional[int] = None

    def add_member(self, who: int) -> None:
        if who not in self.members:
            self.members.append(who)

    def remove_member(self, who: int) -> None:
        if who in self.members:
            self.members.remove(who)

    def is_ready_to_revolt(self) -> bool:
        return self.power >= 80 and self.discontent >= 50 and len(self.members) >= 2

    def can_send_ultimatum(self) -> bool:
        return (
            self.power >= 60
            and self.discontent >= 40
            and not self.ultimatum_sent
            and len(self.members) >= 2
        )


@dataclass
class FactionEvent:
    kind: str
    faction_id: int
    liege: int = 0
    founder: int = 0
    who: int = 0
    faction_kind: Optional[FactionKind] = None
    members: List[int] = field(default_factory=list)
    reason: str = ""


@dataclass
class FactionSystem:
    factions: Dict[int, Faction] = field(default_factory=dict)
    next_id: int = 1

    def create(self, kind: FactionKind, liege: int, claimant: Optional[int] = None) -> int:
        fid = self.next_id
        self.next_id += 1
        self.factions[fid] = Faction(
            id=fid, kind=kind, target_liege=liege, claimant=claimant
        )
        return fid

    def join(self, faction_id: int, who: int) -> None:
        f = self.factions.get(faction_id)
        if f:
            f.add_member(who)

    def leave(self, faction_id: int, who: int) -> None:
        f = self.factions.get(faction_id)
        if f:
            f.remove_member(who)

    def dissolve(self, faction_id: int) -> None:
        self.factions.pop(faction_id, None)

    def find_for_liege(self, liege: int, kind: FactionKind) -> Optional[int]:
        for f in self.factions.values():
            if f.target_liege == liege and f.kind == kind:
                return f.id
        return None

    def recompute_power(
        self, military_power: Dict[int, float], liege_power: Dict[int, float]
    ) -> None:
        for f in self.factions.values():
            member_power = sum(military_power.get(m, 10.0) for m in f.members)
            lp = max(1.0, liege_power.get(f.target_liege, 100.0))
            f.power = min(200.0, member_power / lp * 100.0)

    def tick_discontent(self, opinion_of_liege: Dict[int, int]) -> None:
        for f in self.factions.values():
            if not f.members:
                avg = 0.0
            else:
                avg = sum(opinion_of_liege.get(m, 0) for m in f.members) / len(f.members)
            if avg < 0:
                f.discontent = min(100.0, f.discontent + (-avg) * 0.15)
            else:
                f.discontent = max(0.0, f.discontent - avg * 0.08)
            if len(f.members) < 2:
                f.discontent = max(0.0, f.discontent - 5.0)

    def monthly_ai(
        self,
        vassals: List[tuple],  # (vassal, liege, opinion)
        rng_roll: Callable[[], float],
    ) -> List[FactionEvent]:
        events: List[FactionEvent] = []
        for vassal, liege, opinion in vassals:
            if opinion > -10:
                leave_ids = [
                    f.id
                    for f in self.factions.values()
                    if f.target_liege == liege and vassal in f.members
                ]
                for fid in leave_ids:
                    self.leave(fid, vassal)
                continue
            if rng_roll() > 0.25:
                continue
            if opinion < -50:
                kind = FactionKind.INDEPENDENCE
            elif opinion < -30:
                kind = FactionKind.LOWER_CROWN_AUTHORITY
            else:
                kind = FactionKind.LIBERTY
            fid = self.find_for_liege(liege, kind)
            if fid is not None:
                f = self.factions[fid]
                if vassal not in f.members:
                    self.join(fid, vassal)
                    events.append(
                        FactionEvent(kind="joined", faction_id=fid, who=vassal, liege=liege)
                    )
            elif rng_roll() < 0.4:
                fid = self.create(kind, liege)
                self.join(fid, vassal)
                events.append(
                    FactionEvent(
                        kind="formed",
                        faction_id=fid,
                        founder=vassal,
                        liege=liege,
                        faction_kind=kind,
                    )
                )

        empty = [f.id for f in self.factions.values() if not f.members]
        for fid in empty:
            self.dissolve(fid)
            events.append(
                FactionEvent(kind="dissolved", faction_id=fid, reason="无人支持")
            )

        for f in list(self.factions.values()):
            if f.can_send_ultimatum():
                f.ultimatum_sent = True
                events.append(
                    FactionEvent(
                        kind="ultimatum",
                        faction_id=f.id,
                        liege=f.target_liege,
                        faction_kind=f.kind,
                        members=list(f.members),
                    )
                )
            elif f.is_ready_to_revolt():
                events.append(
                    FactionEvent(
                        kind="revolt",
                        faction_id=f.id,
                        liege=f.target_liege,
                        faction_kind=f.kind,
                        members=list(f.members),
                    )
                )
        return events
