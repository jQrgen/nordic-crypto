#!/usr/bin/env python3
"""Event descriptions: sourced text, no predatory pages, headline-style languages. No network."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import event_description as ed

fails = []


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def main():
    fluffy = "Hello 🧡 bitcoin people.\nSponsor: https://kaupr.io\nhttps://example.test/x\nWe meet to talk about bitcoin and payments in Oslo."
    cleaned = ed.clean_description(fluffy)
    check("kaupr" not in cleaned.lower() and "http" not in cleaned and "🧡" not in cleaned, "emoji, url and Kaupr sponsor dropped")
    check(cleaned.startswith("Hello") and "bitcoin and payments" in cleaned, "the sentences stay")
    long = ("Bitcoin is discussed here. " * 40).strip()
    trimmed = ed.clean_description(long)
    check(len(trimmed) <= 600 and trimmed.endswith("."), "trimmed on a sentence under 600")
    check(ed.usable("Bitcoin meetup", "Bitcoin meetup") == "", "title is not a description")
    check(ed.record("Short.", "en", "https://waset.org/e", "WASET", "2026-10-07T23:50:00+00:00") is None, "predatory url refused")
    check(ed.record("A real bitcoin meetup for people in Oslo who want to talk.", "en", "https://internationalconferencealerts.com/x", "ICA", "2026-10-07T23:50:00+00:00") is None, "listing site refused")
    kept = ed.record(
        "This event is a bitcoin meetup in Gothenburg for people who want to talk.",
        "en", "https://www.meetup.com/swedish-bitcoin-meetups/events/1/", "Meetup", "2026-10-07T23:50:00+00:00",
    )
    check(kept and kept["lang"] == "en" and kept["source_url"].startswith("https://www.meetup.com/"), "record keeps text, language and url")
    check(ed.guess_lang("Vi møtes for å snakke om bitcoin og hvordan det blir brukt.") == "nb", "bokmål detected")
    check(ed.guess_lang("This event is a bitcoin meetup and it is for anyone who wants to learn.") == "en", "english detected")

    text = "Vi møtes for å snakke om bitcoin og lynnettet i byen."
    ev = {"id": "abc", "description": {
        "text": text, "lang": "nb", "source_url": "https://www.meetup.com/oslo-blockchain-meetup/events/1/",
        "source_name": "Oslo Blockchain Meetup", "retrieved": "2026-10-07T23:50:00+00:00",
        "i18n": {"en": "We meet to talk about bitcoin and the Lightning Network in the city."},
        "i18n_source": text,
    }}
    shown, lang, orig = ed.show(ev, "en")
    check(lang == "en" and orig == text and shown.startswith("We meet"), "english page shows translation and original")
    shown, lang, orig = ed.show(ev, "nb")
    check(shown == text and orig == "" and lang == "nb", "bokmål page shows the original only")
    shown, lang, orig = ed.show(ev, "de")
    check(lang == "en" and orig == text, "german page uses the english text plus the original")
    bare = {"id": "abc", "description": dict(ev["description"])}
    bare["description"].pop("i18n")
    shown, lang, orig = ed.show(bare, "sv")
    check(shown == text and orig == "", "missing swedish translation shows the original only")
    pub = ed.public(ev)
    check(pub["source_url"].startswith("https://") and pub["lang"] == "nb" and pub["i18n"].get("en"), "public object")
    check("nb" not in pub["i18n"], "public i18n omits the original language")
    stale = dict(ev)
    stale["description"] = dict(ev["description"], i18n_source="old text")
    check(ed.show(stale, "en")[0] == text, "stale translation is not shown")
    if fails:
        print(f"{len(fails)} failed")
        return 1
    print("all ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
