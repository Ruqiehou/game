from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

from ck_engine.core import GameDate


class CasusBelli(Enum):
    CLAIM = auto()
    CONQUEST = auto()
    INDEPENDENCE = auto()
    DEPOSE_LIEGE = auto()
    HOLY_WAR = auto()
    DE_JURE = auto()
    RIVALRY = auto()
    SUBJUGATION = auto()

    def name_zh(self) -> str:
        return {
            CasusBelli.CLAIM: "宣称战争",
            CasusBelli.CONQUEST: "征服",
            CasusBelli.INDEPENDENCE: "独立战争",
            CasusBelli.DEPOSE_LIEGE: "废黜领主",
            CasusBelli.HOLY_WAR: "圣战",
            CasusBelli.DE_JURE: "法理战争",
            CasusBelli.RIVALRY: "世仇战争",
            CasusBelli.SUBJUGATION: "臣服战争",
        }[self]

    def warscore_goal(self) -> int:
        return 80 if self == CasusBelli.CONQUEST else 100

    def prestige_cost(self) -> float:
        return {
            CasusBelli.CLAIM: 50.0,
            CasusBelli.CONQUEST: 100.0,
            CasusBelli.INDEPENDENCE: 0.0,
            CasusBelli.DEPOSE_LIEGE: 150.0,
            CasusBelli.HOLY_WAR: 0.0,
            CasusBelli.DE_JURE: 75.0,
            CasusBelli.RIVALRY: 25.0,
            CasusBelli.SUBJUGATION: 200.0,
        }[self]

    def attacker_prestige_on_win(self) -> float:
        return {
            CasusBelli.CLAIM: 50.0,
            CasusBelli.CONQUEST: 80.0,
            CasusBelli.INDEPENDENCE: 100.0,
            CasusBelli.DEPOSE_LIEGE: 120.0,
            CasusBelli.HOLY_WAR: 150.0,
            CasusBelli.DE_JURE: 60.0,
            CasusBelli.RIVALRY: 40.0,
            CasusBelli.SUBJUGATION: 200.0,
        }[self]


@dataclass
class RelationFlags:
    allied: bool = False
    at_war: bool = False
    non_aggression: bool = False
    rival: bool = False
    marriage_pact: bool = False

    def blocks_war(self) -> bool:
        return self.allied or self.non_aggression or self.marriage_pact


class TreatyKind(Enum):
    ALLIANCE = auto()
    NON_AGGRESSION = auto()
    MARRIAGE_PACT = auto()
    TRUCE = auto()

    def name_zh(self) -> str:
        return {
            TreatyKind.ALLIANCE: "同盟",
            TreatyKind.NON_AGGRESSION: "互不侵犯",
            TreatyKind.MARRIAGE_PACT: "联姻协定",
            TreatyKind.TRUCE: "停战",
        }[self]


@dataclass
class Treaty:
    a: int
    b: int
    kind: TreatyKind
    start: GameDate
    expires_year: int


@dataclass
class Claim:
    claimant: int
    title: int
    county: Optional[int] = None
    pressed: bool = False
    strength: int = 50


@dataclass
class DiplomacySystem:
    relations: Dict[Tuple[int, int], RelationFlags] = field(default_factory=dict)
    treaties: List[Treaty] = field(default_factory=list)
    claims: Dict[int, List[Claim]] = field(default_factory=dict)
    truce_until: Dict[Tuple[int, int], int] = field(default_factory=dict)
    war_exhaustion: Dict[int, float] = field(default_factory=dict)

    @staticmethod
    def pair_key(a: int, b: int) -> Tuple[int, int]:
        return (a, b) if a < b else (b, a)

    def flags(self, a: int, b: int) -> RelationFlags:
        return self.relations.get(self.pair_key(a, b), RelationFlags())

    def flags_mut(self, a: int, b: int) -> RelationFlags:
        key = self.pair_key(a, b)
        if key not in self.relations:
            self.relations[key] = RelationFlags()
        return self.relations[key]

    def form_alliance(self, a: int, b: int, date: GameDate) -> None:
        f = self.flags_mut(a, b)
        f.allied = True
        f.non_aggression = True
        self.treaties.append(
            Treaty(a=a, b=b, kind=TreatyKind.ALLIANCE, start=date, expires_year=date.year + 50)
        )

    def set_at_war(self, a: int, b: int, at_war: bool) -> None:
        f = self.flags_mut(a, b)
        f.at_war = at_war
        if at_war:
            f.allied = False
            f.non_aggression = False

    def set_rival(self, a: int, b: int) -> None:
        self.flags_mut(a, b).rival = True

    def set_truce(self, a: int, b: int, until_year: int) -> None:
        self.truce_until[self.pair_key(a, b)] = until_year
        self.flags_mut(a, b).at_war = False

    def has_truce(self, a: int, b: int, year: int) -> bool:
        return self.truce_until.get(self.pair_key(a, b), 0) > year

    def add_war_exhaustion(self, who: int, amount: float = 15.0) -> None:
        self.war_exhaustion[who] = self.war_exhaustion.get(who, 0.0) + amount

    def tick_war_exhaustion(self) -> None:
        decayed: Dict[int, float] = {}
        for who, val in self.war_exhaustion.items():
            new_val = max(0.0, val - 1.5)
            if new_val > 0.1:
                decayed[who] = new_val
        self.war_exhaustion = decayed

    def can_declare_war(self, a: int, b: int, year: int) -> bool:
        if a == b:
            return False
        if self.war_exhaustion.get(a, 0.0) >= 60.0:
            return False
        f = self.flags(a, b)
        if f.blocks_war() or f.at_war or self.has_truce(a, b, year):
            return False
        return True

    def are_allied(self, a: int, b: int) -> bool:
        return self.flags(a, b).allied

    def allies_of(self, who: int) -> List[int]:
        out = []
        for t in self.treaties:
            if t.kind != TreatyKind.ALLIANCE:
                continue
            if t.a == who:
                out.append(t.b)
            elif t.b == who:
                out.append(t.a)
        return out

    def add_claim(
        self, claimant: int, title: int, county: Optional[int] = None, strength: int = 50
    ) -> None:
        self.claims.setdefault(claimant, []).append(
            Claim(claimant=claimant, title=title, county=county, strength=strength)
        )

    def claims_of(self, who: int) -> List[Claim]:
        return self.claims.get(who, [])

    def expire_treaties(self, year: int, world=None) -> List[str]:
        logs: List[str] = []
        keep: List[Treaty] = []
        for t in self.treaties:
            if t.expires_year <= year:
                if t.kind == TreatyKind.ALLIANCE:
                    self.flags_mut(t.a, t.b).allied = False
                    an = world.character(t.a).name if world and world.character(t.a) else str(t.a)
                    bn = world.character(t.b).name if world and world.character(t.b) else str(t.b)
                    logs.append(f"同盟到期：{an} 与 {bn}")
                elif t.kind == TreatyKind.NON_AGGRESSION:
                    self.flags_mut(t.a, t.b).non_aggression = False
                    an = world.character(t.a).name if world and world.character(t.a) else str(t.a)
                    bn = world.character(t.b).name if world and world.character(t.b) else str(t.b)
                    logs.append(f"互不侵犯到期：{an} 与 {bn}")
            else:
                keep.append(t)
        self.treaties = keep
        self.truce_until = {k: y for k, y in self.truce_until.items() if y > year}
        return logs

    @staticmethod
    def gift_opinion_gain(amount: float) -> int:
        return int(max(1.0, min(30.0, amount / 5.0)))
