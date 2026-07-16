from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List

from ck_engine.core import NONE_ID


class TitleTier(IntEnum):
    BARONY = 1
    COUNTY = 2
    DUCHY = 3
    KINGDOM = 4
    EMPIRE = 5

    def rank_name(self) -> str:
        return {
            TitleTier.BARONY: "男爵",
            TitleTier.COUNTY: "伯爵",
            TitleTier.DUCHY: "公爵",
            TitleTier.KINGDOM: "国王",
            TitleTier.EMPIRE: "皇帝",
        }[self]


@dataclass
class Title:
    id: int
    name: str
    tier: TitleTier
    adjective: str = ""
    holder: int = NONE_ID
    de_jure_liege: int = NONE_ID
    de_facto_liege: int = NONE_ID
    de_jure_vassals: List[int] = field(default_factory=list)
    de_facto_vassals: List[int] = field(default_factory=list)
    capital: int = NONE_ID
    counties: List[int] = field(default_factory=list)
    creation_cost: float = 0.0
    destroyable: bool = False

    @staticmethod
    def new(title_id: int, name: str, tier: TitleTier) -> Title:
        cost = {
            TitleTier.BARONY: 0.0,
            TitleTier.COUNTY: 50.0,
            TitleTier.DUCHY: 200.0,
            TitleTier.KINGDOM: 500.0,
            TitleTier.EMPIRE: 1000.0,
        }[tier]
        return Title(
            id=title_id,
            name=name,
            tier=tier,
            adjective=f"{name}的",
            creation_cost=cost,
            destroyable=tier >= TitleTier.DUCHY,
        )

    def is_held(self) -> bool:
        return self.holder != NONE_ID

    def set_holder(self, holder: int) -> None:
        self.holder = holder

    def clear_holder(self) -> None:
        self.holder = NONE_ID
