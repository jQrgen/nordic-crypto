#!/usr/bin/env python3
"""Front-page blurbs: what the story says, in two to four sentences.

The editorial summary on a news item is often a single sentence. That is too little on the
front page, especially when the headline is in another language. data/frontpage_blurbs.json
holds a scannable blurb for each published story: English first, then nn, nb, sv, da, fi and is.
The words are ours, drawn from the headline and the public lead. We do not copy article text
and we do not get around paywalls.

card_text() is what the front page uses:
  1. the summary in the page language, if it is already at least two sentences
  2. else the blurb in the page language
  3. else the English summary, if that is at least two sentences
  4. else the English blurb
  5. else the short summary, as before

A later editorial summary of two or more sentences therefore replaces the stored blurb
without editing the file. Other site languages have no blurb of their own and show the English one.

  python3 tools/frontpage_blurbs.py check
"""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "frontpage_blurbs.json")
LANGS = ["en", "nn", "nb", "sv", "da", "fi", "is"]
# A sentence end is . ! or ? followed by whitespace and a capital letter.
# That keeps decimals (6.1) and Nordic dates (8. juni, 18. september) inside the sentence.
_END = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÝÞÆØÅÄÖÜ])")

def sentences(text):
    return [p for p in _END.split((text or "").strip()) if p.strip()]

def substantive(text):
    return len(sentences(text)) >= 2

def load(path=None):
    path = path or PATH
    try:
        data = json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        return {}
    items = data.get("items") or {}
    return items if isinstance(items, dict) else {}

def card_text(item, lang, blurbs=None):
    """Text for one front-page story card. Returns (text, language code of that text)."""
    if blurbs is None:
        blurbs = load()
    i18n_map = item.get("summary_i18n") or {}
    page = (i18n_map.get(lang) or "").strip() if lang != "en" else (item.get("summary") or "").strip()
    if substantive(page):
        return page, lang
    b = blurbs.get(item.get("id")) or {}
    if lang != "en" and (b.get(lang) or "").strip():
        return b[lang].strip(), lang
    en_sum = (item.get("summary") or "").strip()
    if lang != "en" and substantive(en_sum):
        return en_sum, "en"
    if (b.get("en") or "").strip():
        return b["en"].strip(), "en"
    if page:
        return page, lang
    return en_sum, "en"

def opening_sentences(text, n_max=4):
    """First two to four sentences of our own story, for the front-page card."""
    parts = sentences(text)
    if len(parts) <= n_max:
        return " ".join(parts).strip()
    return " ".join(parts[:n_max]).strip()

def check(path=None):
    """Exit 1 if a published story lacks a 2–4 sentence blurb in every front-page language."""
    news = json.load(open(os.path.join(ROOT, "data", "news.json"), encoding="utf-8"))
    blurbs = load(path)
    published = [i for i in news["items"] if i.get("status") == "published" and (i.get("summary") or "").strip()]
    bad = []
    for it in published:
        b = blurbs.get(it["id"])
        if not b:
            bad.append(f"{it['id']}: no blurb")
            continue
        for lang in LANGS:
            text = (b.get(lang) or "").strip()
            n = len(sentences(text))
            if n < 2 or n > 4:
                bad.append(f"{it['id']} {lang}: {n} sentences")
        # The card in every Nordic language, and in a language with no translation, must be substantive.
        for lang in LANGS + ["de"]:
            text, _ = card_text(it, lang, blurbs)
            if not substantive(text):
                bad.append(f"{it['id']} card {lang}: not substantive")
    if bad:
        print("frontpage blurbs: FAIL", file=sys.stderr)
        for line in bad:
            print("  " + line, file=sys.stderr)
        return 1
    print(f"frontpage blurbs: OK ({len(published)} stories, {', '.join(LANGS)}; other site languages use English)")
    return 0

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        sys.exit(check())
    sys.exit("usage: frontpage_blurbs.py check")
