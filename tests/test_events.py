#!/usr/bin/env python3
"""Conference listing ingest (listing-jsonld). No network."""
import datetime as dt
import inspect
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import event_block
import events

fails = []


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


LISTING = """
<html><head><title>Blockchain Conferences in Norway</title></head><body>
<a href="/event-example-oslo-no-202611-1">Conference Blockchain
International Conference on Example Blockchain Sat, Nov 21, 2026 - Sun, Nov 22, 2026 Oslo, Norway</a>
<a href="/event-old-oslo-no-202601-9">Blockchain conference Wed, Jan 7, 2026 - Thu, Jan 8, 2026 Oslo, Norway</a>
<a href="/event-algebra-oslo-no-202612-2">Conference Mathematics International Conference on homological algebra</a>
<a href="https://example.com/not-an-event">Blockchain meetup elsewhere</a>
</body></html>
"""

EVENT = """
<html><head><title>Example</title></head><body>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Event","name":"International Conference on Example Blockchain",
 "startDate":"2026-11-21T00:00:00.000Z","endDate":"2026-11-22T00:00:00.000Z",
 "description":"A blockchain conference.","url":"https://internationalconferencealerts.com/event-example-oslo-no-202611-1",
 "location":{"@type":"Place","name":"Oslo, Norway","address":{"@type":"PostalAddress","addressLocality":"Oslo","addressCountry":"Norway"}},
 "organizer":{"@type":"Organization","name":"Example Org","email":"info@example.test"}}
</script>
<div data-slot="card"><div>Venue</div><p>Example Hall<br>Karl Johans gate 1<br>0159 Oslo<br>Norway</p></div>
<img src="/photo.jpg" alt="hall">
</body></html>
"""

SRC = {
    "id": "ica-blockchain-norway",
    "name": "International Conference Alerts – blockchain, Norway",
    "url": "https://internationalconferencealerts.com/blockchain/norway",
    "type": "listing-jsonld",
    "link_pattern": "^/event-[a-z0-9-]+$",
    "max_links": 40,
    "trusted": False,
    "country": "NO",
}


def main():
    links = events.listing_event_links(LISTING, SRC["url"], SRC["link_pattern"])
    check([x["url"].rsplit("/", 1)[-1] for x in links] == [
        "event-example-oslo-no-202611-1", "event-old-oslo-no-202601-9", "event-algebra-oslo-no-202612-2"], "event links only")
    a, b = events.listing_span(links[0]["text"])
    check(a == dt.date(2026, 11, 21) and b == dt.date(2026, 11, 22), "card dates")
    fetched = []

    def fetch_text(url):
        fetched.append(url)
        return EVENT

    def matches(text):
        return "blockchain" in text.lower()

    evs, n_links, errs = events.listing_jsonld_events(SRC, LISTING, fetch_text, matches, dt.date(2026, 10, 6), "Europe/Oslo")
    check(n_links == 2, f"keyword filter keeps 2 links, got {n_links}")
    check(fetched == ["https://internationalconferencealerts.com/event-example-oslo-no-202611-1"], "finished card is not fetched")
    check(errs == [], "no page errors")
    check(len(evs) == 1, "one event")
    ev = evs[0]
    check(ev["title"].startswith("International Conference on Example Blockchain"), "title")
    check(ev["start"].isoformat() == "2026-11-21T00:00:00+01:00", f"start civil day {ev['start'].isoformat()}")
    check(ev["end"].isoformat() == "2026-11-22T23:59:00+01:00", f"end inclusive {ev['end'].isoformat()}")
    check(ev["place"] == "Example Hall, Karl Johans gate 1, 0159 Oslo, Norway", f"venue {ev['place']}")
    check("photo" not in ev["place"] and "example.test" not in str(ev), "no photo or email copied")
    check(ev["organiser"] == "Example Org" and ev["city"] == "Oslo" and ev["country_hint"] == "Norway", "organiser, city, country")
    check(ev["url"].endswith("/event-example-oslo-no-202611-1"), "links to the event page")
    check(events.listing_blocked("<html><title>Just a moment...</title></html>"), "challenge page detected")
    try:
        events.listing_jsonld_events(SRC, "<html><title>Just a moment...</title></html>", fetch_text, matches, dt.date(2026, 10, 6), "Europe/Oslo")
        check(False, "challenge should raise")
    except RuntimeError as ex:
        check("Cloudflare" in str(ex), "challenge raises")
    # summer time: 23 Oct 2026 is still CEST
    z = events.civil_from_utc_midnight(dt.datetime(2026, 10, 23, tzinfo=dt.timezone.utc), "Europe/Oslo")
    check(z.isoformat() == "2026-10-23T00:00:00+02:00", f"CEST day {z.isoformat()}")
    blocklist(ev)
    if fails:
        print(f"{len(fails)} failed")
        sys.exit(1)
    print("all ok")


def blocklist(parsed):
    """Predatory listings are refused by the pipeline and are not stored."""
    blocked = [
        {"url": "https://internationalconferencealerts.com/event-example-oslo-no-202611-1"},
        {"url": "https://www.conferencealerts.com/blockchain/norway"},
        {"url": "https://conferencealerts.org/city/oslo"},
        {"url": "https://conferencealert.com/e"},
        {"url": "https://allconferencealert.com/event"},
        {"url": "https://www.allconferencealert.net/e"},
        {"url": "https://allconferencealerts.com/e"},
        {"url": "https://waset.org/conference"},
        {"url": "https://www.conferenceindex.org/event"},
        {"url": "https://events.conferenceindex.org/x"},
        {"url": "https://conferencenext.com/e"},
        {"url": "https://iraj.in/conference"},
        {"url": "https://theiier.org/e"},
        {"url": "https://iser.co.in/e"},
        {"url": "https://academicsworld.org/e"},
        {"organiser": "WASET"},
        {"organiser": "World Academy of Science, Engineering and Technology"},
        {"organiser": "IRAJ"},
        {"organiser": "Institute of Research and Journals"},
        {"organiser": "IIER"},
        {"organiser": "IIERD"},
        {"organiser": "International Institute of Engineers and Researchers"},
        {"organiser": "ISER"},
        {"organiser": "International Society for Engineers and Researchers"},
        {"organiser": "ISSER"},
        {"organiser": "Institute for Scientific and Engineering Research"},
        {"organiser": "Academics World"},
        {"organiser": "World Academics"},
        {"source": "International Conference Alerts – blockchain, Norway"},
        {"source": "Conference Alerts"},
        {"source": "All Conference Alert"},
    ]
    for ev in blocked:
        check(event_block.blocked_event(ev), "blocked " + json.dumps(ev, ensure_ascii=False))
    check(event_block.blocked_event(parsed, SRC), "parsed International Conference Alerts event is blocked")
    check(event_block.blocked_source(SRC), "International Conference Alerts source is blocked")
    # A trusted flag does not bypass the check. take() returns before it trusts the source.
    waset = {"title": "Bitcoin conference", "url": "https://waset.org/c", "organiser": "WASET", "place": "Oslo"}
    src = {"name": "WASET", "url": "https://waset.org/", "organiser": "WASET", "trusted": True}
    check(event_block.blocked_event(waset, src), "trusted WASET source is still blocked")
    kept = [
        {"url": "https://www.meetup.com/swedish-bitcoin-meetups/events/316047111/", "organiser": "Swedish Bitcoin Meetups", "source": "Swedish Bitcoin Meetups (Meetup.com)"},
        {"url": "https://www.polyteknisk.no/program/crypto-killer-apps", "organiser": "Polyteknisk Forening", "source": "Polyteknisk Forening (program)"},
        {"url": "https://www.lusem.lu.se/calendar/arne-ryde-conference-crypto-fintech-and-payments", "organiser": "Knut Wicksell Centre for Financial Studies, Lund University School of Economics and Management", "source": "Lund University School of Economics and Management (lusem.lu.se)"},
        {"url": "https://en.itu.dk/About-ITU/Calendar", "organiser": "IT University of Copenhagen", "source": "itu.dk"},
        {"url": "https://www.meetup.com/oslo-blockchain-meetup/", "organiser": "Oslo Blockchain Meetup", "source": "Oslo Blockchain Meetup (Meetup.com)"},
        {"url": "https://notwaset.org/conference", "organiser": "Notwaset"},
        {"url": "https://example.com/notes/waset-warning", "organiser": "Oslo Blockchain Meetup"},
        {"organiser": "Research", "url": "https://example.org/seminar", "source": "Example"},
        {"organiser": "Advisers", "url": "https://example.org/advisers"},
    ]
    for ev in kept:
        check(not event_block.blocked_event(ev), "kept " + (ev.get("organiser") or ev.get("url")))
    check(not event_block.blocked_source({
        "name": "Oslo Blockchain Meetup (Meetup.com)",
        "url": "https://www.meetup.com/oslo-blockchain-meetup/",
        "organiser": "Oslo Blockchain Meetup",
    }), "meetup source kept")
    pipe = inspect.getsource(events.run)
    check("blocked_event" in pipe and "blocked_source" in pipe, "importer consults the blocklist")
    check("blocked_event" in inspect.getsource(events._drop_queue_ids), "queue drop uses the blocklist")
    for rel in ("data/events.json", "archive/events.json"):
        rows = json.load(open(os.path.join(ROOT, rel), encoding="utf-8"))["events"]
        bad = [e.get("url") or e.get("title") for e in rows if event_block.blocked_event(e)]
        check(bad == [], rel + " has no predatory listings" + (": " + ", ".join(bad[:3]) if bad else ""))
    catalogue = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
    bad_src = [s.get("id") for s in catalogue.get("event_sources") or [] if event_block.blocked_source(s)]
    check(bad_src == [], "event_sources has no predatory listings" + (": " + ", ".join(bad_src) if bad_src else ""))


if __name__ == "__main__":
    main()
