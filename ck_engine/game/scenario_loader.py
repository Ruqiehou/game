"""从 JSON 数据构建场景世界。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from ck_engine.core import AttributeSet, GameDate
from ck_engine.world import Gender, Terrain, TitleTier, World

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "scenarios"


def _date(arr: List[int]) -> GameDate:
    return GameDate(int(arr[0]), int(arr[1]), int(arr[2]))


def _terrain(name: str) -> Terrain:
    return Terrain[name]


def _tier(name: str) -> TitleTier:
    return TitleTier[name]


def _gender(name: str) -> Gender:
    return Gender[name]


def load_scenario(path: Path | str | None = None) -> World:
    path = Path(path) if path else DATA_DIR / "1066.json"
    data: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    start = data.get("start_date", [1066, 1, 1])
    world = World(_date(start))

    dyn: Dict[str, int] = {}
    for row in data.get("dynasties", []):
        did = world.create_dynasty(row["name"])
        dyn[row["key"]] = did
        d = world.dynasties[did]
        if "color" in row:
            d.color = tuple(row["color"])  # type: ignore[assignment]
        if "motto" in row:
            d.motto = row["motto"]

    counties: Dict[str, int] = {}
    for row in data.get("counties", []):
        cid = world.create_county(row["name"], _terrain(row["terrain"]))
        counties[row["key"]] = cid
        c = world.map.get(cid)
        if not c:
            continue
        c.development = int(row.get("development", c.development))
        c.levies = int(row.get("levies", c.levies))
        c.tax = float(row.get("tax", c.tax))
        c.fort_level = int(row.get("fort", c.fort_level))
        c.buildings = ["庄园", "市场"]
        if c.fort_level >= 2:
            c.buildings.append("城堡")

    for a, b in data.get("connections", []):
        world.map.connect(counties[a], counties[b])

    titles: Dict[str, int] = {}
    for row in data.get("titles", []):
        tid = world.create_title(row["name"], _tier(row["tier"]))
        titles[row["key"]] = tid

    for tkey, ckeys in data.get("title_counties", {}).items():
        tid = titles[tkey]
        for ck in ckeys:
            cid = counties[ck]
            # 伯爵领头衔与省份绑定
            t = world.title(tid)
            if t and t.tier == TitleTier.COUNTY:
                world.attach_county_to_title(cid, tid)
            else:
                if t and cid not in t.counties:
                    t.counties.append(cid)

    for vkey, lkey in data.get("vassals", []):
        world.set_vassal(titles[vkey], titles[lkey])

    chars: Dict[str, int] = {}
    for row in data.get("characters", []):
        cid = world.create_character(
            row["name"],
            dyn[row["dynasty"]],
            _gender(row["gender"]),
            _date(row["birth"]),
        )
        chars[row["key"]] = cid
        ch = world.character(cid)
        if not ch:
            continue
        ch.culture = int(row.get("culture", 0))
        ch.faith = int(row.get("faith", 0))
        if "attrs" in row:
            a = row["attrs"]
            ch.base_attrs = AttributeSet(
                int(a[0]), int(a[1]), int(a[2]), int(a[3]), int(a[4]), int(a[5])
            )
        if "gold" in row:
            ch.gold = float(row["gold"])
        if "prestige" in row:
            ch.prestige = float(row["prestige"])
        for t in row.get("traits", []):
            if t not in ch.traits:
                ch.traits.append(int(t))

    for child, father, mother in data.get("parents", []):
        world.set_parents(chars[child], chars[father], chars[mother])
    for a, b in data.get("marriages", []):
        world.marry(chars[a], chars[b])

    for tkey, ckey in data.get("grants", []):
        world.grant_title(titles[tkey], chars[ckey])

    for vkey, lkey in data.get("post_grants_vassals", []):
        world.set_vassal(titles[vkey], titles[lkey])

    # 再次填充高阶头衔的 counties 列表（与旧场景一致）
    for tkey, ckeys in data.get("title_counties", {}).items():
        t = world.title(titles[tkey])
        if not t:
            continue
        for ck in ckeys:
            cid = counties[ck]
            if cid not in t.counties:
                t.counties.append(cid)

    for frm, to, delta in data.get("opinions", []):
        world.modify_opinion(chars[frm], chars[to], int(delta))

    for line in data.get("logs", []):
        world.push_log(line)

    return world
