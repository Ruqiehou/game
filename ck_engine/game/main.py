"""CK 风格大战略引擎 — Python 演示入口。

运行:
  python -m ck_engine.game.main
  或
  python ck_engine/game/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# 允许直接 python ck_engine/game/main.py
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ck_engine.game.simulation import GameSimulation


def main() -> None:
    print("====================================================")
    print("  CK-Style Grand Strategy Engine (Python)")
    print("  大战略引擎演示 — 1066 英格兰场景")
    print("====================================================\n")

    sim = GameSimulation()
    sim.print_status()
    sim.print_politics()

    days = 365 * 2
    print(f"\n>>> 开始模拟 {days} 天...\n")
    sim.run_days(days)

    print("\n====================================================")
    print("  模拟结束")
    print("====================================================")
    sim.print_status()
    sim.print_recent_log(40)
    sim.print_wars()
    sim.print_politics()
    sim.print_dynasties()


if __name__ == "__main__":
    main()
