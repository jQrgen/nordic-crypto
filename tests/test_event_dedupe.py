"""Duplicate calendar listings: same start and venue (or same event URL) with fuzzy-matching titles are merged."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import events as ev

DESC = {"text": "I kjølvannet av bitcoin har vi fått en rekke apper ... i tillegg til bitcoin selv.", "lang": "nb"}
BASE = {"start": "2026-10-14T17:30:00+02:00", "end": "2026-10-14T18:30:00+02:00", "city": "Oslo",
        "place": "Rosenkrantz' gate 7, 0159 Oslo", "url": "https://www.polyteknisk.no/program/crypto-killer-apps"}

def row(i, title, **kw): return {**BASE, "id": i, "title": title, **kw}

def test_prefix_title_same_start_and_venue_is_merged_keeping_fuller_title_and_description():
    a = row("89ced460e4ca", "Crypto killer apps", description=DESC, note="Paid entry.")
    b = row("019f42a4506c", "Crypto killer apps: bitcoin-appene som endrer økonomien", description=None, place_source={"name": "x"})
    rows, moved = ev.dedupe_events([a, b])
    assert len(rows) == 1 and moved == {"89ced460e4ca": "019f42a4506c"}
    k = rows[0]
    assert k["id"] == "019f42a4506c" and k["title"].endswith("økonomien")
    assert k["description"]["text"] == DESC["text"] and k["note"] == "Paid entry." and k["place_source"]

def test_richest_description_wins_either_way():
    long_ = {"text": DESC["text"] + " Mer tekst.", "lang": "nb"}
    rows, _ = ev.dedupe_events([row("a", "Crypto killer apps: x", description=DESC), row("b", "Crypto killer apps", description=long_)])
    assert rows[0]["id"] == "a" and rows[0]["description"]["text"] == long_["text"]

def test_same_url_with_near_title():
    a = row("a", "Bitcoin meetup Oslo", place="Somewhere else")
    b = row("b", "Bitcoin Meetup Oslo!", place="Other venue", start="2026-10-14T19:00:00+02:00")
    assert ev.same_event(a, b)

def test_different_events_stay_apart():
    a = row("a", "Crypto killer apps", url="https://x/1")
    b = row("b", "Lightning workshop", url="https://x/2")
    c = row("c", "Crypto killer apps", url="https://x/3", start="2026-10-15T17:30:00+02:00")
    rows, moved = ev.dedupe_events([a, b, c])
    assert len(rows) == 3 and not moved

def test_stored_data_has_no_duplicates_and_redirect_is_recorded():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data = json.load(open(os.path.join(root, "data", "events.json"), encoding="utf-8"))["events"]
    _, moved = ev.dedupe_events([dict(e) for e in data])
    assert not moved
    rd = json.load(open(os.path.join(root, "data", "event_redirects.json"), encoding="utf-8"))
    assert rd["89ced460e4ca"] == "019f42a4506c"
    kept = next(e for e in data if e["id"] == "019f42a4506c")
    assert "i tillegg til bitcoin selv" in kept["description"]["text"]

def test_similar_titles_rules():
    assert ev.similar_titles("Crypto killer apps", "Crypto killer apps: bitcoin-appene som endrer økonomien")
    assert ev.similar_titles("Crypto killer apps", "Crypto killers apps")
    assert not ev.similar_titles("Blockchain page one", "Blockchain page two")
    assert not ev.similar_titles("Nordic Bitcoin Conference 2026", "Nordic Bitcoin Conference 2027")
