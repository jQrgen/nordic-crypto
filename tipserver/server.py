#!/usr/bin/env python3
"""Nordic Crypto tip server (Python stdlib only). Listens on localhost; will later be exposed via a Cloudflare tunnel.
  POST /api/tip     JSON or form fields: url (required, http/https), country (NO/SE/DK/FI/IS/unsure), note (<=1000 chars),
                    name (optional, <=100 chars), website (honeypot: must be empty). Stored in SQLite as status 'pending'.
  GET  /api/health  {"ok": true}
Privacy: the IP address is never stored or logged (it is only held in memory, hashed, for the rate limit) and the request
body is never logged. No user agent or other metadata is stored. Body capped at 4 KB.
CORS: only https://jqrgen.github.io (plus TIP_EXTRA_ORIGINS for local tests). A browser POST from any other Origin is refused.
Env: TIP_PORT (8787), TIP_HOST (127.0.0.1), TIP_DB (tipserver/tips.db), TIP_EXTRA_ORIGINS (comma-separated, tests only)."""
import hashlib, json, os, re, secrets, sqlite3, sys, threading, time, urllib.parse, datetime as dt
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("TIP_PORT", "8787")); HOST = os.environ.get("TIP_HOST", "127.0.0.1")
DB = os.environ.get("TIP_DB", os.path.join(HERE, "tips.db"))
ORIGINS = {"https://jqrgen.github.io"} | {o.strip() for o in os.environ.get("TIP_EXTRA_ORIGINS", "").split(",") if o.strip()}
THANKS = "https://jqrgen.github.io/nordic-crypto/tip/"
MAX_BODY = 4096; MAX_NOTE = 1000; MAX_NAME = 100; MAX_URL = 2000
COUNTRIES = {"NO", "SE", "DK", "FI", "IS", "UNSURE"}
RATE_N, RATE_WINDOW = 5, 600          # max 5 tips per IP per 10 minutes
RATE_GLOBAL_N = 200                    # and max 200 tips per 10 minutes in total (spam flood guard)
_salt = secrets.token_bytes(16)        # per-process; the hashed IPs are never written anywhere
_hits, _all, _lock = {}, [], threading.Lock()

def db():
    c = sqlite3.connect(DB, timeout=10); c.execute("PRAGMA journal_mode=WAL"); return c
def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS tips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,            -- UTC ISO timestamp
            url TEXT NOT NULL, country TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', name TEXT,
            status TEXT NOT NULL DEFAULT 'pending',   -- pending | imported | duplicate | invalid
            imported_at TEXT, queue_item_id TEXT)""")
    for p in (DB, DB + "-wal", DB + "-shm"):
        if os.path.exists(p): os.chmod(p, 0o600)

def rate_ok(ip):
    now = time.time(); k = hashlib.sha256(_salt + ip.encode()).hexdigest()
    with _lock:
        for key in [x for x, v in _hits.items() if not v or v[-1] < now - RATE_WINDOW]: _hits.pop(key, None)
        h = [t for t in _hits.get(k, []) if t > now - RATE_WINDOW]; _all[:] = [t for t in _all if t > now - RATE_WINDOW]
        if len(h) >= RATE_N or len(_all) >= RATE_GLOBAL_N: _hits[k] = h; return False
        h.append(now); _hits[k] = h; _all.append(now); return True

def validate(f):
    g = lambda k: (f.get(k) or "").strip() if isinstance(f.get(k, ""), str) else None
    url, country, note, name = g("url"), (g("country") or "unsure"), g("note"), g("name")
    if None in (url, country, note, name): return None, "Invalid field type."
    if not url: return None, "Please enter the article URL."
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname or "." not in p.hostname or len(url) > MAX_URL or re.search(r"\s", url):
        return None, "The URL must be a full http:// or https:// link."
    m = re.search(r"\b(NO|SE|DK|FI|IS)\b", country.upper()); country = m.group(1) if m else country.upper().replace("NOT SURE", "UNSURE")
    if country not in COUNTRIES: return None, "Country must be NO, SE, DK, FI, IS or unsure."
    if len(note) > MAX_NOTE: return None, f"The note can be at most {MAX_NOTE} characters."
    if len(name) > MAX_NAME: return None, f"The name can be at most {MAX_NAME} characters."
    strip = lambda s: re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", s)
    return {"url": strip(url), "country": country.lower() if country == "UNSURE" else country, "note": strip(note), "name": strip(name) or None}, None

class H(BaseHTTPRequestHandler):
    server_version = "nc-tips/1"; sys_version = ""
    def log_message(self, fmt, *a):  # method, path (without query) and status only – never IP, query or body
        if fmt.startswith('"%s" %s %s') and len(a) >= 2:
            line = str(a[0]).split(" "); path = line[1].split("?")[0] if len(line) > 1 else "?"
            sys.stderr.write(f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} {line[0]} {path} {a[1]}\n")
    def log_error(self, fmt, *a): pass
    def origin_ok(self):
        o = self.headers.get("Origin"); return o is None or o in ORIGINS
    def send(self, code, obj=None, extra=None):
        b = json.dumps(obj if obj is not None else {}).encode()
        self.send_response(code)
        o = self.headers.get("Origin")
        if o in ORIGINS: self.send_header("Access-Control-Allow-Origin", o); self.send_header("Vary", "Origin")
        for k, v in {"Content-Type": "application/json; charset=utf-8", "Content-Length": str(len(b)), "Cache-Control": "no-store",
                     "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", **(extra or {})}.items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)
    def redirect(self, q):
        self.send_response(303); self.send_header("Location", THANKS + "?" + urllib.parse.urlencode(q)); self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store"); self.end_headers()
    def client_ip(self):
        ip = self.client_address[0]
        if ip in ("127.0.0.1", "::1"):  # behind the local Cloudflare tunnel: use the visitor IP it forwards (memory only)
            ip = (self.headers.get("CF-Connecting-IP") or ip).strip()[:64]
        return ip
    def do_OPTIONS(self):
        if self.path.split("?")[0] != "/api/tip" or not self.origin_ok(): return self.send(403, {"ok": False})
        self.send_response(204)
        o = self.headers.get("Origin")
        if o in ORIGINS: self.send_header("Access-Control-Allow-Origin", o); self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS"); self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400"); self.send_header("Content-Length", "0"); self.end_headers()
    def do_GET(self):
        if self.path.split("?")[0] == "/api/health":
            try:
                with db() as c: c.execute("SELECT 1")
                return self.send(200, {"ok": True, "service": "nordic-crypto-tips"})
            except Exception: return self.send(503, {"ok": False})
        self.send(404, {"ok": False, "error": "Not found."})
    def do_POST(self):
        if self.path.split("?")[0] != "/api/tip": return self.send(404, {"ok": False, "error": "Not found."})
        if not self.origin_ok(): return self.send(403, {"ok": False, "error": "Origin not allowed."})
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        is_form = ctype == "application/x-www-form-urlencoded"
        wants_json = "application/json" in (self.headers.get("Accept") or "") or not is_form
        fail = (lambda code, msg: self.send(code, {"ok": False, "error": msg})) if wants_json else (lambda code, msg: self.redirect({"error": msg}))
        try: n = int(self.headers.get("Content-Length") or "-1")
        except ValueError: n = -1
        if n < 0: return self.send(411, {"ok": False, "error": "Content-Length required."})
        if n > MAX_BODY: self.close_connection = True; return fail(413, "The tip is too long (max 4 KB).")
        raw = self.rfile.read(n)
        if not rate_ok(self.client_ip()): return fail(429, "Too many tips from you in a short time. Please try again later.")
        try:
            if ctype == "application/json": f = json.loads(raw.decode("utf-8")); assert isinstance(f, dict)
            elif is_form: f = {k: v[0] for k, v in urllib.parse.parse_qs(raw.decode("utf-8"), keep_blank_values=True).items()}
            else: return fail(415, "Send JSON or form data.")
        except Exception: return fail(400, "Could not read the tip.")
        if (f.get("website") or "").strip():  # honeypot filled in: pretend success, store nothing
            return self.send(200, {"ok": True}) if wants_json else self.redirect({"sent": "1"})
        t, err = validate(f)
        if err: return fail(400, err)
        try:
            with db() as c:
                c.execute("INSERT INTO tips (created_at, url, country, note, name) VALUES (?,?,?,?,?)",
                          (dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), t["url"], t["country"], t["note"], t["name"]))
        except Exception: return fail(503, "The tip service is temporarily offline, try again later.")
        return self.send(201, {"ok": True}) if wants_json else self.redirect({"sent": "1"})

if __name__ == "__main__":
    init_db()
    srv = ThreadingHTTPServer((HOST, PORT), H); srv.daemon_threads = True
    sys.stderr.write(f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} tip server listening on http://{HOST}:{PORT}\n"); sys.stderr.flush()
    srv.serve_forever()
