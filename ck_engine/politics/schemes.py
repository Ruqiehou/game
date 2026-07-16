from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional

from ck_engine.core import GameDate


class SchemeKind(Enum):
    MURDER = auto()
    ABDUCT = auto()
    FABRICATE_HOOK = auto()
    SWAY = auto()
    SEDUCE = auto()
    CLAIM_FABRICATION = auto()

    def name_zh(self) -> str:
        return {
            SchemeKind.MURDER: "谋杀",
            SchemeKind.ABDUCT: "绑架",
            SchemeKind.FABRICATE_HOOK: "伪造把柄",
            SchemeKind.SWAY: "拉拢",
            SchemeKind.SEDUCE: "引诱",
            SchemeKind.CLAIM_FABRICATION: "伪造宣称",
        }[self]

    def base_monthly_progress(self) -> float:
        return {
            SchemeKind.MURDER: 5.0,
            SchemeKind.ABDUCT: 4.0,
            SchemeKind.FABRICATE_HOOK: 6.0,
            SchemeKind.SWAY: 8.0,
            SchemeKind.SEDUCE: 7.0,
            SchemeKind.CLAIM_FABRICATION: 3.0,
        }[self]

    def secrecy_base(self) -> float:
        return {
            SchemeKind.MURDER: 40.0,
            SchemeKind.ABDUCT: 35.0,
            SchemeKind.FABRICATE_HOOK: 50.0,
            SchemeKind.SWAY: 80.0,
            SchemeKind.SEDUCE: 60.0,
            SchemeKind.CLAIM_FABRICATION: 70.0,
        }[self]


@dataclass
class Scheme:
    id: int
    kind: SchemeKind
    owner: int
    target: int
    progress: float = 0.0
    secrecy: float = 50.0
    agents: List[int] = field(default_factory=list)
    started: Optional[GameDate] = None
    exposed: bool = False

    def is_complete(self) -> bool:
        return self.progress >= 100.0


@dataclass
class SchemeOutcome:
    kind: str  # success / exposed / progressed
    scheme_id: int
    scheme_kind: Optional[SchemeKind] = None
    owner: int = 0
    target: int = 0
    progress: float = 0.0


@dataclass
class SchemeSystem:
    schemes: Dict[int, Scheme] = field(default_factory=dict)
    next_id: int = 1

    def start(self, kind: SchemeKind, owner: int, target: int, date: GameDate) -> int:
        sid = self.next_id
        self.next_id += 1
        self.schemes[sid] = Scheme(
            id=sid,
            kind=kind,
            owner=owner,
            target=target,
            secrecy=kind.secrecy_base(),
            started=date,
        )
        return sid

    def monthly_tick(
        self,
        intrigue_of: Dict[int, int],
        rng_roll: Callable[[], float],
    ) -> List[SchemeOutcome]:
        outcomes: List[SchemeOutcome] = []
        completed: List[int] = []
        exposed: List[int] = []
        for s in self.schemes.values():
            intrigue = float(intrigue_of.get(s.owner, 8))
            target_intrigue = float(intrigue_of.get(s.target, 8))
            gain = (
                s.kind.base_monthly_progress()
                + intrigue * 0.5
                + len(s.agents) * 2.0
                - target_intrigue * 0.2
            )
            s.progress = min(100.0, s.progress + max(0.5, gain))
            discovery = max(0.01, min(0.4, (100.0 - s.secrecy) * 0.01 + target_intrigue * 0.005))
            if rng_roll() < discovery:
                s.exposed = True
                exposed.append(s.id)
            outcomes.append(
                SchemeOutcome(
                    kind="progressed",
                    scheme_id=s.id,
                    progress=s.progress,
                    owner=s.owner,
                    target=s.target,
                )
            )
            if s.is_complete():
                completed.append(s.id)
        for sid in exposed:
            s = self.schemes.get(sid)
            if s:
                outcomes.append(
                    SchemeOutcome(
                        kind="exposed",
                        scheme_id=sid,
                        owner=s.owner,
                        target=s.target,
                        scheme_kind=s.kind,
                    )
                )
        for sid in completed:
            s = self.schemes.pop(sid, None)
            if s:
                outcomes.append(
                    SchemeOutcome(
                        kind="success",
                        scheme_id=sid,
                        scheme_kind=s.kind,
                        owner=s.owner,
                        target=s.target,
                    )
                )
        return outcomes
