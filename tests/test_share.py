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
    check("a.share-linkedin" in script and "preventDefault" in script, "LinkedIn on a phone opens the share sheet")
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
        li = re.search(r'class="share-linkedin" href="([^"]*)"', nav)
        li_parts, li_q = decoded(li.group(1))
        check(li_parts.geturl().split("?")[0] == "https://www.linkedin.com/sharing/share-offsite/" and list(li_q) == ["url"], "event LinkedIn intent is share-offsite with only url")
        check(li_q.get("url") == "https://nordiccrypto.no/nb/calendar/ccc2eea6b213/", "event LinkedIn url round-trips")
        described = dict(ev, description={
            "text": "Vi møtes for å snakke om bitcoin og lynnettet.",
            "lang": "nb",
            "source_url": ev["url"],
            "source_name": "Swedish Bitcoin Meetups (Meetup.com)",
            "retrieved": "2026-10-07T23:50:00+00:00",
            "i18n": {"en": "We meet to talk about bitcoin and the Lightning Network."},
            "i18n_source": "Vi møtes for å snakke om bitcoin og lynnettet.",
        })
        build.build_one_event(described)
        page = open(os.path.join(site, "nb", "calendar", ev["id"], "index.html"), encoding="utf-8").read()
        head = page.split("</head>", 1)[0]
        def meta(prop):
            m = re.search(r'<meta property="' + prop + r'" content="([^"]*)"', head)
            return htmllib.unescape(m.group(1)) if m else ""
        check(meta("og:title") == 'Göteborg & "Bitcoin"', "og:title is the event title")
        check(meta("og:type") == "article", "og:type is one LinkedIn unfurls")
        check(meta("og:description") == "8. okt. 2026, kl. 18.00 · Göteborg – Vi møtes for å snakke om bitcoin og lynnettet.", "og:description is date, city and the description")
        check("Kronhusgatan" not in meta("og:description"), "og:description leaves out the street address")
        img = meta("og:image")
        check(img == "https://nordiccrypto.no/nb/calendar/ccc2eea6b213/og.png", "og:image is the event card")
        check(meta("og:image:secure_url") == img and meta("og:image:alt") == 'Göteborg & "Bitcoin"', "og image secure url and alt")
        check(meta("og:image:width") == "1200" and meta("og:image:height") == "630" and meta("og:image:type") == "image/png", "og image size and type")
        card = os.path.join(site, "nb", "calendar", ev["id"], "og.png")
        check(os.path.exists(card), "event card file is written beside the page")
        from PIL import Image
        with Image.open(card) as im:
            check(im.size == (1200, 630), "event card is 1200x630")
        build.LANG = "en"
        build.build_one_event(described)
        en_card = os.path.join(site, "calendar", ev["id"], "og.png")
        check(open(card, "rb").read() != open(en_card, "rb").read(), "each language gets its own card")
        en_head = open(os.path.join(site, "calendar", ev["id"], "index.html"), encoding="utf-8").read().split("</head>", 1)[0]
        en_desc = htmllib.unescape(re.search(r'<meta property="og:description" content="([^"]*)"', en_head).group(1))
        check(en_desc.startswith("8 Oct 2026, 18:00 · Göteborg – We meet to talk about bitcoin"), "english preview is localized")

    if fails:
        print(f"\n{len(fails)} failed")
        sys.exit(1)
    print("\nall ok")


if __name__ == "__main__":
    main()
