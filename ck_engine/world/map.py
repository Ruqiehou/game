from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Iterator, List, Optional, Set

from ck_engine.core import NONE_ID


class Terrain(Enum):
    PLAINS = auto()
    HILLS = auto()
    MOUNTAINS = auto()
    FOREST = auto()
    DESERT = auto()
    WETLAND = auto()
    FARMLAND = auto()
    COASTAL = auto()

    def supply_limit(self) -> float:
        return {
            Terrain.PLAINS: 1.0,
            Terrain.HILLS: 0.8,
            Terrain.MOUNTAINS: 0.5,
            Terrain.FOREST: 0.7,
            Terrain.DESERT: 0.4,
            Terrain.WETLAND: 0.6,
            Terrain.FARMLAND: 1.3,
            Terrain.COASTAL: 1.1,
        }[self]

    def combat_width(self) -> float:
        return {
            Terrain.PLAINS: 1.0,
            Terrain.FARMLAND: 1.0,
            Terrain.HILLS: 0.8,
            Terrain.FOREST: 0.8,
            Terrain.MOUNTAINS: 0.6,
            Terrain.WETLAND: 0.6,
            Terrain.DESERT: 0.9,
            Terrain.COASTAL: 0.95,
        }[self]

    def development_cap(self) -> int:
        return {
            Terrain.FARMLAND: 100,
            Terrain.PLAINS: 80,
            Terrain.COASTAL: 80,
            Terrain.HILLS: 60,
            Terrain.FOREST: 60,
            Terrain.WETLAND: 50,
            Terrain.DESERT: 40,
            Terrain.MOUNTAINS: 40,
        }[self]


@dataclass
class County:
    id: int
    name: str
    terrain: Terrain
    development: int = 10
    control: float = 100.0
    prosperity: float = 50.0
    culture: int = 0
    faith: int = 0
    owner_title: int = NONE_ID
    holder: int = NONE_ID
    fort_level: int = 1
    buildings: List[str] = field(default_factory=list)
    levies: int = 200
    tax: float = 1.0
    neighbors: List[int] = field(default_factory=list)

    @staticmethod
    def new(county_id: int, name: str, terrain: Terrain) -> County:
        return County(id=county_id, name=name, terrain=terrain)

    def monthly_tax(self) -> float:
        base = self.tax * (1.0 + self.development * 0.02)
        return base * (self.control / 100.0) * self.terrain.supply_limit()

    def monthly_levies(self) -> int:
        base = self.levies * (1.0 + self.development * 0.01)
        return int(base * (self.control / 100.0))


@dataclass
class MapGraph:
    counties: Dict[int, County] = field(default_factory=dict)

    def insert(self, county: County) -> None:
        self.counties[county.id] = county

    def get(self, county_id: int) -> Optional[County]:
        return self.counties.get(county_id)

    def connect(self, a: int, b: int) -> None:
        ca, cb = self.counties.get(a), self.counties.get(b)
        if ca and b not in ca.neighbors:
            ca.neighbors.append(b)
        if cb and a not in cb.neighbors:
            cb.neighbors.append(a)

    def path(self, frm: int, to: int) -> Optional[List[int]]:
        if frm == to:
            return [frm]
        visited: Set[int] = {frm}
        queue = deque([frm])
        parent: Dict[int, int] = {}
        while queue:
            cur = queue.popleft()
            county = self.counties.get(cur)
            if not county:
                continue
            for n in county.neighbors:
                if n in visited:
                    continue
                visited.add(n)
                parent[n] = cur
                if n == to:
                    path = [to]
                    p = n
                    while p in parent:
                        prev = parent[p]
                        path.append(prev)
                        if prev == frm:
                            break
                        p = prev
                    path.reverse()
                    return path
                queue.append(n)
        return None

    def iter(self) -> Iterator[County]:
        return iter(self.counties.values())
