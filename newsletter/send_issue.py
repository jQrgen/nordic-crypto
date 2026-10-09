#!/usr/bin/env python3
"""Send one published newsletter issue (or a digest file) to confirmed addresses in the private D1 list.

The list is the Cloudflare D1 table `subscribers` (database nordic-crypto-tips), the same table POST /api/subscribe
writes. Addresses are never printed and never written to git. Pending and unsubscribed rows are skipped.

Nothing is delivered unless MAIL_SEND_ENABLED=1. Without that flag, or with --dry-run, the script prints counts only.

Provider (same names as tipworker/src/mailer.js; values are env placeholders, never committed):
  MAIL_PROVIDER=resend|mailgun|webhook
  RESEND_API_KEY
  MAILGUN_API_KEY, MAILGUN_DOMAIN, optional MAILGUN_API_BASE (default https://api.mailgun.net)
  MAIL_WEBHOOK_URL (https only), MAIL_WEBHOOK_TOKEN
  MAIL_FROM_NORDIC_CRYPTO="Nordic Crypto <FROM-ADDRESS>"
  UNSUB_SECRET                 # the same secret as the Worker (deploy.sh / wrangler secret)
  NEWSLETTER_WORKER_ORIGIN     # https://<worker>.workers.dev  (unsubscribe links)
  CLOUDFLARE_API_TOKEN         # remote D1. Or pass --local / --from-json.

Cloudflare Email Routing can receive mail for the domain. It does not send this list. See newsletter/email-list.md.

Usage:
  .venv/bin/python newsletter/send_issue.py --issue 001 --dry-run
  MAIL_SEND_ENABLED=1 .venv/bin/python newsletter/send_issue.py --issue 001
  .venv/bin/python newsletter/send_issue.py --html newsletter/out/digest-DATE-en.html --text newsletter/out/digest-DATE-en.txt --subject "Nordic Crypto weekly" --lang en --dry-run
"""
import argparse, hashlib, hmac, html, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import site_url
SIGN_OFF = "The Nordic Crypto team"
SIGNED = (SIGN_OFF, "Nordic Crypto-teamet", "Nordic Crypto-laget", "Nordic Crypto-holdet", "Nordic Crypton tiimi", "Nordic Crypto-hópurinn")
SITE = "nordic-crypto"
LANGS = ["en", "nn", "nb", "sv", "da", "fi", "is"]
COPY = {
 "en": dict(read="Read this issue on Nordic Crypto", unsub="Unsubscribe", why="You get this email because you subscribed to the Nordic Crypto newsletter."),
 "nn": dict(read="Les utgåva på Nordic Crypto", unsub="Meld deg av", why="Du får denne e-posten fordi du har abonnert på nyheitsbrevet frå Nordic Crypto."),
 "nb": dict(read="Les utgaven på Nordic Crypto", unsub="Meld deg av", why="Du får denne e-posten fordi du har abonnert på nyhetsbrevet fra Nordic Crypto."),
 "sv": dict(read="Läs utgåvan på Nordic Crypto", unsub="Avsluta prenumerationen", why="Du får det här mejlet eftersom du prenumererar på Nordic Cryptos nyhetsbrev."),
 "da": dict(read="Læs udgaven på Nordic Crypto", unsub="Afmeld", why="Du får denne e-mail, fordi du abonnerer på Nordic Cryptos nyhedsbrev."),
 "fi": dict(read="Lue numero Nordic Cryptossa", unsub="Peru tilaus", why="Saat tämän viestin, koska olet tilannut Nordic Crypton uutiskirjeen."),
 "is": dict(read="Lesa tölublaðið á Nordic Crypto", unsub="Segja upp áskrift", why="Þú færð þennan póst vegna þess að þú ert áskrifandi að fréttabréfi Nordic Crypto."),
}
TAG = re.compile(r"<[^>]+>")
PREFIX = {l: ("" if l == "en" else l + "/") for l in LANGS}

def unsub_sig(secret, row_id, email, site=SITE):
    """First 40 hex chars of HMAC-SHA-256(secret, 'id|email|site'), same as tipworker/src/newsletter.js."""
    msg = f"{row_id}|{email}|{site}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()[:40]

def unsub_url(origin, secret, row):
    if not origin or not secret or not row.get("id"): return ""
    origin = origin.rstrip("/")
    sig = unsub_sig(secret, row["id"], row["email"], row.get("site") or SITE)
    q = urllib.parse.urlencode({"id": str(row["id"]), "sig": sig, "s": row.get("site") or SITE, "l": row.get("lang") or "en"})
    return f"{origin}/api/unsubscribe?{q}"

def plain_from_html(fragment):
    text = TAG.sub("", fragment)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def compose(body_html, lang, page, unsub, subject, plain=None):
    """Left-aligned HTML and plain text. Unsubscribe is per recipient. Sign-off is not repeated when the issue already has it."""
    c = COPY.get(lang) or COPY["en"]
    body = site_url.expand(body_html or "").replace("{{unsubscribe}}", unsub or "")
    sign = "" if any(s in body for s in SIGNED) else f'<p style="text-align:left">{html.escape(SIGN_OFF)}</p>'
    link = f'<p style="text-align:left"><a href="{html.escape(page)}">{html.escape(c["read"])}</a></p>' if page else ""
    bye = (f'<p style="text-align:left;font-size:13px;color:#4B5563">{html.escape(c["why"])} '
           f'<a href="{html.escape(unsub)}">{html.escape(c["unsub"])}</a></p>') if unsub else f'<p style="text-align:left;font-size:13px;color:#4B5563">{html.escape(c["why"])}</p>'
    page_html = (f'<!doctype html><html lang="{html.escape(lang)}"><head><meta charset="utf-8"><title>{html.escape(subject)}</title></head>'
                 f'<body style="margin:0;padding:16px;text-align:left;font:16px/1.5 Arial,sans-serif;color:#111">'
                 f'<div style="max-width:640px;margin:0;text-align:left">{link}{body}{sign}{bye}</div></body></html>')
    base = (plain or plain_from_html(body)).replace("{{unsubscribe}}", unsub or "")
    bits = []
    if page and page not in base: bits.append(f"{c['read']}: {page}")
    bits.append(base.strip())
    if not any(s in base for s in SIGNED): bits.append(SIGN_OFF)
    if c["why"] not in base: bits.append(c["why"])
    if unsub and unsub not in base: bits.append(unsub)
    return page_html, "\n\n".join(b for b in bits if b)

def confirmed_rows(rows, site=SITE, lang=None):
    seen, out = set(), []
    for r in rows:
        email = (r.get("email") or "").strip().lower()
        if r.get("site") != site or r.get("status") != "confirmed" or not email or email in seen: continue
        if lang and (r.get("lang") or "") != lang: continue
        seen.add(email)
        out.append({"id": r.get("id"), "email": email, "site": site, "lang": r.get("lang") or "en", "status": "confirmed"})
    return out

def issue_parts(issue_id, lang, root=ROOT):
    pub = os.path.join(root, "newsletter", "published")
    meta = json.load(open(os.path.join(pub, "issues.json"), encoding="utf-8"))
    iss = next((i for i in meta.get("issues", []) if str(i.get("id")) == str(issue_id)), None)
    if not iss: raise SystemExit(f"send: no published issue {issue_id}")
    lang = lang if lang in LANGS else "en"
    path = os.path.join(pub, str(issue_id), "issue.html" if lang == "en" else f"issue.{lang}.html")
    used = lang
    if not os.path.exists(path):
        path = os.path.join(pub, str(issue_id), "issue.html"); used = iss.get("lang") or "en"
    title = (iss.get("title_i18n") or {}).get(used) if used != "en" else None
    title = title or iss.get("title") or "Nordic Crypto"
    page = site_url.join(PREFIX.get(used, "") + f"newsletter/{issue_id}/")
    return title, open(path, encoding="utf-8").read(), page, used

def from_address(env):
    return env.get("MAIL_FROM_NORDIC_CRYPTO") or env.get("MAIL_FROM") or ""

def _post(url, data, headers, timeout=30):
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 300, ""
    except urllib.error.HTTPError as e:
        return False, "provider error " + str(e.code)
    except Exception:
        return False, "send failed"

def provider_send(env, msg):
    """msg: to, subject, text, html, unsubscribe, from. Never includes the address in the reason string."""
    p = (env.get("MAIL_PROVIDER") or "none").lower()
    sender = msg.get("from") or ""
    if p == "resend":
        if not env.get("RESEND_API_KEY") or not sender: return False, "resend not configured"
        payload = {"from": sender, "to": [msg["to"]], "subject": msg["subject"], "text": msg["text"], "html": msg["html"]}
        if msg.get("unsubscribe"):
            payload["headers"] = {"List-Unsubscribe": f"<{msg['unsubscribe']}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
        return _post("https://api.resend.com/emails", json.dumps(payload).encode(),
                     {"Authorization": "Bearer " + env["RESEND_API_KEY"], "Content-Type": "application/json"})
    if p == "mailgun":
        domain, key = env.get("MAILGUN_DOMAIN") or "", env.get("MAILGUN_API_KEY") or ""
        if not domain or not key or not sender: return False, "mailgun not configured"
        base = (env.get("MAILGUN_API_BASE") or "https://api.mailgun.net").rstrip("/")
        fields = {"from": sender, "to": msg["to"], "subject": msg["subject"], "text": msg["text"], "html": msg["html"]}
        if msg.get("unsubscribe"):
            fields["h:List-Unsubscribe"] = f"<{msg['unsubscribe']}>"
            fields["h:List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        body = urllib.parse.urlencode(fields).encode()
        token = __import__("base64").b64encode(("api:" + key).encode()).decode()
        return _post(f"{base}/v3/{domain}/messages", body, {"Authorization": "Basic " + token, "Content-Type": "application/x-www-form-urlencoded"})
    if p == "webhook":
        url = env.get("MAIL_WEBHOOK_URL") or ""
        if not url.startswith("https://"): return False, "webhook not configured"
        payload = {k: msg.get(k, "") for k in ("to", "subject", "text", "html", "unsubscribe")}
        payload["from"] = sender; payload["site"] = SITE; payload["kind"] = "issue"
        return _post(url, json.dumps(payload).encode(),
                     {"Authorization": "Bearer " + (env.get("MAIL_WEBHOOK_TOKEN") or ""), "Content-Type": "application/json"})
    return False, "no provider configured"

def d1_rows(local):
    """Confirmed rows for this site, including id (needed for the unsubscribe link). Addresses stay in the result, not in stdout."""
    import subprocess
    if not local and not os.environ.get("CLOUDFLARE_API_TOKEN"):
        raise SystemExit("send: needs CLOUDFLARE_API_TOKEN (or --local / --from-json)")
    env = dict(os.environ, WRANGLER_SEND_METRICS="false")
    n22 = os.path.expanduser("~/.local/node22/bin")
    if os.path.isdir(n22): env["PATH"] = n22 + os.pathsep + env.get("PATH", "")
    sql = "SELECT id, email, site, lang, status FROM subscribers WHERE status = 'confirmed' AND site = 'nordic-crypto'"
    p = subprocess.run(["npx", "--no-install", "wrangler", "d1", "execute", "nordic-crypto-tips",
                        "--local" if local else "--remote", "--json", "--command", sql],
                       cwd=os.path.join(ROOT, "tipworker"), env=env, capture_output=True, text=True, timeout=180)
    if p.returncode != 0: raise SystemExit("send: wrangler d1 execute failed (no row data printed)")
    out = json.loads(p.stdout); out = out if isinstance(out, list) else [out]
    return [r for part in out for r in (part.get("results") or [])]

def ledger_path(key):
    safe = re.sub(r"[^A-Za-z0-9._-]", "-", key)[:80]
    return os.path.join(ROOT, "state", "newsletter", f"sent-{safe}.json")

def load_ledger(path):
    try: return set(json.load(open(path, encoding="utf-8")).get("ids") or [])
    except FileNotFoundError: return set()

def save_ledger(path, ids):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump({"ids": sorted(ids)}, f)
    os.chmod(path, 0o600)

def deliver(rows, bodies, env, sender, dry, ledger, force, sleep_s):
    """bodies(lang) -> (subject, html_fragment, page). Returns counts. Never prints an address."""
    sent = skipped = failed = 0
    reasons = {}
    done = set() if force else load_ledger(ledger)
    origin, secret = (env.get("NEWSLETTER_WORKER_ORIGIN") or "").rstrip("/"), env.get("UNSUB_SECRET") or ""
    frm = from_address(env)
    if not dry:
        if not frm: raise SystemExit("send: set MAIL_FROM_NORDIC_CRYPTO (placeholder, not committed)")
        if not secret or not origin.startswith("https://"): raise SystemExit("send: set UNSUB_SECRET and NEWSLETTER_WORKER_ORIGIN (https)")
    for row in rows:
        if row.get("id") in done:
            skipped += 1; continue
        lang = row.get("lang") if row.get("lang") in COPY else "en"
        subject, fragment, page, plain = bodies(lang)
        link = unsub_url(origin, secret, row) if secret and origin.startswith("https://") and row.get("id") else ""
        if not dry and not link:
            failed += 1; reasons["missing unsubscribe id"] = reasons.get("missing unsubscribe id", 0) + 1; continue
        html_body, text = compose(fragment, lang, page, link, subject, plain)
        if dry:
            sent += 1; continue
        ok, reason = sender(env, {"to": row["email"], "from": frm, "subject": subject, "text": text, "html": html_body, "unsubscribe": link})
        if ok:
            sent += 1
            if row.get("id") is not None:
                done.add(row["id"]); save_ledger(ledger, done)
        else:
            failed += 1; reasons[reason or "send failed"] = reasons.get(reason or "send failed", 0) + 1
        if sleep_s: time.sleep(sleep_s)
    return sent, skipped, failed, reasons

def main(argv=None, sender=None, env=None):
    a = argparse.ArgumentParser()
    a.add_argument("--issue"); a.add_argument("--html"); a.add_argument("--text"); a.add_argument("--subject")
    a.add_argument("--lang", choices=LANGS); a.add_argument("--site", default=SITE, choices=[SITE])
    a.add_argument("--dry-run", action="store_true"); a.add_argument("--local", action="store_true")
    a.add_argument("--from-json"); a.add_argument("--force", action="store_true"); a.add_argument("--sleep", type=float, default=0.6)
    o = a.parse_args(argv)
    if not o.issue and not o.html: raise SystemExit("send: pass --issue 001 or --html FILE")
    env = dict(os.environ if env is None else env)
    dry = o.dry_run or env.get("MAIL_SEND_ENABLED") != "1"
    rows = json.load(open(o.from_json, encoding="utf-8")) if o.from_json else d1_rows(o.local)
    rows = confirmed_rows(rows, o.site, o.lang)
    if o.issue:
        def bodies(lang):
            title, fragment, page, _used = issue_parts(o.issue, lang)
            return title, fragment, page, None
        key = "issue-" + str(o.issue)
    else:
        fragment = open(o.html, encoding="utf-8").read()
        extra = open(o.text, encoding="utf-8").read() if o.text else None
        subject = o.subject or "Nordic Crypto"
        page = site_url.join(PREFIX.get(o.lang or "en", "") + "newsletter/")
        def bodies(lang):
            return subject, fragment, page, extra
        key = "file-" + os.path.basename(o.html)
    if sender is None: sender = provider_send
    sent, skipped, failed, reasons = deliver(rows, bodies, env, sender, dry, ledger_path(key), o.force, 0 if dry else o.sleep)
    mode = "dry-run" if dry else "sent"
    why = "" if not reasons else " (" + ", ".join(f"{n} {k}" for k, n in sorted(reasons.items())) + ")"
    print(f"send: {mode} {sent}, skipped {skipped}, failed {failed}, confirmed {len(rows)}{why}")
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
