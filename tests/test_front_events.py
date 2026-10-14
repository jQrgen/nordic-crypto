#!/usr/bin/env python3
"""The front page lists the next six events that have not started, on a phone too.

Static HTML is what a build at 12:00 Oslo on 14 Oct 2026 would have published
(the 17:30 Oslo talk still in the list). A row that started at 12:00 with no
end is already past by 18:50, because a missing end lasts three hours. The
browser clock is NC_NOW. Headless Chrome at a phone width must show the next
six, for Bokmål and the other site languages. An event that has started and
not ended is ongoing, with the local "happening now" label, and is not in
the upcoming list or the past list.
"""
import datetime as dt
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import build
import i18n
from tools import event_select

NOW = "2026-10-14T18:50:00+02:00"
BUILT_AT = "2026-10-14T12:00:00+02:00"
DURING = "2026-10-14T18:00:00+02:00"
NEXT6 = [
    "c4a53ca9bd26",  # Uppsala 15 Oct
    "16b9aa68f972",  # Göteborg 18 Oct
    "a1ea7afabcb0",  # Oslo 28 Oct, stored as +01:00
    "a6cadcf35c22",  # Stockholm 5 Nov, +01:00
    "ce0c87469bd8",  # Helsinki 6 Nov, +02:00
    "7adc8e1ede97",  # Oslo 25 Nov, +01:00
]
ENDED = "019f42a4506c"  # Oslo 14 Oct 17:30–18:30
PROBE = """<script>
(function(){
  function rows(sel){
    return [].slice.call(document.querySelectorAll(sel)).map(function(el){
      var st=getComputedStyle(el);
      return {id:el.getAttribute('data-id'), hidden:!!el.hidden, display:st.display,
              start:el.getAttribute('data-start'), end:el.getAttribute('data-end')||''};
    });
  }
  var n=document.createElement('pre'); n.id='probe';
  n.textContent=JSON.stringify({
    soon:rows('#evsoon-list .evcard'),
    hero:rows('#evhero-list .evcard'),
    heroHidden:document.getElementById('evhero').hidden,
    heading:document.getElementById('evsoon-h').textContent,
    badge:(document.querySelector('#evhero .evphase')||{textContent:''}).textContent
  });
  document.body.appendChild(n);
})();
</script>"""


def archive_events():
    with open(os.path.join(ROOT, "archive", "events.json"), encoding="utf-8") as fh:
        return json.load(fh)["events"]


def with_open_end(events):
    """Started at noon with no end. The assumed end is 15:00, so 18:50 is past."""
    row = {
        "id": "noend", "title": "Started with no end", "start": "2026-10-14T12:00:00+02:00",
        "place": "Venue", "city": "Oslo", "country": "NO", "organiser": "Test",
        "url": "https://example.test/noend",
    }
    return [row] + list(events)


def with_assumed_ongoing(events):
    """Started at 17:00 with no end. At 18:50 the assumed end (20:00) has not passed."""
    row = {
        "id": "open3", "title": "No published end", "start": "2026-10-14T17:00:00+02:00",
        "place": "Venue", "city": "Oslo", "country": "NO", "organiser": "Test",
        "url": "https://example.test/open3",
    }
    return [row] + list(events)


def page(lang, events, built_at, clock):
    build.LANG = lang
    block = build.front_events_block(events, built_at, compact=True)
    os.environ["NC_NOW"] = clock
    script = build.front_events_script()
    direction = "rtl" if i18n.rtl(lang) else "ltr"
    return f"""<!DOCTYPE html>
<html lang="{i18n.HTML_LANG[lang]}" dir="{direction}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>{build.CSS}</style></head>
<body><div class="wrap"><div class="home"><aside class="home-events">{block}</aside></div></div>
{script}
{PROBE}</body></html>""", block


def chrome():
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    return None


def render(html, width, height):
    browser = chrome()
    if not browser:
        raise unittest.SkipTest("headless Chrome is not installed")
    tmp = tempfile.mkdtemp(prefix="nc-front-")
    proc = None
    stdout = None
    try:
        src = os.path.join(tmp, "index.html")
        out = os.path.join(tmp, "dom.html")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(html)
        stdout = open(out, "w", encoding="utf-8")
        proc = subprocess.Popen(
            [browser, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
             "--disable-background-networking", "--disable-sync", "--no-first-run",
             f"--user-data-dir={os.path.join(tmp, 'profile')}", f"--window-size={width},{height}",
             "--dump-dom", src],
            stdout=stdout, stderr=subprocess.DEVNULL, start_new_session=True)
        deadline = time.time() + 20
        text = ""
        while time.time() < deadline:
            stdout.flush()
            try:
                with open(out, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                text = ""
            if 'id="probe"' in text and text.rstrip().endswith("</html>"):
                break
            time.sleep(0.05)
        else:
            raise AssertionError("headless Chrome did not render the probe")
        return text
    finally:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        if stdout is not None:
            stdout.close()
        shutil.rmtree(tmp, ignore_errors=True)


def probe_of(dom):
    import html as html_lib
    import re
    match = re.search(r'<pre id="probe">(.*?)</pre>', dom, re.S)
    if not match:
        raise AssertionError("probe missing from rendered DOM")
    return json.loads(html_lib.unescape(match.group(1)))


def visible_ids(dom):
    data = probe_of(dom)
    shown = [row["id"] for row in data["soon"] if not row["hidden"] and row["display"] != "none"]
    return shown, data


class FrontEvents(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("NC_NOW", None)
        build.LANG = "en"

    def test_phone_css_does_not_clip_the_list(self):
        with open(os.path.join(ROOT, "assets", "css", "home.css"), encoding="utf-8") as fh:
            home = fh.read()
        self.assertNotIn("nth-child(n+4)", home)
        self.assertNotIn("#evsoon-list .evcard:nth-child", build.CSS)
        self.assertIn("The next six events stay visible", home)

    def test_offset_instants_match_the_build_clock(self):
        # 17:00+01:00 is 16:00 UTC. A parser that ignores the offset, or applies DST twice, disagrees.
        samples = [
            ("2026-10-14T18:50:00+02:00", "2026-10-14T16:50:00+00:00"),
            ("2026-10-28T17:00:00+01:00", "2026-10-28T16:00:00+00:00"),
            ("2026-11-05T17:30:00+01:00", "2026-11-05T16:30:00+00:00"),
            ("2026-11-06T18:00:00+02:00", "2026-11-06T16:00:00+00:00"),
        ]
        for raw, utc in samples:
            got = dt.datetime.fromisoformat(raw).astimezone(dt.timezone.utc)
            want = dt.datetime.fromisoformat(utc).astimezone(dt.timezone.utc)
            self.assertEqual(got, want, raw)

    def test_partition_at_1850_is_the_next_six(self):
        part = event_select.partition(with_open_end(archive_events()), NOW)
        self.assertEqual([e["id"] for e in part["upcoming"]], NEXT6)
        self.assertEqual(part["ongoing"], [])
        self.assertIn("noend", [e["id"] for e in part["previous"]])
        self.assertIn(ENDED, [e["id"] for e in part["previous"]])

    def test_every_language_renders_the_same_cards(self):
        events = with_open_end(archive_events())
        counts = {}
        for lang in i18n.ALL_LANGS:
            build.LANG = lang
            block = build.front_events_block(events, BUILT_AT, compact=True)
            counts[lang] = (block.count('class="evcard'), block.count(" hidden"))
            self.assertIn('id="evsoon-list"', block)
            self.assertIn('data-start="2026-10-28T17:00:00+01:00"', block)
            self.assertIn('data-start="2026-11-06T18:00:00+02:00"', block)
            self.assertIn('data-id="noend"', block)
            card = block[block.find('id="e-noend"'):block.find('data-id="noend"')]
            self.assertIn('data-end="2026-10-14T15:00:00+02:00"', card)
            self.assertIn('data-phase="ongoing"', card)
            self.assertNotIn('data-end=""', card)
        self.assertEqual(len(set(counts.values())), 1, counts)

    def test_phone_shows_six_after_a_started_event_ends(self):
        if not chrome():
            self.skipTest("headless Chrome is not installed")
        events = with_open_end(archive_events())
        for lang in ("nb", "en", "nn", "sv", "da", "fi", "is", "de", "ar"):
            html, _block = page(lang, events, BUILT_AT, NOW)
            shown, data = visible_ids(render(html, 390, 844))
            self.assertEqual(data["heading"], i18n.t(lang, "front_ev_h"), lang)
            self.assertTrue(data["heroHidden"], lang)
            self.assertEqual(data["hero"], [], lang)
            self.assertEqual(shown, NEXT6, lang)
            ids = [row["id"] for row in data["soon"]]
            self.assertNotIn(ENDED, ids, lang)
            self.assertNotIn("noend", ids, lang)
            # The seventh upcoming card stays in the list, hidden, so the next start can promote it.
            self.assertEqual(ids[len(NEXT6)], "e884ba1f0333", lang)
            self.assertTrue(data["soon"][len(NEXT6)]["hidden"], lang)

    def test_desktop_shows_the_same_six(self):
        if not chrome():
            self.skipTest("headless Chrome is not installed")
        html, _block = page("nb", with_open_end(archive_events()), BUILT_AT, NOW)
        shown, _data = visible_ids(render(html, 1280, 900))
        self.assertEqual(shown, NEXT6)

    def test_ongoing_event_is_the_hero_and_the_list_stays_six(self):
        if not chrome():
            self.skipTest("headless Chrome is not installed")
        saved = os.environ.get("NC_NOW")
        os.environ["NC_NOW"] = DURING
        try:
            build.LANG = "nb"
            events = archive_events()
            block = build.front_events_block(events, BUILT_AT, compact=True)
            script = build.front_events_script()
        finally:
            if saved is None:
                os.environ.pop("NC_NOW", None)
            else:
                os.environ["NC_NOW"] = saved
        html = f"""<!DOCTYPE html><html lang="nb"><head><meta charset="utf-8">
<style>{build.CSS}</style></head><body><div class="wrap"><div class="home"><aside class="home-events">{block}</aside></div></div>
{script}{PROBE}</body></html>"""
        shown, data = visible_ids(render(html, 390, 900))
        self.assertFalse(data["heroHidden"])
        self.assertEqual([row["id"] for row in data["hero"]], [ENDED])
        self.assertEqual(data["badge"], i18n.t("nb", "ongoing_h"))
        self.assertEqual(shown, NEXT6)
        self.assertNotIn(ENDED, shown)


    def test_missing_end_stays_ongoing_for_three_hours(self):
        events = with_assumed_ongoing(archive_events())
        part = event_select.partition(events, NOW)
        self.assertEqual([e["id"] for e in part["ongoing"]], ["open3"])
        self.assertEqual([e["id"] for e in part["upcoming"]], NEXT6)
        self.assertNotIn("open3", [e["id"] for e in part["previous"]])
        self.assertNotIn(ENDED, [e["id"] for e in part["upcoming"]])
        self.assertIn(ENDED, [e["id"] for e in part["previous"]])
        if not chrome():
            self.skipTest("headless Chrome is not installed")
        html, _block = page("nb", events, BUILT_AT, NOW)
        shown, data = visible_ids(render(html, 390, 900))
        self.assertEqual([row["id"] for row in data["hero"]], ["open3"])
        self.assertEqual(data["badge"], "Pågår nå")
        self.assertEqual(shown, NEXT6)
        self.assertNotIn("open3", shown)
        self.assertNotIn(ENDED, shown)

    def test_clock_flips_upcoming_to_ongoing_then_past(self):
        if not chrome():
            self.skipTest("headless Chrome is not installed")
        os.environ.pop("NC_NOW", None)
        build.LANG = "nb"
        block = build.front_events_block(archive_events(), BUILT_AT, compact=True)
        script = build.front_events_script()
        self.assertIn("FIXED=null", script)
        self.assertIn("window.ncPhaseApply", script)
        self.assertIn("setInterval(apply,30000)", script)
        html = f"""<!DOCTYPE html><html lang="nb"><head><meta charset="utf-8">
<style>{build.CSS}</style></head><body><div class="wrap"><div class="home"><aside class="home-events">{block}</aside></div></div>
<script>window.NC_CLOCK={json.dumps(DURING)};</script>
{script}
<script>
function rows(sel){{return [].slice.call(document.querySelectorAll(sel)).filter(function(el){{return !el.hidden&&getComputedStyle(el).display!=='none'}}).map(function(el){{return el.getAttribute('data-id')}})}}
var during={{hero:rows('#evhero-list .evcard'), soon:rows('#evsoon-list .evcard'),
  badge:(document.querySelector('#evhero .evphase')||{{textContent:''}}).textContent,
  hidden:document.getElementById('evhero').hidden}};
window.NC_CLOCK={json.dumps(NOW)};
window.ncPhaseApply();
var after={{hero:rows('#evhero-list .evcard'), soon:rows('#evsoon-list .evcard'),
  hidden:document.getElementById('evhero').hidden,
  gone:!!document.getElementById('e-{ENDED}')}};
var n=document.createElement('pre'); n.id='probe';
n.textContent=JSON.stringify({{during:during, after:after}});
document.body.appendChild(n);
</script></body></html>"""
        data = probe_of(render(html, 390, 900))
        self.assertEqual(data["during"]["hero"], [ENDED])
        self.assertEqual(data["during"]["badge"], "Pågår nå")
        self.assertNotIn(ENDED, data["during"]["soon"])
        self.assertEqual(data["during"]["soon"][:6], NEXT6)
        self.assertEqual(data["after"]["hero"], [])
        self.assertTrue(data["after"]["hidden"])
        self.assertFalse(data["after"]["gone"])
        self.assertNotIn(ENDED, data["after"]["soon"])
        self.assertEqual(data["after"]["soon"][:6], NEXT6)

    def test_calendar_and_event_page_show_ongoing(self):
        now = event_select.clock(DURING)
        rows = []
        for raw in archive_events():
            row = dict(raw)
            row.update(event_select.annotate(row, now))
            rows.append(row)
        killer = next(row for row in rows if row["id"] == ENDED)
        open_end = {
            "id": "open3phase01", "title": "No published end", "start": "2026-10-14T17:00:00+02:00",
            "place": "Venue", "city": "Oslo", "country": "NO", "organiser": "Test",
            "url": "https://example.test/open3", "source": "Test", "source_url": "https://example.test/open3",
            "status": "published",
        }
        open_end.update(event_select.annotate(open_end, now))
        saved_site, saved_preview = build.SITE, build.PREVIEW
        try:
            with tempfile.TemporaryDirectory() as site:
                build.SITE = site
                build.PREVIEW = False
                build.LANG = "nb"
                build.build_calendar({"events": (rows, now)})
                cal = open(os.path.join(site, "nb", "calendar", "index.html"), encoding="utf-8").read()
                build.build_one_event(killer)
                page_html = open(os.path.join(site, "nb", "calendar", ENDED, "index.html"), encoding="utf-8").read()
                build.build_one_event(open_end)
                open_html = open(os.path.join(site, "nb", "calendar", open_end["id"], "index.html"), encoding="utf-8").read()
        finally:
            build.SITE = saved_site
            build.PREVIEW = saved_preview
        self.assertIn('id="evnow"', cal)
        self.assertNotIn('id="evnow" hidden', cal)
        ongoing = cal.split('id="evongoing"', 1)[1].split("</ol>", 1)[0]
        evlist = cal.split('id="evlist"', 1)[1].split("</ol>", 1)[0]
        past = cal.split('class="news past"', 1)[1].split("</ol>", 1)[0]
        self.assertIn(ENDED, ongoing)
        self.assertIn("Pågår nå", ongoing)
        self.assertIn('data-phase="ongoing"', ongoing)
        self.assertNotIn(ENDED, evlist)
        self.assertNotIn(ENDED, past)
        self.assertIn('id="evphase"', page_html)
        self.assertIn('data-phase="ongoing"', page_html)
        self.assertIn("Pågår nå", page_html)
        self.assertIn('data-end="2026-10-14T18:30:00+02:00"', page_html)
        self.assertIn('data-phase="ongoing"', open_html)
        self.assertIn('data-end="2026-10-14T20:00:00+02:00"', open_html)
        when = open_html.split("<time", 1)[1].split("</time>", 1)[0]
        self.assertNotIn("20:00", when)
        self.assertNotIn("20.00", when)
        self.assertIn("window.ncPhaseApply", cal)
        self.assertIn("window.ncPhaseApply", page_html)

    def test_calendar_flips_live(self):
        if not chrome():
            self.skipTest("headless Chrome is not installed")
        os.environ.pop("NC_NOW", None)
        build.LANG = "nb"
        script = build.calendar_phase_script()
        html = f"""<!DOCTYPE html><html lang="nb"><body>
<section id="evnow" hidden><h2 id="evnow-h">Pågår nå</h2><ol id="evongoing"></ol></section>
<ol id="evlist">
<li id="e-{ENDED}" data-c="NO" data-start="2026-10-14T17:30:00+02:00" data-end="2026-10-14T18:30:00+02:00" data-phase="upcoming"><h3>Crypto killer apps</h3></li>
<li id="e-next" data-c="SE" data-start="2026-10-15T17:30:00+02:00" data-end="2026-10-15T19:00:00+02:00" data-phase="upcoming"><h3>Next</h3></li>
</ol>
<ol class="news past"></ol>
<script>window.NC_CLOCK={json.dumps(DURING)};</script>
{script}
<script>
function ids(sel){{return [].slice.call(document.querySelectorAll(sel)).map(function(el){{return el.id}})}}
var during={{now:ids('#evongoing li'), up:ids('#evlist li'), past:ids('ol.past li'),
  label:(document.querySelector('#evongoing .evphase')||{{textContent:''}}).textContent,
  hidden:document.getElementById('evnow').hidden}};
window.NC_CLOCK={json.dumps(NOW)};
window.ncPhaseApply();
var after={{now:ids('#evongoing li'), up:ids('#evlist li'), past:ids('ol.past li'),
  hidden:document.getElementById('evnow').hidden}};
var n=document.createElement('pre'); n.id='probe';
n.textContent=JSON.stringify({{during:during, after:after}});
document.body.appendChild(n);
</script></body></html>"""
        data = probe_of(render(html, 800, 700))
        self.assertEqual(data["during"]["now"], [f"e-{ENDED}"])
        self.assertEqual(data["during"]["label"], "Pågår nå")
        self.assertFalse(data["during"]["hidden"])
        self.assertNotIn(f"e-{ENDED}", data["during"]["up"])
        self.assertNotIn(f"e-{ENDED}", data["during"]["past"])
        self.assertIn("e-next", data["during"]["up"])
        self.assertEqual(data["after"]["now"], [])
        self.assertTrue(data["after"]["hidden"])
        self.assertEqual(data["after"]["past"], [f"e-{ENDED}"])
        self.assertEqual(data["after"]["up"], ["e-next"])


if __name__ == "__main__":
    unittest.main()
