"""CK 风格大战略引擎 — 可玩启动入口。

运行:
  python run_game.py
  python run_game.py --no-browser
  python run_game.py --port 8765
  python run_game.py --demo
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ck_engine.ui.server import Handler, STATIC_DIR

HOST = "127.0.0.1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CK 风格大战略引擎启动器")
    parser.add_argument("--port", type=int, default=8765, help="本地服务器端口，默认 8765")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--demo", action="store_true", help="运行纯控制台模拟演示")
    return parser.parse_args()


def find_available_port(preferred: int) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"端口 {preferred}-{preferred + 19} 都不可用")


def open_browser_later(url: str) -> None:
    def worker() -> None:
        time.sleep(0.8)
        webbrowser.open(url)

    threading.Thread(target=worker, daemon=True).start()


def run_demo() -> None:
    from ck_engine.game.main import main as demo_main

    demo_main()


def run_ui(port: int, no_browser: bool) -> None:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    actual_port = find_available_port(port)
    url = f"http://{HOST}:{actual_port}/"

    if actual_port != port:
        print(f"端口 {port} 被占用，已改用 {actual_port}")

    server = ThreadingHTTPServer((HOST, actual_port), Handler)

    print("====================================================")
    print("  CK-Style Grand Strategy Engine")
    print("  可玩地图 UI 已启动")
    print("====================================================")
    print(f"  打开: {url}")
    print("  Ctrl+C 退出")
    print("====================================================")

    if not no_browser:
        open_browser_later(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在退出...")
    finally:
        server.server_close()
        print("已停止")


def main() -> None:
    args = parse_args()
    if args.demo:
        run_demo()
        return
    run_ui(args.port, args.no_browser)


if __name__ == "__main__":
    main()
