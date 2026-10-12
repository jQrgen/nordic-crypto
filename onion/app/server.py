#!/usr/bin/env python3
"""Tor onion tip page for Nordic Crypto.

Static HTML, no JavaScript, no external resources, no analytics. Works with scripts
disabled (Tor Browser Safest). Forwards a tip to the private Cloudflare Worker.
If the Worker does not answer, the tip is stored on this server and retried.

Nothing is written to logs: request lines, tip text, contact and addresses are not printed.
"""
import json, os, ssl, threading, time, urllib.error, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent
COPY = json.loads((HERE / "copy.json").read_text(encoding="utf-8"))
LANGS = [k for k in COPY if not k.startswith("_")]
MAX_BODY = 32768
RATE_N = 30
RATE_WINDOW = 600
QUEUE_DIR = Path(os.environ.get("QUEUE_DIR", "/var/lib/nordic-tips"))
WORKER_URL = (os.environ.get("WORKER_URL") or "").strip().rstrip("/")
ONION_TOKEN = os.environ.get("ONION_INGEST_TOKEN") or ""
ONION_HOST = (os.environ.get("ONION_HOST") or "").strip().rstrip("/")
SYNC_SECONDS = float(os.environ.get("SYNC_SECONDS") or "30")
_hits = []
_lock = threading.Lock()

def _worker_allowed(url):
    u = urlsplit(url)
    if u.scheme == "https" and u.hostname:
        return True
    return u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost")

def _queue_path():
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(QUEUE_DIR, 0o700)
    p = QUEUE_DIR / "queue.jsonl"
    if not p.exists():
        p.touch(mode=0o600)
    os.chmod(p, 0o600)
    return p

def _read_queue():
    p = _queue_path()
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows

def _write_queue(rows):
    p = _queue_path()
    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    tmp = p.with_suffix(".jsonl.tmp")
    tmp.write_text(data, encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, p)
    os.chmod(p, 0o600)

def _post_worker(row):
    if not WORKER_URL or not ONION_TOKEN or not _worker_allowed(WORKER_URL):
        return "down"
    req = urllib.request.Request(
        WORKER_URL + "/api/private-tip",
        data=json.dumps(row).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer " + ONION_TOKEN,
        },
        method="POST",
    )
    try:
        kwargs = {"timeout": 15}
        if urlsplit(WORKER_URL).scheme == "https":
            kwargs["context"] = ssl.create_default_context()
        with urllib.request.urlopen(req, **kwargs) as res:
            res.read(4096)
            code = res.status
    except urllib.error.HTTPError as e:
        code = e.code
        try:
            body = e.read(4096)
        except Exception:
            body = b""
    except Exception:
        return "down"
    if 200 <= code < 300:
        return "ok"
    if code == 429:
        return "rate"
    if 400 <= code < 500:
        return "bad"
    return "down"

def _enqueue(row):
    item = dict(row)
    item["_id"] = os.urandom(8).hex()
    with _lock:
        rows = _read_queue()
        rows.append(item)
        _write_queue(rows)

def sync_once():
    with _lock:
        rows = list(_read_queue())
    if not rows:
        return
    done = []
    for row in rows:
        payload = {k: v for k, v in row.items() if k != "_id"}
        result = _post_worker(payload)
        if result in ("ok", "bad"):
            done.append(row.get("_id"))
            continue
        break
    if not done:
        return
    with _lock:
        current = _read_queue()
        _write_queue([r for r in current if r.get("_id") not in set(done)])

def _sync_loop():
    while True:
        time.sleep(SYNC_SECONDS)
        try:
            sync_once()
        except Exception:
            pass

def _rate_ok():
    now = time.time()
    with _lock:
        global _hits
        _hits = [t for t in _hits if now - t < RATE_WINDOW]
        if len(_hits) >= RATE_N:
            return False
        _hits.append(now)
        return True

def _esc(s):
    return (str(s if s is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))

def _lang(code):
    return code if code in COPY else "en"

def _page_for(lang):
    if ONION_HOST.startswith("http://") and ONION_HOST.endswith(".onion"):
        return ONION_HOST + "/" + lang + "/"
    return "/" + lang + "/"

def _page(lang, kind, detail=""):
    s = COPY[_lang(lang)]
    direction = s.get("dir") or "ltr"
    links = " ".join(
        f'<a href="/{_esc(code)}/" hreflang="{_esc(code)}" lang="{_esc(code)}">{_esc(COPY[code]["name"])}</a>'
        for code in LANGS
    )
    if kind == "form":
        main = f"""<p>{_esc(s["tip_onion_page"])}</p>
<p>{_esc(s["tip_intro"])}</p>
<p><b>{_esc(s["tip_privacy_h"])}.</b> {_esc(s["tip_privacy"])}</p>
<form method="post" action="/{_esc(lang)}/" accept-charset="utf-8">
<input type="hidden" name="language" value="{_esc(lang)}">
<input type="hidden" name="page" value="{_esc(_page_for(lang))}">
<p class="hp"><label for="website">{_esc(s["tip_honeypot"])}</label><input id="website" name="website" tabindex="-1" autocomplete="off"></p>
<p><label for="tip"><b>{_esc(s["tip_label"])}</b> {_esc(s["tip_required"])}</label><br>
<textarea id="tip" name="tip" required maxlength="8000" rows="8"></textarea><br><span class="meta">{_esc(s["tip_hint"])}</span></p>
<p><label for="attachments"><b>{_esc(s["tip_links"])}</b></label><br>
<textarea id="attachments" name="attachments" maxlength="4000" rows="3"></textarea><br><span class="meta">{_esc(s["tip_links_opt"])}</span></p>
<p><label for="contact"><b>{_esc(s["tip_contact"])}</b></label><br>
<input id="contact" name="contact" type="text" maxlength="500" autocomplete="off"><br><span class="meta">{_esc(s["tip_contact_opt"])}</span></p>
<p><button type="submit">{_esc(s["tip_send"])}</button></p>
</form>"""
    elif kind == "thanks":
        main = f"<p>{_esc(s['tip_thanks'])}</p><p><a href=\"/{_esc(lang)}/\">{_esc(s['tip_title'])}</a></p>"
    elif kind == "queued":
        main = f"<p>{_esc(s['tip_onion_queued'])}</p><p><a href=\"/{_esc(lang)}/\">{_esc(s['tip_title'])}</a></p>"
    else:
        main = f"<p>{_esc(detail or s['tip_fail'])}</p><p><a href=\"/{_esc(lang)}/\">{_esc(s['tip_title'])}</a></p>"
    return f"""<!doctype html>
<html lang="{_esc(lang if lang in COPY else 'en')}" dir="{_esc(direction)}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer"><meta name="robots" content="noindex">
<title>{_esc(s["tip_title"])}</title>
<style>
html,body,p,h1,label,textarea,input,button,a,form{{text-align:left}}
body{{margin:0;padding:16px 20px;max-width:40rem;font:16px/1.5 sans-serif;background:#fff;color:#111}}
textarea,input[type=text]{{display:block;width:100%;max-width:40rem;font:inherit;text-align:left}}
button{{font:inherit;text-align:left}}
.meta{{color:#333}}
.hp{{position:absolute;left:-9999px;height:1px;width:1px;overflow:hidden}}
nav{{margin:0 0 12px}}
nav a{{margin-right:10px}}
</style></head>
<body>
<nav aria-label="{_esc(s["tip_lang"])}">{links}</nav>
<h1>{_esc(s["tip_title"])}</h1>
{f'<p>{_esc(s["tip_lead"])}</p>' if kind == "form" else ""}
{main}
</body></html>"""

def _field(form, name):
    vals = form.get(name) or [""]
    return vals[0] if vals else ""

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def version_string(self):
        return "tip"

    def log_message(self, fmt, *args):
        return

    def _send(self, code, html, extra=None):
        data = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/health":
            self._send(200, "<!doctype html><html><body><p>ok</p></body></html>")
            return
        if path in ("/", ""):
            self.send_response(302)
            self.send_header("Location", "/en/")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        parts = [p for p in path.split("/") if p]
        if len(parts) == 1 and parts[0] in COPY:
            self._send(200, _page(parts[0], "form"))
            return
        self._send(404, _page("en", "error"))

    def do_POST(self):
        path = urlsplit(self.path).path
        parts = [p for p in path.split("/") if p]
        lang = parts[0] if len(parts) == 1 and parts[0] in COPY else "en"
        s = COPY[_lang(lang)]
        try:
            n = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            n = 0
        if n < 0 or n > MAX_BODY:
            self._send(413, _page(lang, "error", s["tip_long"]))
            return
        raw = self.rfile.read(n)
        form = parse_qs(raw.decode("utf-8", "replace"), keep_blank_values=True)
        if _field(form, "website").strip():
            self._send(200, _page(lang, "thanks"))
            return
        if not _rate_ok():
            self._send(429, _page(lang, "error", s["tip_rate"]))
            return
        tip = _field(form, "tip").strip()
        if not tip:
            self._send(400, _page(lang, "error", s["tip_empty"]))
            return
        if len(tip) > 8000:
            self._send(400, _page(lang, "error", s["tip_long"]))
            return
        contact = _field(form, "contact").strip()
        if len(contact) > 500:
            self._send(400, _page(lang, "error", s["tip_fail"]))
            return
        links = [ln.strip() for ln in _field(form, "attachments").replace(",", "\n").splitlines() if ln.strip()]
        if len(links) > 10 or any(len(ln) > 2000 or not ln.startswith(("http://", "https://")) for ln in links):
            self._send(400, _page(lang, "error", s["tip_bad_link"]))
            return
        language = _field(form, "language").strip().lower() or lang
        if language not in COPY:
            language = "en"
        page = _field(form, "page").strip() or _page_for(language)
        row = {
            "tip": tip,
            "contact": contact,
            "attachments": "\n".join(links),
            "language": language,
            "page": page,
        }
        result = _post_worker({**row, "contact": contact})
        if result == "ok":
            self._send(200, _page(lang, "thanks"))
            return
        if result == "rate":
            self._send(429, _page(lang, "error", s["tip_rate"]))
            return
        if result == "bad":
            self._send(400, _page(lang, "error", s["tip_fail"]))
            return
        _enqueue(row)
        self._send(202, _page(lang, "queued"))

def drop_privs():
    uid = int(os.environ.get("DROP_UID") or "0")
    if os.geteuid() != 0 or not uid:
        return
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    os.chown(QUEUE_DIR, uid, uid)
    os.chmod(QUEUE_DIR, 0o700)
    os.setgid(uid)
    os.setuid(uid)

def main():
    drop_privs()
    host = os.environ.get("BIND", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    threading.Thread(target=_sync_loop, daemon=True).start()
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.serve_forever()

if __name__ == "__main__":
    main()
