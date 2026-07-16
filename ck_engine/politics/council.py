from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

from ck_engine.core import NONE_ID


class CouncilPosition(Enum):
    CHANCELLOR = auto()
    MARSHAL = auto()
    STEWARD = auto()
    SPYMASTER = auto()
    COURT_CHAPLAIN = auto()

    def name_zh(self) -> str:
        return {
            CouncilPosition.CHANCELLOR: "首相",
            CouncilPosition.MARSHAL: "元帅",
            CouncilPosition.STEWARD: "总管",
            CouncilPosition.SPYMASTER: "间谍总管",
            CouncilPosition.COURT_CHAPLAIN: "宫廷神甫",
        }[self]

    @staticmethod
    def all() -> List[CouncilPosition]:
        return list(CouncilPosition)


class CouncilTask(Enum):
    DOMESTIC_RELATIONS = auto()
    FABRICATE_CLAIM = auto()
    TRAIN_COMMANDERS = auto()
    INCREASE_CONTROL = auto()
    COLLECT_TAXES = auto()
    DEVELOP_COUNTY = auto()
    DISRUPT_SCHEMES = auto()
    SUPPORT_MURDER = auto()
    CONVERT_FAITH = auto()
    FABRICATE_HOOK = auto()

    def name_zh(self) -> str:
        return {
            CouncilTask.DOMESTIC_RELATIONS: "内政外交",
            CouncilTask.FABRICATE_CLAIM: "伪造宣称",
            CouncilTask.TRAIN_COMMANDERS: "训练将领",
            CouncilTask.INCREASE_CONTROL: "强化控制",
            CouncilTask.COLLECT_TAXES: "催收税赋",
            CouncilTask.DEVELOP_COUNTY: "发展领地",
            CouncilTask.DISRUPT_SCHEMES: "破坏阴谋",
            CouncilTask.SUPPORT_MURDER: "协助密谋",
            CouncilTask.CONVERT_FAITH: "传播信仰",
            CouncilTask.FABRICATE_HOOK: "神权施压",
        }[self]


@dataclass
class CouncilMonthlyResult:
    gold: float = 0.0
    prestige: float = 0.0
    piety: float = 0.0
    control_gain: float = 0.0
    development_chance: float = 0.0
    claim_progress: float = 0.0
    logs: List[str] = field(default_factory=list)


@dataclass
class Council:
    ruler: int
    chancellor: int = NONE_ID
    marshal: int = NONE_ID
    steward: int = NONE_ID
    spymaster: int = NONE_ID
    chaplain: int = NONE_ID
    tasks: Dict[CouncilPosition, CouncilTask] = field(default_factory=dict)

    @staticmethod
    def empty(ruler: int) -> Council:
        c = Council(ruler=ruler)
        c.tasks = {
            CouncilPosition.CHANCELLOR: CouncilTask.DOMESTIC_RELATIONS,
            CouncilPosition.MARSHAL: CouncilTask.TRAIN_COMMANDERS,
            CouncilPosition.STEWARD: CouncilTask.COLLECT_TAXES,
            CouncilPosition.SPYMASTER: CouncilTask.DISRUPT_SCHEMES,
            CouncilPosition.COURT_CHAPLAIN: CouncilTask.CONVERT_FAITH,
        }
        return c

    def get(self, pos: CouncilPosition) -> int:
        return {
            CouncilPosition.CHANCELLOR: self.chancellor,
            CouncilPosition.MARSHAL: self.marshal,
            CouncilPosition.STEWARD: self.steward,
            CouncilPosition.SPYMASTER: self.spymaster,
            CouncilPosition.COURT_CHAPLAIN: self.chaplain,
        }[pos]

    def set(self, pos: CouncilPosition, who: int) -> None:
        if pos == CouncilPosition.CHANCELLOR:
            self.chancellor = who
        elif pos == CouncilPosition.MARSHAL:
            self.marshal = who
        elif pos == CouncilPosition.STEWARD:
            self.steward = who
        elif pos == CouncilPosition.SPYMASTER:
            self.spymaster = who
        else:
            self.chaplain = who

    def members(self) -> List[Tuple[CouncilPosition, int]]:
        return [(p, self.get(p)) for p in CouncilPosition.all() if self.get(p) != NONE_ID]

    def task_of(self, pos: CouncilPosition) -> CouncilTask:
        return self.tasks.get(pos, CouncilTask.DOMESTIC_RELATIONS)

    def auto_appoint(self, candidates: List[Tuple[int, int, int, int, int, int]]) -> None:
        # id, dip, mar, ste, int, lea
        used = set()
        if self.ruler != NONE_ID:
            used.add(self.ruler)

        def pick(score_idx: int) -> int:
            best, best_s = NONE_ID, -999
            for row in candidates:
                if row[0] in used:
                    continue
                if row[score_idx] > best_s:
                    best_s = row[score_idx]
                    best = row[0]
            if best != NONE_ID:
                used.add(best)
            return best

        self.chancellor = pick(1)
        self.marshal = pick(2)
        self.steward = pick(3)
        self.spymaster = pick(4)
        self.chaplain = pick(5)

    def monthly_effect(
        self, skill_of: Dict[int, Tuple[int, int, int, int, int]]
    ) -> CouncilMonthlyResult:
        r = CouncilMonthlyResult()
        for pos, who in self.members():
            skills = skill_of.get(who, (8, 8, 8, 8, 8))
            task = self.task_of(pos)
            if pos == CouncilPosition.CHANCELLOR and task == CouncilTask.DOMESTIC_RELATIONS:
                gain = skills[0] * 0.3
                r.prestige += gain
            elif pos == CouncilPosition.CHANCELLOR and task == CouncilTask.FABRICATE_CLAIM:
                r.claim_progress += skills[0] * 0.8
            elif pos == CouncilPosition.MARSHAL and task == CouncilTask.INCREASE_CONTROL:
                r.control_gain += skills[1] * 0.4
            elif pos == CouncilPosition.STEWARD and task == CouncilTask.COLLECT_TAXES:
                g = skills[2] * 0.6
                r.gold += g
            elif pos == CouncilPosition.STEWARD and task == CouncilTask.DEVELOP_COUNTY:
                r.development_chance += skills[2] * 0.5
            elif pos == CouncilPosition.COURT_CHAPLAIN:
                r.piety += skills[4] * 0.5
        return r


@dataclass
class CouncilRegistry:
    by_ruler: Dict[int, Council] = field(default_factory=dict)

    def get_or_create(self, ruler: int) -> Council:
        if ruler not in self.by_ruler:
            self.by_ruler[ruler] = Council.empty(ruler)
        return self.by_ruler[ruler]

    def get(self, ruler: int) -> Optional[Council]:
        return self.by_ruler.get(ruler)
