from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from ck_engine.core import NONE_ID


@dataclass
class Dynasty:
    id: int
    name: str
    head: int = NONE_ID
    founder: int = NONE_ID
    members: List[int] = field(default_factory=list)
    color: Tuple[int, int, int] = (128, 128, 128)
    motto: str = ""
    prestige: float = 0.0

    @staticmethod
    def new(dynasty_id: int, name: str, head: int = NONE_ID) -> Dynasty:
        return Dynasty(id=dynasty_id, name=name, head=head, founder=head)

    def add_member(self, who: int) -> None:
        if who not in self.members:
            self.members.append(who)
