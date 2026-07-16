from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from .stats import AttributeSet


class TraitKind(Enum):
    PERSONALITY = auto()
    EDUCATION = auto()
    CONGENITAL = auto()
    LIFESTYLE = auto()
    HEALTH = auto()
    COMMANDER = auto()
    CULTURAL = auto()
    RELIGIOUS = auto()


TraitId = int


@dataclass
class Trait:
    id: TraitId
    name: str
    kind: TraitKind
    attr_bonus: AttributeSet = field(default_factory=AttributeSet.zero)
    opinion_self: int = 0
    opinion_others: int = 0
    fertility_mod: float = 0.0
    health_mod: float = 0.0
    description: str = ""


def builtin_traits() -> list[Trait]:
    def t(
        tid: int,
        name: str,
        kind: TraitKind,
        **kwargs,
    ) -> Trait:
        return Trait(id=tid, name=name, kind=kind, **kwargs)

    return [
        t(1, "勇敢", TraitKind.PERSONALITY, attr_bonus=AttributeSet(prowess=2, martial=1), opinion_others=5),
        t(2, "狡诈", TraitKind.PERSONALITY, attr_bonus=AttributeSet(intrigue=3, diplomacy=-1), opinion_others=-5),
        t(3, "公正", TraitKind.PERSONALITY, attr_bonus=AttributeSet(diplomacy=2, stewardship=1), opinion_others=10),
        t(4, "贪婪", TraitKind.PERSONALITY, attr_bonus=AttributeSet(stewardship=2, diplomacy=-1), opinion_others=-8),
        t(5, "慷慨", TraitKind.PERSONALITY, attr_bonus=AttributeSet(diplomacy=2, stewardship=-1), opinion_others=8),
        t(6, "军事天才", TraitKind.COMMANDER, attr_bonus=AttributeSet(martial=4, prowess=2), opinion_others=5),
        t(7, "病弱", TraitKind.HEALTH, attr_bonus=AttributeSet(prowess=-2), health_mod=-0.5, fertility_mod=-0.1),
        t(8, "博学", TraitKind.EDUCATION, attr_bonus=AttributeSet(learning=3), opinion_others=3),
        t(9, "野心勃勃", TraitKind.PERSONALITY, attr_bonus=AttributeSet(martial=1, intrigue=1, stewardship=1), opinion_others=-3),
        t(10, "忠诚", TraitKind.PERSONALITY, attr_bonus=AttributeSet(diplomacy=1), opinion_others=12),
        t(11, "残忍", TraitKind.PERSONALITY, attr_bonus=AttributeSet(intrigue=2, diplomacy=-2), opinion_others=-15),
        t(12, "魅力四射", TraitKind.PERSONALITY, attr_bonus=AttributeSet(diplomacy=3), opinion_others=10),
    ]
