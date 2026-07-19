"""CK 风格大战略引擎 — 真实可玩启动脚本。

运行:
  python run_game.py              # 启动图形界面并打开浏览器
  python run_game.py --demo       # 运行后台模拟
  python run_game.py --headless   # 启动服务器但不打开浏览器
  python run_game.py --port 8888  # 指定端口
  python run_game.py --new-game   # 忽略已有存档，直接开始新局
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ck_engine.ui.api import GameAPI
from ck_engine.ui.server import Handler, STATIC_DIR, main as server_main


# ── 终端颜色 ──────────────────────────────────────────────
class C:
    """简单的终端 ANSI 颜色（Windows 兼容）。"""
    _enabled = os.name != "nt" or bool(os.environ.get("TERM")) or bool(os.environ.get("ANSICON"))

    @classmethod
    def _c(cls, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if cls._enabled else text

    @classmethod
    def header(cls, text: str) -> str: return cls._c("94;1", text)      # 亮蓝
    @classmethod
    def ok(cls, text: str) -> str: return cls._c("92", text)             # 绿色
    @classmethod
    def warn(cls, text: str) -> str: return cls._c("93", text)           # 黄色
    @classmethod
    def err(cls, text: str) -> str: return cls._c("91", text)            # 红色
    @classmethod
    def dim(cls, text: str) -> str: return cls._c("90", text)            # 灰色
    @classmethod
    def accent(cls, text: str) -> str: return cls._c("36", text)         # 青色
    @classmethod
    def bold(cls, text: str) -> str: return cls._c("1", text)            # 加粗


# ── 端口管理 ──────────────────────────────────────────────

def find_free_port(preferred: int, max_attempts: int = 10) -> int:
    """从 preferred 开始查找可用端口。"""
    for offset in range(max_attempts):
        port = preferred + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 0  # 都不可用


def wait_for_server(port: int, timeout: float = 15.0) -> bool:
    """等待 HTTP 服务器就绪。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.connect(("127.0.0.1", port))
                return True
            except OSError:
                time.sleep(0.3)
    return False


# ── 自动存档管理 ──────────────────────────────────────────

SAVES_DIR = ROOT / "saves"
AUTOSAVE_PATH = SAVES_DIR / "autosave.json"
QUICKSAVE_PATH = SAVES_DIR / "quicksave.json"


def autosave_exists() -> bool:
    return AUTOSAVE_PATH.exists() and AUTOSAVE_PATH.stat().st_size > 0


def get_autosave_info() -> str | None:
    """读取自动存档的日期信息。"""
    if not autosave_exists():
        return None
    try:
        data = json.loads(AUTOSAVE_PATH.read_text(encoding="utf-8"))
        date_list = data.get("date", [])
        if len(date_list) == 3:
            return f"{date_list[0]:04d}-{date_list[1]:02d}-{date_list[2]:02d}"
        return "(未知日期)"
    except Exception:
        return "(已损坏)"


def save_on_exit() -> None:
    """退出时自动存档。"""
    try:
        handler = Handler.api
        handler.notify("服务器关闭，自动保存...")
        handler._save(None)
        print(f"\n{C.dim('已保存 → autosave.json')}")
    except Exception:
        pass


# ── CLI 参数 ──────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CK-Style Grand Strategy Engine — 中世纪大战略模拟",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_game.py             启动图形界面（默认端口 8765）
  python run_game.py --port 8080 指定端口
  python run_game.py --new-game  忽略存档，直接开始新局
  python run_game.py --headless  只启动服务器，不打开浏览器
  python run_game.py --demo      控制台模拟（无需浏览器）
""",
    )
    parser.add_argument("--port", type=int, default=8765, help="HTTP 服务器端口（默认 8765）")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="绑定地址（默认 127.0.0.1）")
    parser.add_argument("--headless", action="store_true", help="只启动服务器，不打开浏览器")
    parser.add_argument("--new-game", action="store_true", help="忽略已有存档，开始新局")
    parser.add_argument("--demo", action="store_true", help="运行控制台模拟演示（无需浏览器）")
    parser.add_argument("--days", type=int, default=0, help="演示模式模拟天数（默认 2 年）")
    return parser.parse_args()


# ── 演示模式 ──────────────────────────────────────────────

def run_demo(days: int = 0) -> None:
    """功能更丰富的控制台演示。"""
    from ck_engine.game.simulation import GameSimulation

    if days <= 0:
        days = 365 * 2

    print()
    print(f"  {C.header('CK-Style Grand Strategy Engine')}")
    print(f"  {C.dim('控制台演示模式 — 1066 英格兰场景')}")
    print(f"  {C.dim(f'模拟 {days} 天（约 {days / 365:.1f} 年）')}")
    print(f"  {'─' * 52}")

    sim = GameSimulation()

    # 初始状态
    sim.print_status()

    # 模拟进度条
    print()
    bar_width = 50
    report_interval = max(1, days // 10)

    for d in range(1, days + 1):
        sim.tick_day()
        if d % report_interval == 0 or d == days:
            pct = d / days
            filled = int(bar_width * pct)
            bar = "█" * filled + "░" * (bar_width - filled)
            year_progress = sim.world.date.year + (sim.world.date.month - 1) / 12
            sys.stdout.write(
                f"\r  {C.accent(f'模拟中')} [{C.ok(bar)}] "
                f"{C.bold(f'{pct * 100:.0f}%')} "
                f"{C.dim(str(sim.world.date))}  "
                f"战争:{len([w for w in sim.wars.active_wars()])}  "
                f"派系:{len(sim.factions.factions)}"
            )
            sys.stdout.flush()

    print(f"\n\n{C.header('模拟结束')}")
    print(f"  {'─' * 52}")
    sim.print_status()
    print()
    sim.print_recent_log(30)
    sim.print_wars()
    sim.print_politics()
    sim.print_dynasties()
    print(f"\n  {C.dim('总耗时: ')}{len(sim.world.log)} 条日志记录")
    print()


# ── 启动横幅 ──────────────────────────────────────────────

def print_banner(port: int) -> None:
    print()
    print(f"  {C.header('╔══════════════════════════════════════════╗')}")
    print(f"  {C.header('║')}  CK-Style Grand Strategy Engine        {C.header('║')}")
    print(f"  {C.header('║')}  中世纪大战略模拟 · 可交互地图          {C.header('║')}")
    print(f"  {C.header('╚══════════════════════════════════════════╝')}")
    print()
    print(f"  {C.accent('服务器')}  http://127.0.0.1:{port}/")
    print(f"  {C.dim('静态资源')}  {STATIC_DIR}")
    print(f"  {C.dim('存档目录')}  {SAVES_DIR}")
    print()


def print_rulers_info() -> None:
    """打印主要统治者信息。"""
    try:
        # 临时创建一个模拟场景来读取初始状态
        from ck_engine.game.simulation import GameSimulation

        sim = GameSimulation()
        print(f"  {C.bold('世界初始状态')}")
        print(f"  {C.dim('─' * 40)}")
        for r in sim.world.rulers():
            title = sim.world.title(r.primary_title)
            tname = title.name if title else "无"
            income = sim.world.monthly_income_of(r.id)
            men = sim.wars.total_men_of(r.id)
            print(f"  {C.accent(f'{r.name:12s}')} {tname:10s}  "
                  f"金 {C.ok(f'{r.gold:.0f}')}  "
                  f"月入 {C.ok(f'{income:.1f}')}  "
                  f"军力 {C.ok(f'{men}')}")
        print()
    except Exception:
        pass  # 静默失败，不影响主启动


# ── 存档选择 ──────────────────────────────────────────────

def prompt_load_autosave(new_game: bool = False) -> bool:
    """询问是否加载自动存档。

    返回: True=继续加载, False=开始新局
    """
    if new_game:
        return False
    if not autosave_exists():
        return False

    info = get_autosave_info()
    try:
        resp = input(
            f"  {C.warn('发现自动存档')} ({info or '?'})\n"
            f"  {C.dim('[Enter] 读取存档  [n] 新游戏  [d] 删除存档')}: "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return True

    if resp == "n":
        return False
    if resp == "d":
        try:
            AUTOSAVE_PATH.unlink()
            print(f"  {C.warn('已删除自动存档')}")
        except Exception:
            print(f"  {C.err('删除失败')}")
        return False
    return True  # Enter 或其它 → 加载


# ── 启动 GUI 服务器 ──────────────────────────────────────

def run_gui(args: argparse.Namespace) -> None:
    """启动带地图 UI 的 HTTP 服务器。"""
    port = find_free_port(args.port)
    if port == 0:
        print(f"\n  {C.err('错误')} 找不到可用端口，请指定其它端口")
        print(f"  {C.dim('python run_game.py --port 9000')}")
        sys.exit(1)

    if port != args.port:
        print(f"\n  {C.warn(f'端口 {args.port} 被占用，改用 {port}')}")

    print_banner(port)

    # 处理存档
    if not args.new_game and autosave_exists():
        load_save = prompt_load_autosave(new_game=False)
        if load_save:
            Handler.api._load(None)
            print(f"  {C.ok('✓ 已加载自动存档')}")
        else:
            print(f"  {C.dim('开始新游戏')}")
    else:
        print(f"  {C.dim('开始新游戏')}")

    print()
    print_rulers_info()

    # 注册退出自动存档
    atexit.register(save_on_exit)

    # 启动服务器线程
    server_thread = threading.Thread(
        target=server_main,
        kwargs={"host": args.host, "port": port},
        daemon=True,
    )
    server_thread.start()

    # 等待就绪
    if not wait_for_server(port):
        print(f"  {C.err('服务器启动超时，请查看上方错误信息。')}")
        sys.exit(1)

    print(f"  {C.ok('✓ 服务器已就绪')}")
    print()

    # 打开浏览器
    if not args.headless:
        def _open_browser():
            time.sleep(0.6)
            url = f"http://127.0.0.1:{port}/"
            try:
                webbrowser.open(url)
                print(f"  {C.dim(f'已打开浏览器 → {url}')}")
            except Exception:
                print(f"  {C.warn(f'请手动打开浏览器访问 {url}')}")

        t = threading.Thread(target=_open_browser, daemon=True)
        t.start()
    else:
        print(f"  {C.dim('静默模式（--headless）')}")
        print(f"  {C.dim(f'浏览器打开 http://127.0.0.1:{port}/')}")

    print(f"\n  {C.dim('按 Ctrl+C 停止服务器')}")
    print()

    # 保持主线程存活
    try:
        while server_thread.is_alive():
            server_thread.join(timeout=1.0)
    except KeyboardInterrupt:
        print(f"\n  {C.warn('正在停止服务器...')}")
        save_on_exit()
        print(f"  {C.ok('✓ 已安全退出')}")
        sys.exit(0)


# ── 主入口 ──────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # 确保存档目录存在
    SAVES_DIR.mkdir(parents=True, exist_ok=True)

    if args.demo:
        run_demo(days=args.days)
        return

    run_gui(args)


if __name__ == "__main__":
    main()
