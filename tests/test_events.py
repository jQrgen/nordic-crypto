#!/usr/bin/env python3
"""Conference listing ingest (listing-jsonld). No network."""
import datetime as dt
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
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
    if fails:
        print(f"{len(fails)} failed")
        sys.exit(1)
    print("all ok")


if __name__ == "__main__":
    main()
