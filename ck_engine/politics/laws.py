from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum, auto
from typing import List, Optional, Tuple

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


@dataclass
class RealmLaw:
    succession: SuccessionLaw = SuccessionLaw.PRIMOGENITURE
    crown_authority: CrownAuthority = CrownAuthority.LIMITED
    gender_law: GenderLaw = GenderLaw.AGNATIC_COGNATIC
    partition_enabled: bool = False

    @staticmethod
    def feudal_default() -> RealmLaw:
        return RealmLaw()
