import json
import mimetypes
import os
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dashboard.alerts import AlertService
from dashboard.api import App
from dashboard.store import Store
from dashboard.weather import WeatherService

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
HOST, PORT = "127.0.0.1", 8765
MAX_BODY = 1024 * 1024


def _clock():
    override = os.environ.get("DASHBOARD_TODAY")
    if override:
        return lambda: date.fromisoformat(override)
    return date.today


def build_app():
    rules = json.loads((ROOT / "content" / "chores.json").read_text(encoding="utf-8"))["rules"]
    recipes = json.loads((ROOT / "content" / "recipes.json").read_text(encoding="utf-8"))
    store = Store(ROOT / "data" / "data.json", ROOT / "data" / "backups")
    return App(store, rules, recipes, WeatherService(), clock=_clock(), alerts=AlertService())


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, payload, ctype="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def _api(self, method):
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length < 0 or length > MAX_BODY:
                    return self._send(400, b'{"error": "Bad request"}')
                raw = self.rfile.read(length) if length else b""
                body = json.loads(raw) if raw else {}
            except (ValueError, json.JSONDecodeError):
                return self._send(400, b'{"error": "Bad request"}')
            status, payload = app.handle(method, self.path.split("?")[0], body)
            self._send(status, json.dumps(payload).encode("utf-8"))

        def do_GET(self):
            path = self.path.split("?")[0]
            if path.startswith("/api/"):
                return self._api("GET")
            target = (WEB / ("index.html" if path == "/" else path.lstrip("/"))).resolve()
            if WEB.resolve() not in target.parents or not target.is_file():
                return self._send(404, b'{"error": "Not found"}')
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            self._send(200, target.read_bytes(), ctype)

        def do_POST(self):
            self._api("POST")

        def do_PUT(self):
            self._api("PUT")

        def do_PATCH(self):
            self._api("PATCH")

        def do_DELETE(self):
            self._api("DELETE")

        def log_message(self, *args):
            pass

    return Handler


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), make_handler(build_app())).serve_forever()
