#!/usr/bin/env python3
"""Local stand-in for GET/POST /api/shouts. Not deployed. Used to preview the widget with NC_CHAT=1.

    python3 tipworker/shout_mock.py
    NC_CHAT=1 CHAT_ENDPOINT=http://127.0.0.1:8791 NC_LANGS=en,sv NC_SITE_DIR=/tmp/nc-chat .venv/bin/python build.py
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8791
SHOUTS = [
    {"id": 1, "nickname": "Ada", "message": "Hello from Oslo. This room is shared by every language.", "created_at": "2026-10-07T18:00:00+00:00", "lang": "en"},
    {"id": 2, "nickname": "Björn", "message": "Hej från Stockholm.", "created_at": "2026-10-07T18:05:00+00:00", "lang": "sv"},
    {"id": 3, "nickname": "Mikko", "message": "Moi Helsingistä.", "created_at": "2026-10-07T18:10:00+00:00", "lang": "fi"},
]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, code, obj):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path != "/api/shouts":
            self._send(404, {"ok": False})
            return
        self._send(200, {"ok": True, "shouts": list(SHOUTS)})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            body = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            body = {}
        if path == "/api/shouts/report":
            self._send(200, {"ok": True})
            return
        if path != "/api/shouts":
            self._send(404, {"ok": False})
            return
        if body.get("website"):
            self._send(200, {"ok": True})
            return
        nick = str(body.get("nickname") or "").strip()
        message = str(body.get("message") or "").strip()
        if len(nick) < 2 or len(message) < 1:
            self._send(400, {"ok": False, "error": "nickname" if len(nick) < 2 else "message"})
            return
        row = {
            "id": (SHOUTS[-1]["id"] + 1) if SHOUTS else 1,
            "nickname": nick[:24],
            "message": message[:280],
            "created_at": "2026-10-07T19:00:00+00:00",
            "lang": body.get("lang") if isinstance(body.get("lang"), str) else None,
        }
        SHOUTS.append(row)
        self._send(201, {"ok": True, "shout": row})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
