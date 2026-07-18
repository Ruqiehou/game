"""地图布局：从 data/map_layouts 加载，支持多场景。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

_LAYOUT_DIR = Path(__file__).resolve().parents[1] / "data" / "map_layouts"
_CACHE: Dict[str, dict] = {}


def _load(scenario: str = "1066") -> dict:
    if scenario in _CACHE:
        return _CACHE[scenario]
    path = _LAYOUT_DIR / f"{scenario}.json"
    if not path.exists():
        data = {"viewbox": "0 0 820 720", "sea": {"y": 475, "label": ""}, "counties": {}}
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
    # 规范化 points 为 tuple 列表
    counties: Dict[str, dict] = {}
    for name, row in data.get("counties", {}).items():
        pts = [tuple(p) for p in row.get("points", [])]
        counties[name] = {
            "cx": float(row["cx"]),
            "cy": float(row["cy"]),
            "points": pts,
        }
    packed = {
        "viewbox": data.get("viewbox", "0 0 820 720"),
        "sea": data.get("sea", {"y": 475, "label": ""}),
        "counties": counties,
    }
    _CACHE[scenario] = packed
    return packed


def layout_for(name: str, scenario: str = "1066") -> dict:
    data = _load(scenario)
    if name in data["counties"]:
        return data["counties"][name]
    h = abs(hash(name)) % 800
    return {
        "cx": 100 + h % 700,
        "cy": 80 + (h // 7) % 500,
        "points": _box(100 + h % 700, 80 + (h // 7) % 500, 70, 50),
    }


def sea_band(scenario: str = "1066") -> dict:
    return dict(_load(scenario)["sea"])


def viewbox(scenario: str = "1066") -> str:
    return str(_load(scenario)["viewbox"])


# 兼容旧导入
SEA_BAND = sea_band()


def _box(cx: float, cy: float, w: float, h: float) -> List[Tuple[float, float]]:
    return [
        (cx - w / 2, cy - h / 2),
        (cx + w / 2, cy - h / 2),
        (cx + w / 2, cy + h / 2),
        (cx - w / 2, cy + h / 2),
    ]


def points_to_svg(points: List[Tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def reload_layouts() -> None:
    """测试/热更新用。"""
    _CACHE.clear()
