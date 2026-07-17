from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum, auto
from typing import List, Optional, Sequence, Tuple

from ck_engine.world.character import Gender


class SuccessionLaw(Enum):
    PRIMOGENITURE = auto()
    CONFEDERATE_PARTITION = auto()
    ELECTIVE = auto()
    HOUSE_SENIORITY = auto()
    ULTIMOGENITURE = auto()

    def name_zh(self) -> str:
        return {
            SuccessionLaw.PRIMOGENITURE: "长子继承制",
            SuccessionLaw.CONFEDERATE_PARTITION: "联邦分割继承",
            SuccessionLaw.ELECTIVE: "选举君主制",
            SuccessionLaw.HOUSE_SENIORITY: "家族长老制",
            SuccessionLaw.ULTIMOGENITURE: "幼子继承制",
        }[self]


class CrownAuthority(IntEnum):
    AUTONOMOUS = 0
    LIMITED = 1
    HIGH = 2
    ABSOLUTE = 3

    def name_zh(self) -> str:
        return {
            CrownAuthority.AUTONOMOUS: "自治王权",
            CrownAuthority.LIMITED: "有限王权",
            CrownAuthority.HIGH: "高度王权",
            CrownAuthority.ABSOLUTE: "绝对王权",
        }[self]

    def vassal_opinion_penalty(self) -> int:
        return {
            CrownAuthority.AUTONOMOUS: 0,
            CrownAuthority.LIMITED: -5,
            CrownAuthority.HIGH: -15,
            CrownAuthority.ABSOLUTE: -30,
        }[self]

    def tax_bonus(self) -> float:
        return {
            CrownAuthority.AUTONOMOUS: 0.0,
            CrownAuthority.LIMITED: 0.05,
            CrownAuthority.HIGH: 0.15,
            CrownAuthority.ABSOLUTE: 0.25,
        }[self]


class GenderLaw(Enum):
    AGNATIC = auto()
    AGNATIC_COGNATIC = auto()
    ABSOLUTE_COGNATIC = auto()
    ENATIC = auto()

    def name_zh(self) -> str:
        return {
            GenderLaw.AGNATIC: "男系继承",
            GenderLaw.AGNATIC_COGNATIC: "男系优先",
            GenderLaw.ABSOLUTE_COGNATIC: "绝对双系",
            GenderLaw.ENATIC: "女系继承",
        }[self]

    def allows(self, gender: Gender, has_male_heir: bool) -> bool:
        if self == GenderLaw.AGNATIC:
            return gender == Gender.MALE
        if self == GenderLaw.AGNATIC_COGNATIC:
            return gender == Gender.MALE or not has_male_heir
        if self == GenderLaw.ENATIC:
            return gender == Gender.FEMALE
        return True


# (id, gender, birth_ordinal, alive)
HeirCandidate = Tuple[int, Gender, int, bool]


@dataclass
class RealmLaw:
    succession: SuccessionLaw = SuccessionLaw.PRIMOGENITURE
    crown_authority: CrownAuthority = CrownAuthority.LIMITED
    gender_law: GenderLaw = GenderLaw.AGNATIC_COGNATIC
    partition_enabled: bool = False

    @staticmethod
    def feudal_default() -> RealmLaw:
        return RealmLaw()

    def pick_heir(
        self,
        children: Sequence[HeirCandidate],
        dynasty_members: Sequence[HeirCandidate],
    ) -> Optional[int]:
        living_children = [c for c in children if c[3]]
        has_male = any(g == Gender.MALE for _, g, _, _ in living_children)

        def eligible(g: Gender) -> bool:
            return self.gender_law.allows(g, has_male)

        def gender_key(g: Gender) -> int:
            if self.gender_law in (GenderLaw.AGNATIC, GenderLaw.AGNATIC_COGNATIC):
                return 0 if g == Gender.MALE else 1
            if self.gender_law == GenderLaw.ENATIC:
                return 0 if g == Gender.FEMALE else 1
            return 0

        if self.succession == SuccessionLaw.HOUSE_SENIORITY:
            pool = [c for c in dynasty_members if c[3] and eligible(c[1])]
            pool.sort(key=lambda c: c[2])  # 年长优先
            return pool[0][0] if pool else None

        if self.succession == SuccessionLaw.ULTIMOGENITURE:
            pool = [c for c in living_children if eligible(c[1])]
            pool.sort(key=lambda c: (gender_key(c[1]), -c[2]))
            return pool[0][0] if pool else None

        # 长子 / 分割 / 选举：简化为长嗣
        pool = [c for c in living_children if eligible(c[1])]
        pool.sort(key=lambda c: (gender_key(c[1]), c[2]))
        if pool:
            return pool[0][0]

        # 无子女则取王朝成员
        pool = [c for c in dynasty_members if c[3] and eligible(c[1])]
        pool.sort(key=lambda c: (gender_key(c[1]), c[2]))
        return pool[0][0] if pool else None

    def partition_titles(
        self, titles: List[int], heirs: List[int]
    ) -> List[Tuple[int, List[int]]]:
        if not heirs:
            return []
        if not self.partition_enabled or self.succession != SuccessionLaw.CONFEDERATE_PARTITION:
            return [(heirs[0], list(titles))]
        result: List[Tuple[int, List[int]]] = [(h, []) for h in heirs]
        for i, t in enumerate(titles):
            result[i % len(heirs)][1].append(t)
        return result
