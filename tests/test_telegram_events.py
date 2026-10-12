#!/usr/bin/env python3
"""tools/telegram_events.py: post each new upcoming event once, never flood, never print the token. No network."""
import datetime as dt, json, os, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import telegram_events as te

NOW = dt.datetime(2026, 10, 9, 8, 0, tzinfo=dt.timezone.utc)

def ev(i, start, end=None, **kw):
    e = {"id": i, "title": f"Meetup {i}", "start": start, "end": end, "place": "Kulturhuset", "city": "Oslo", "country": "NO",
         "organiser": "Bitcoin Oslo", "html_url": f"https://nordiccrypto.no/calendar/{i}/"}
    e.update(kw); return e

class Sender:
    def __init__(self, fail_on=()): self.sent, self.fail_on = [], set(fail_on)
    def __call__(self, token, chat, text):
        if any(f in text for f in self.fail_on): return False, "HTTP 400 Bad Request"
        self.sent.append((token, chat, text)); return True, ""

class TelegramEvents(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(); self.ledger = os.path.join(self.dir, "l", "ledger.json"); self.log = []
    def go(self, events, sender=None, dry=False, max_posts=5, preview=False):
        self.sender = sender or Sender()
        return te.run({"preview": preview, "events": events}, self.ledger, now=NOW, token="T0KEN", chat="@nordiccryptochat",
                      max_posts=max_posts, dry=dry, sender=self.sender, log=self.log.append)
    def ids(self): return json.load(open(self.ledger))["posted"]

    def test_first_run_seeds_and_posts_nothing(self):
        self.assertEqual(self.go([ev("a1", "2026-10-20T18:00:00+02:00"), ev("b2", "2026-11-01T18:00:00+01:00")]), 0)
        self.assertEqual(self.sender.sent, []); self.assertEqual(self.ids(), ["a1", "b2"])

    def test_posts_only_new_upcoming_events_in_start_order(self):
        self.go([ev("a1", "2026-10-20T18:00:00+02:00")])
        events = [ev("a1", "2026-10-20T18:00:00+02:00"), ev("late", "2026-12-01T18:00:00+01:00"),
                  ev("soon", "2026-10-12T18:00:00+02:00", "2026-10-12T21:00:00+02:00"),
                  ev("old", "2026-09-01T18:00:00+02:00", "2026-09-01T21:00:00+02:00"),
                  ev("now", "2026-10-09T09:00:00+02:00", "2026-10-09T17:00:00+02:00")]
        self.assertEqual(self.go(events), 0)
        sent_ids = [s[2].split("/calendar/")[1].split("/")[0] for s in self.sender.sent]
        self.assertEqual(sent_ids, ["now", "soon", "late"])
        self.assertEqual(sorted(self.ids()), ["a1", "late", "now", "soon"])
        self.go(events); self.assertEqual(self.sender.sent, [], "never posted twice")

    def test_max_per_run(self):
        self.go([])
        events = [ev(f"e{i}", f"2026-11-{10 + i}T18:00:00+01:00") for i in range(7)]
        self.go(events, max_posts=5); self.assertEqual(len(self.sender.sent), 5)
        self.go(events, max_posts=5); self.assertEqual(len(self.sender.sent), 2)

    def test_failed_send_is_retried_and_stops_the_run(self):
        self.go([])
        events = [ev("x1", "2026-10-20T18:00:00+02:00"), ev("x2", "2026-10-21T18:00:00+02:00")]
        self.assertEqual(self.go(events, sender=Sender(fail_on=["Meetup x1"])), 1)
        self.assertEqual(self.ids(), []); self.assertFalse(any("T0KEN" in l for l in self.log))
        self.go(events); self.assertEqual(len(self.sender.sent), 2)

    def test_dry_run_changes_nothing(self):
        self.go([], dry=True); self.assertFalse(os.path.exists(self.ledger))
        self.go([])
        self.go([ev("d1", "2026-10-20T18:00:00+02:00")], dry=True)
        self.assertEqual(self.sender.sent, []); self.assertEqual(self.ids(), [])

    def test_preview_feed_refused(self):
        self.assertEqual(self.go([ev("p", "2026-10-20T18:00:00+02:00")], preview=True), 2)
        self.assertFalse(os.path.exists(self.ledger))

    def test_message_is_escaped_html(self):
        m = te.message(ev("h1", "2026-10-14T18:00:00+02:00", "2026-10-14T21:00:00+02:00", title="Bits & <Bytes>"))
        self.assertIn("<b>New event: Bits &amp; &lt;Bytes&gt;</b>", m)
        self.assertIn("Wed 14 Oct 2026, 18:00–21:00", m)
        self.assertIn("🇳🇴 Kulturhuset, Oslo", m)
        self.assertIn('<a href="https://nordiccrypto.no/calendar/h1/">', m)
        online = te.message(ev("o1", "2026-10-14T00:00:00+02:00", place="", city="", online=True, country=None))
        self.assertIn("📍 Online", online); self.assertIn("Wed 14 Oct 2026\n", online)

if __name__ == "__main__":
    unittest.main()
