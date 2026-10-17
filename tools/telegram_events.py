#!/usr/bin/env python3
"""Post each new upcoming event (or, with --kind news, each new story) on nordiccrypto.no to the Telegram chat, once.

Reads the published feed (https://nordiccrypto.no/api/v1/events.json by default), so it sees events whether they were
published by CI or by ./publish.sh on the box. A ledger file lists the event ids already posted (or seen). Run from
.github/workflows/telegram-events.yml after every deploy and every 30 minutes.

  - No ledger yet (first run, or the Actions cache expired): every current id is recorded and nothing is posted, so a
    lost ledger never floods the chat with old events.
  - Only events that have not ended are posted, earliest start first, at most --max per run. The rest wait for the next run.
  - An id goes into the ledger only after Telegram accepted the message. A failed send is retried next run.
  - A preview feed ("preview": true) is refused.
  - --kind news reads /api/v1/news.json and posts one digest of the stories not in its own ledger, published in the
    last --max-age-days. It waits until the feed's "updated" is 10 minutes old, so one publish round is one post.
  - --post ID[,ID] puts those ids in the digest now, even if already in the ledger or old: a manual backfill.

Secrets: TELEGRAM_BOT_TOKEN (the existing bot; never printed) and TELEGRAM_CHAT_ID (e.g. @nordiccryptochat or -100…).
Without both it is a dry run: it prints what it would post and does not change the ledger.

  python3 tools/telegram_events.py --ledger .telegram/ledger.json [--feed URL_OR_PATH] [--max 5] [--dry-run]
"""
import argparse, datetime as dt, html, json, os, sys, urllib.parse, urllib.request, zoneinfo

FEED = "https://nordiccrypto.no/api/v1/events.json"
NEWS_FEED = "https://nordiccrypto.no/api/v1/news.json"
FLAGS = {"NO": "🇳🇴", "SE": "🇸🇪", "DK": "🇩🇰", "FI": "🇫🇮", "IS": "🇮🇸", "FO": "🇫🇴", "GL": "🇬🇱", "AX": "🇦🇽"}
OSLO = zoneinfo.ZoneInfo("Europe/Oslo")
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


def fresh_news(items, now, max_age_days):
    """Stories with an id and title published in the last max_age_days, oldest first."""
    out = []
    for e in items:
        pub = parse(e.get("published"))
        if not e.get("id") or not pub or not (e.get("title_en") or e.get("title")):
            continue
        if pub < now - dt.timedelta(days=max_age_days):
            continue
        out.append((pub, e["id"], e))
    return [e for _, _, e in sorted(out, key=lambda x: (x[0], x[1]))]


def news_digests(items, now, limit=4096):
    """One HTML digest for the round, oldest first; split into more messages only past Telegram's limit."""
    E = lambda s: html.escape(str(s or ""), quote=False)
    head = f"📰 <b>Nye saker på Nordic Crypto – {now.astimezone(OSLO).strftime('%-d.%-m.%Y')}</b>"
    out, ids, text = [], [], head
    for e in items:
        flag = FLAGS.get((e.get("country") or "").upper(), "")
        title = E(e.get("title_en") or e["title"])
        link = e.get("html_url") or e.get("url")
        line = (f"{flag} " if flag else "• ") + (f'<a href="{html.escape(link, quote=True)}">{title}</a>' if link else title)
        if e.get("source_name"):
            line += f" – {E(e['source_name'])}"
        if ids and len(text) + 2 + len(line) > limit:
            out.append((ids, text)); ids, text = [], head
        ids.append(e["id"]); text += "\n\n" + line
    return out + ([(ids, text)] if ids else [])


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


def run(feed, ledger_path, *, now, token, chat, max_posts, dry, sender=send, log=print,
        kind="events", force=(), max_age_days=7, settle_minutes=10):
    if feed.get("preview"):
        log(f"telegram {kind}: refusing a preview feed")
        return 2
    events = (feed.get("items") if kind == "news" else feed.get("events")) or []
    have = os.path.exists(ledger_path)
    ledger = json.load(open(ledger_path, encoding="utf-8")) if have else {"posted": []}
    seen = set(ledger.get("posted") or [])
    force = [i for i in force if i]
    if not have:
        ids = sorted({e["id"] for e in events if e.get("id")})
        seen = set(ids)
        if not dry:
            save(ledger_path, ids)
        log(f"telegram {kind}: no ledger yet; recorded {len(ids)} current {kind}" + ("" if force else ", posted nothing")
            + (" (dry run, not saved)" if dry else ""))
        if not force:
            return 0
    byid = {e.get("id"): e for e in events}
    for i in force:
        if i not in byid:
            log(f"telegram {kind}: {i} is not in the feed")
    if kind == "news":
        updated = parse(feed.get("updated"))
        if not force and updated and now - updated < dt.timedelta(minutes=settle_minutes):
            log(f"telegram news: feed updated {updated.isoformat()}, waiting for the publish round to settle")
            return 0
        fresh = [e for e in fresh_news(events, now, max_age_days) if e["id"] not in seen]
        forced = [byid[i] for i in dict.fromkeys(force) if i in byid]
        todo = fresh_news(forced, now, 36500) + [e for e in fresh if e["id"] not in force]
        todo.sort(key=lambda e: (parse(e["published"]), e["id"]))
        msgs = news_digests(todo, now)
    else:
        todo = [e for e in postable(events, now) if e["id"] not in seen]
        msgs = [([e["id"]], message(e)) for e in todo[:max_posts]]
    if not todo:
        log(f"telegram {kind}: nothing new")
        return 0
    posted = 0
    for ids, text in msgs:
        if dry:
            log(f"--- would post {', '.join(ids)}:\n{text}")
            continue
        ok, why = sender(token, chat, text)
        if not ok:
            log(f"telegram {kind}: send failed for {', '.join(ids)}: {why}")
            break
        seen.update(ids); posted += len(ids)
        save(ledger_path, sorted(seen))
        log(f"telegram {kind}: posted {', '.join(ids)}")
    left = 0 if dry else len(todo) - posted
    log(f"telegram {kind}: {posted} posted, {left} left for the next run" + (" (dry run)" if dry else ""))
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
    ap.add_argument("--kind", choices=("events", "news"), default="events")
    ap.add_argument("--feed")
    ap.add_argument("--post", default="", help="comma-separated ids to post now (backfill)")
    ap.add_argument("--max-age-days", type=int, default=7)
    ap.add_argument("--max", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
    dry = a.dry_run or not (token and chat)
    if dry and not a.dry_run:
        print(f"telegram {a.kind}: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set; dry run")
    feed = a.feed or (NEWS_FEED if a.kind == "news" else FEED)
    force = [i.strip() for i in a.post.replace(" ", ",").split(",") if i.strip()]
    return run(load_feed(feed), a.ledger, now=dt.datetime.now(dt.timezone.utc), token=token, chat=chat,
               max_posts=max(1, a.max), dry=dry, kind=a.kind, force=force, max_age_days=a.max_age_days)


if __name__ == "__main__":
    sys.exit(main())
