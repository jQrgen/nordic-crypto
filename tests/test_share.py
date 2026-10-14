#!/usr/bin/env python3
"""Share bars: a normal intent link (no popup), a phone share sheet, and a prefilled event line.
No network."""
import html as htmllib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import build
import i18n

fails = []


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def decoded(href):
    raw = htmllib.unescape(href)
    parts = urllib.parse.urlsplit(raw)
    q = urllib.parse.parse_qs(parts.query, keep_blank_values=True)
    return parts, {k: v[0] for k, v in q.items()}


def anchors(fragment):
    return re.findall(r'<a class="(share-[a-z]+)" href="([^"]*)"([^>]*)>', fragment)


def main():
    missing = json.loads(subprocess.check_output(
        ["node", "-e",
         "const s=require('./vendor/share.js');"
         "const langs=JSON.parse(process.argv[1]);"
         "process.stdout.write(JSON.stringify(langs.filter(l=>!s.LABELS[l]||!s.LABELS[l].native||!s.LABELS[l].share)));",
         json.dumps(i18n.ALL_LANGS)],
        cwd=ROOT, text=True))
    check(missing == [], "share labels for every site language" + (": " + ",".join(missing) if missing else ""))

    url = "https://nordiccrypto.no/nb/calendar/x/?q=1&x=2"
    text = 'Say "hi" & æøå + more'
    raw = subprocess.check_output(
        ["node", os.path.join(ROOT, "tools", "snippets.js"), url, "Page title", "nb", text],
        text=True)
    snip = json.loads(raw)
    bar, script = snip["top"], snip["script"]
    check("window.open" not in bar and "window.open" not in script, "no popup")
    check("about:blank" not in bar and "about:blank" not in script, "no about:blank")
    check("x.com/intent/post" not in bar, "X intent is not the web login URL")
    check("navigator.share" in script and "pointer: coarse" in script, "native share on phones")
    check('class="share-native" hidden' in bar and bar.index("share-native") < bar.index("share-x"), "native share is first and hidden until a phone")
    check("Del:" in bar and ">Del</button>" in bar, "bokmål share label")
    found = {cls: (href, attrs) for cls, href, attrs in anchors(bar)}
    for key in ("share-linkedin", "share-x", "share-facebook"):
        attrs = found[key][1]
        check('target="_blank"' in attrs and 'rel="noopener"' in attrs and "noreferrer" not in attrs, key + " is a normal new tab")
    x_parts, x_q = decoded(found["share-x"][0])
    check(x_parts.scheme == "https" and x_parts.netloc == "twitter.com" and x_parts.path == "/intent/tweet", "X universal link")
    check(x_q.get("text") == text and x_q.get("url") == url and x_q.get("via") == "nordiccryptobot", "X text, url and via round-trip")
    x_query = urllib.parse.urlsplit(htmllib.unescape(found["share-x"][0])).query
    check("%20" in found["share-x"][0] and "%2B" in found["share-x"][0] and "+" not in x_query, "spaces are %20 and plus is %2B")
    fb_parts, fb_q = decoded(found["share-facebook"][0])
    check(fb_parts.netloc == "www.facebook.com" and fb_parts.path == "/sharer/sharer.php" and fb_q.get("u") == url, "Facebook url")
    li_parts, li_q = decoded(found["share-linkedin"][0])
    check(li_parts.netloc == "www.linkedin.com" and li_parts.path == "/sharing/share-offsite/" and li_q.get("url") == url, "LinkedIn url")
    email = re.search(r'class="share-email" href="([^"]*)"', bar)
    check(email and "target=" not in email.group(0), "email stays a mailto link")
    _ep, eq = decoded(email.group(1))
    check(eq.get("subject") == text and url in eq.get("body", ""), "email subject and body")

    ev = {
        "id": "ccc2eea6b213",
        "title": 'Göteborg & "Bitcoin"',
        "start": "2026-10-08T18:00:00+02:00",
        "end": "2026-10-08T21:00:00+02:00",
        "place": "Ölrepubliken, Kronhusgatan 2B, Göteborg",
        "city": "Göteborg",
        "country": "SE",
        "online": False,
        "organiser": "Swedish Bitcoin Meetups",
        "url": "https://www.meetup.com/swedish-bitcoin-meetups/events/316047111/",
        "source": "Swedish Bitcoin Meetups (Meetup.com)",
        "source_url": "https://www.meetup.com/swedish-bitcoin-meetups/",
    }
    build.LANG = "nb"
    check(build.event_share_text(ev) == 'Göteborg & "Bitcoin" · 8. okt. 2026, kl. 18.00 · Göteborg', "bokmål event line")
    build.LANG = "en"
    check(build.event_share_text(ev) == 'Göteborg & "Bitcoin" · 8 Oct 2026, 18:00 · Göteborg', "english event line")
    span = dict(ev, start="2026-08-25T08:30:00+02:00", end="2026-08-26T12:30:00+02:00", city="Lund", title="Conference")
    check(build.event_share_text(span) == "Conference · 25 Aug 2026 – 26 Aug 2026 · Lund", "multi-day line has no clock")
    day = dict(ev, start="2026-10-08T00:00:00+02:00", end="2026-10-08T23:59:00+02:00", city="", title="All day")
    check(build.event_share_text(day) == "All day · 8 Oct 2026", "date-only line drops the clock and an empty city")

    with tempfile.TemporaryDirectory() as site:
        build.SITE = site
        build.PREVIEW = False
        build.LANG = "nb"
        build.build_one_event(ev)
        page = open(os.path.join(site, "nb", "calendar", ev["id"], "index.html"), encoding="utf-8").read()
        nav = page.split('<nav class="share"', 1)[1].split("</nav>", 1)[0]
        href = re.search(r'class="share-x" href="([^"]*)"', nav).group(1)
        _parts, q = decoded(href)
        check(q.get("text") == build.event_share_text(ev), "event page prefills the localized line")
        check(q.get("url") == "https://nordiccrypto.no/nb/calendar/ccc2eea6b213/", "event page url")
        check(q.get("via") == "nordiccryptobot", "event page via")
        check("x.com/intent/post" not in nav and "window.open" not in page and "about:blank" not in page, "event page has no web-login intent or popup")
        check('class="share-native" hidden' in nav, "event page keeps the native button for phones")

    if fails:
        print(f"\n{len(fails)} failed")
        sys.exit(1)
    print("\nall ok")


if __name__ == "__main__":
    main()
