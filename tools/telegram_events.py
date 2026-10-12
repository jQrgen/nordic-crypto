#!/usr/bin/env python3
"""Post each new upcoming event on nordiccrypto.no to the Nordic Crypto Telegram chat, once.

Reads the published feed (https://nordiccrypto.no/api/v1/events.json by default), so it sees events whether they were
published by CI or by ./publish.sh on the box. A ledger file lists the event ids already posted (or seen). Run from
.github/workflows/telegram-events.yml after every deploy and every 30 minutes.

  - No ledger yet (first run, or the Actions cache expired): every current id is recorded and nothing is posted, so a
    lost ledger never floods the chat with old events.
  - Only events that have not ended are posted, earliest start first, at most --max per run. The rest wait for the next run.
  - An id goes into the ledger only after Telegram accepted the message. A failed send is retried next run.
  - A preview feed ("preview": true) is refused.

Secrets: TELEGRAM_BOT_TOKEN (the existing bot; never printed) and TELEGRAM_CHAT_ID (e.g. @nordiccryptochat or -100…).
Without both it is a dry run: it prints what it would post and does not change the ledger.

  python3 tools/telegram_events.py --ledger .telegram/ledger.json [--feed URL_OR_PATH] [--max 5] [--dry-run]
"""
import argparse, datetime as dt, html, json, os, sys, urllib.parse, urllib.request

FEED = "https://nordiccrypto.no/api/v1/events.json"
FLAGS = {"NO": "🇳🇴", "SE": "🇸🇪", "DK": "🇩🇰", "FI": "🇫🇮", "IS": "🇮🇸", "FO": "🇫🇴", "GL": "🇬🇱", "AX": "🇦🇽"}
UA = "nordic-crypto-telegram-events/1 (+https://nordiccrypto.no/)"


def load_feed(src):
    if src.startswith("https://"):
        req = urllib.request.Request(src + ("&" if "?" in src else "?") + "t=" + str(int(dt.datetime.now().timestamp())),
                                     headers={"User-Agent": UA, "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    with open(src, encoding="utf-8") as fh:
        return json.load(fh)


def parse(ts):
    try:
        d = dt.datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def postable(events, now):
    """Events with an id that have not ended (end, else start), earliest start first."""
    out = []
    for e in events:
        start, end = parse(e.get("start")), parse(e.get("end"))
        if not e.get("id") or not start or not e.get("title"):
            continue
        if (end or start) < now:
            continue
        out.append((start, e["id"], e))
    return [e for _, _, e in sorted(out, key=lambda x: (x[0], x[1]))]


def when(e):
    """'Tue 14 Oct 2026, 18:00–21:00' in the event's own offset (the feed gives local times)."""
    s, end = parse(e["start"]), parse(e.get("end"))
    day = s.strftime("%a %-d %b %Y")
    if s.hour == 0 and s.minute == 0 and (not end or (end.hour, end.minute) in ((0, 0), (23, 59))):
        if end and end.date() > s.date():
            return f"{day} – {end.strftime('%a %-d %b %Y')}"
        return day
    out = f"{day}, {s.strftime('%H:%M')}"
    if end and end.date() == s.date():
        out += f"–{end.strftime('%H:%M')}"
    elif end:
        out += f" – {end.strftime('%a %-d %b %H:%M')}"
    return out


def message(e):
    """Telegram HTML message. Only facts that are in the public feed."""
    E = lambda s: html.escape(str(s or ""), quote=False)
    place = e.get("place") or ""
    city = e.get("city") or ""
    if city and city not in place:
        place = f"{place}, {city}" if place else city
    if not place and e.get("online"):
        place = "Online"
    flag = FLAGS.get((e.get("country") or "").upper(), "")
    lines = [f"📅 <b>New event: {E(e['title'])}</b>", f"🗓 {E(when(e))}"]
    if place:
        lines.append(f"📍 {flag + ' ' if flag else ''}{E(place)}")
    if e.get("organiser"):
        lines.append(f"👥 {E(e['organiser'])}")
    link = e.get("html_url") or e.get("url")
    if link:
        lines.append(f'<a href="{html.escape(link, quote=True)}">Details on Nordic Crypto</a>')
    return "\n".join(lines)


def send(token, chat, text):
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.load(r)
    except urllib.error.HTTPError as err:   # never print the URL: it contains the token
        try: desc = json.load(err).get("description", "")
        except Exception: desc = ""
        return False, f"HTTP {err.code} {desc}".strip()
    except OSError as err:
        return False, type(err).__name__
    return bool(body.get("ok")), body.get("description", "")


def run(feed, ledger_path, *, now, token, chat, max_posts, dry, sender=send, log=print):
    if feed.get("preview"):
        log("telegram events: refusing a preview feed")
        return 2
    events = feed.get("events") or []
    have = os.path.exists(ledger_path)
    ledger = json.load(open(ledger_path, encoding="utf-8")) if have else {"posted": []}
    seen = set(ledger.get("posted") or [])
    if not have:
        ids = sorted({e["id"] for e in events if e.get("id")})
        if not dry:
            save(ledger_path, ids)
        log(f"telegram events: no ledger yet; recorded {len(ids)} current events, posted nothing"
            + (" (dry run, not saved)" if dry else ""))
        return 0
    todo = [e for e in postable(events, now) if e["id"] not in seen]
    if not todo:
        log("telegram events: nothing new")
        return 0
    posted = 0
    for e in todo[:max_posts]:
        text = message(e)
        if dry:
            log(f"--- would post {e['id']}:\n{text}")
            continue
        ok, why = sender(token, chat, text)
        if not ok:
            log(f"telegram events: send failed for {e['id']}: {why}")
            break
        seen.add(e["id"]); posted += 1
        save(ledger_path, sorted(seen))
        log(f"telegram events: posted {e['id']}")
    left = len(todo) - min(len(todo), max_posts)
    log(f"telegram events: {posted} posted, {left} left for the next run" + (" (dry run)" if dry else ""))
    return 0 if dry or posted or not todo else 1


def save(path, ids):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"posted": ids}, fh, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--feed", default=FEED)
    ap.add_argument("--max", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
    dry = a.dry_run or not (token and chat)
    if dry and not a.dry_run:
        print("telegram events: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set; dry run")
    return run(load_feed(a.feed), a.ledger, now=dt.datetime.now(dt.timezone.utc), token=token, chat=chat,
               max_posts=max(1, a.max), dry=dry)


if __name__ == "__main__":
    sys.exit(main())
