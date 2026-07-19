"""本地地图 UI 服务器。

运行:
  python -m ck_engine.ui.server
  浏览器打开 http://127.0.0.1:8765/
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ck_engine.ui.api import GameAPI

STATIC_DIR = Path(__file__).resolve().parent / "static"
HOST = "127.0.0.1"
PORT = 8765


class Handler(SimpleHTTPRequestHandler):
    api = GameAPI()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send_json(self, data, code: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/state":
            self._send_json(self.api.snapshot())
            return
        if path in ("/", ""):
            self.path = "/index.html"
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/action":
            payload = self._read_json()
            self._send_json(self.api.action(payload))
            return
        self._send_json({"error": "not found"}, 404)


def main(host: str | None = None, port: int | None = None) -> None:
    """启动 HTTP 服务器。

    参数:
        host: 绑定地址，默认 127.0.0.1
        port: 绑定端口，默认 8765
    """
    if host is None:
        host = HOST
    if port is None:
        port = PORT
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"地图 UI: http://{host}:{port}/")
    print("Ctrl+C 退出")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CK 引擎地图服务器")
    parser.add_argument("--port", type=int, default=PORT, help=f"服务器端口（默认 {PORT}）")
    parser.add_argument("--host", type=str, default=HOST, help=f"绑定地址（默认 {HOST}）")
    args = parser.parse_args()
    main(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
