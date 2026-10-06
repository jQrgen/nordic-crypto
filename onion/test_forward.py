#!/usr/bin/env python3
"""The onion app forwards a form POST into the private Worker API, and queues when it is down."""
import json, os, sys, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "onion" / "app"))
os.environ["QUEUE_DIR"] = "/tmp/nordic-onion-test-queue"
os.environ["WORKER_URL"] = ""  # set after the fake worker binds
os.environ["ONION_INGEST_TOKEN"] = "onion-token-0123456789abcdef"
os.environ["SYNC_SECONDS"] = "0.2"
os.environ["BIND"] = "127.0.0.1"

import shutil
shutil.rmtree(os.environ["QUEUE_DIR"], ignore_errors=True)

got = []

class Fake(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(n)
        got.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": json.loads(raw)})
        data = b'{"ok":true,"id":1}'
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

fake = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=fake.serve_forever, daemon=True).start()
os.environ["WORKER_URL"] = f"http://127.0.0.1:{fake.server_address[1]}"

import server
server.WORKER_URL = os.environ["WORKER_URL"]
server.ONION_TOKEN = os.environ["ONION_INGEST_TOKEN"]
server.QUEUE_DIR = Path(os.environ["QUEUE_DIR"])
server.SYNC_SECONDS = 0.2

app = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
threading.Thread(target=app.serve_forever, daemon=True).start()
threading.Thread(target=server._sync_loop, daemon=True).start()
base = f"http://127.0.0.1:{app.server_address[1]}"

def post(lang="da", tip="Et tip om bitcoin i Danmark.", extra=None):
    fields = {"tip": tip, "language": lang, "page": f"/{lang}/", "contact": "", "attachments": "https://example.com/a", "website": ""}
    if extra:
        fields.update(extra)
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(base + f"/{lang}/", data=data, method="POST")
    with urllib.request.urlopen(req, timeout=5) as res:
        return res.status, res.read().decode("utf-8")

import urllib.parse
page = urllib.request.urlopen(base + "/da/", timeout=5)
html = page.read().decode("utf-8")
assert "text-align:left" in html, html[:200]
assert "<script" not in html.lower()
assert "kunstig intelligens" in html
assert "github.com" not in html
assert 'action="/da/"' in html

status, thanks = post()
assert status == 200, status
assert "private indbakke" in thanks or "kunstig intelligens" in thanks
assert len(got) == 1
assert got[0]["path"] == "/api/tip"
assert got[0]["auth"] == "Bearer onion-token-0123456789abcdef"
assert got[0]["body"]["tip"].startswith("Et tip")
assert "203.0.113" not in json.dumps(got[0]["body"])

# Worker down: queue, then sync.
server.WORKER_URL = "http://127.0.0.1:1"
status, queued = post(tip="Et tip der skal vente.")
assert status == 202, status
assert "onion-server" in queued or "gemmes" in queued
q = Path(os.environ["QUEUE_DIR"]) / "queue.jsonl"
assert "skal vente" in q.read_text(encoding="utf-8")

server.WORKER_URL = os.environ["WORKER_URL"]
for _ in range(20):
    if not q.exists() or "skal vente" not in q.read_text(encoding="utf-8"):
        break
    time.sleep(0.15)
else:
    raise SystemExit("queue was not forwarded: " + q.read_text(encoding="utf-8"))
assert any(item["body"]["tip"].startswith("Et tip der skal vente") for item in got)
print("onion forward: ok")
