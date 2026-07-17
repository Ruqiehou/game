from __future__ import annotations

from pathlib import Path

from ck_engine.game.scenario_loader import DATA_DIR, load_scenario
from ck_engine.world import World


class Scenario1066:
    """1066 场景：数据在 data/scenarios/1066.json，代码只负责加载。"""

    DATA_FILE = DATA_DIR / "1066.json"

    @staticmethod
    def build(path: Path | str | None = None) -> World:
        return load_scenario(path or Scenario1066.DATA_FILE)
