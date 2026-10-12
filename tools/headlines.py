#!/usr/bin/env python3
"""Headlines on story cards.

The stored title is the source headline. title_en is our English headline.
data/title_i18n.json holds nn, nb, sv, da, fi and is for every published story
whose source language is not already that site language. An editor can also set
title_i18n on the news item (queue/approved.json); that copy wins.

card_headline() is what the front page, the story page and the newsletter use:
  * the headline in the page language, when we have one
  * the source headline underneath, when it is a different text
  * one headline only when the page language is the source language, or when the
    translation repeats the source headline

Norwegian headlines in this data are Bokmål, so a Nynorsk page translates them.
Other site languages (German, Spanish, …) use the English headline, with the
source headline underneath when it differs. Our own stories keep the title of
the article.

  python3 tools/headlines.py check
"""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import i18n
PATH = os.path.join(ROOT, "data", "title_i18n.json")
NORDIC = ["nn", "nb", "sv", "da", "fi", "is"]
# Site language that already reads the stored title. Norwegian press titles are Bokmål.
SOURCE_SITE = {
    "Norwegian": "nb",
    "Swedish": "sv",
    "Danish": "da",
    "Finnish": "fi",
    "Icelandic": "is",
    "English": "en",
}
_WS = re.compile(r"\s+")

def norm(text):
    return _WS.sub(" ", (text or "").strip()).casefold()

_LOADED = {}   # path -> ((mtime_ns, size), items); a build asks once per card, so parse the file once

def load(path=None):
    """Catalogue items. The dict is shared between callers: read it, do not change it."""
    path = path or PATH
    try:
        st = os.stat(path)
        stamp = (st.st_mtime_ns, st.st_size)
        hit = _LOADED.get(path)
        if hit and hit[0] == stamp:
            return hit[1]
        data = json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        return {}
    items = data.get("items") or {}
    items = items if isinstance(items, dict) else {}
    _LOADED[path] = (stamp, items)
    return items

def needed_langs(language):
    """Nordic site languages that still need a headline for this source language."""
    src = SOURCE_SITE.get(language or "")
    return [lang for lang in NORDIC if lang != src]

def title_map(item, catalogue=None):
    """Page-language headlines that still belong to this source title.

    The catalogue entry is used only while its source field is the current title.
    title_i18n on the item overrides it. title_i18n_source, when set, must match
    the title or the item map is ignored.
    """
    if catalogue is None:
        catalogue = load()
    title = (item.get("title") or "").strip()
    out = {}
    cat = catalogue.get(item.get("id")) or {}
    if isinstance(cat, dict) and (cat.get("source") or "") == title:
        for lang in NORDIC:
            text = (cat.get(lang) or "").strip()
            if text:
                out[lang] = text
    item_map = item.get("title_i18n") or {}
    item_src = item.get("title_i18n_source")
    if item_map and (item_src is None or item_src == title):
        for lang, text in item_map.items():
            if lang in NORDIC and (text or "").strip():
                out[lang] = text.strip()
    return out

def _source_code(item):
    """BCP 47-ish code for the stored title, matching i18n.SRC_LANG."""
    return i18n.SRC_LANG.get(item.get("language") or "", "en")

def card_headline(item, lang, catalogue=None):
    """Headline for one card.

    Returns (headline, language code of that headline, original title or "").
    The original is empty when the card should show a single headline.
    """
    title = (item.get("title") or "").strip()
    if item.get("own_story"):
        return title, "en", ""
    src = SOURCE_SITE.get(item.get("language") or "")
    src_code = _source_code(item)
    translated = title_map(item, catalogue)

    def source_only():
        code = src_code if src_code != lang else lang
        return title, code, ""

    if lang == "en":
        en = (item.get("title_en") or "").strip()
        if en and norm(en) != norm(title):
            return en, "en", title
        return source_only()

    # The page already reads the source headline. One line, even if a translation
    # was stored for that same language.
    if lang == src:
        return source_only()

    if lang in NORDIC:
        text = (translated.get(lang) or "").strip()
        if text:
            if norm(text) == norm(title):
                return source_only()
            return text, lang, title

    en = (item.get("title_en") or "").strip()
    if en and norm(en) != norm(title):
        return en, "en", title
    return source_only()

def public_title_i18n(item, catalogue=None):
    """title_i18n for the public JSON: only headlines that differ from the source title."""
    title = (item.get("title") or "").strip()
    out = {}
    for lang, text in title_map(item, catalogue).items():
        if text and norm(text) != norm(title):
            out[lang] = text
    return out

def check(path=None):
    """Exit 1 if a published story is missing a headline in a Nordic language it needs."""
    news = json.load(open(os.path.join(ROOT, "data", "news.json"), encoding="utf-8"))
    catalogue = load(path)
    published = [i for i in news["items"] if i.get("status") == "published" and (i.get("summary") or "").strip()]
    bad = []
    for it in published:
        lang_name = it.get("language") or ""
        src = SOURCE_SITE.get(lang_name)
        if not src:
            bad.append(f"{it['id']}: unknown source language {lang_name!r}")
            continue
        if src != "en" and not (it.get("title_en") or "").strip():
            bad.append(f"{it['id']}: no English headline")
        got = title_map(it, catalogue)
        for lang in needed_langs(lang_name):
            if not (got.get(lang) or "").strip():
                bad.append(f"{it['id']} {lang}: no headline")
        # The card in every site language must come back with a headline.
        for lang in NORDIC + ["en", "de"]:
            head, code, orig = card_headline(it, lang, catalogue)
            if not (head or "").strip():
                bad.append(f"{it['id']} card {lang}: empty")
                continue
            if lang == src or (lang == "en" and src == "en"):
                if orig:
                    bad.append(f"{it['id']} card {lang}: original shown on a same-language page")
                if norm(head) != norm(it["title"]) and not (lang == "en" and it.get("title_en")):
                    bad.append(f"{it['id']} card {lang}: replaced the source headline")
            elif lang in NORDIC and (got.get(lang) or "").strip() and norm(got[lang]) != norm(it["title"]):
                if norm(head) != norm(got[lang]) or not orig:
                    bad.append(f"{it['id']} card {lang}: expected translated headline plus original")
                if code != lang:
                    bad.append(f"{it['id']} card {lang}: headline language is {code}")
            elif lang not in NORDIC and src != "en" and (it.get("title_en") or "").strip():
                if code != "en" or not orig:
                    bad.append(f"{it['id']} card {lang}: expected English headline plus original")
    if bad:
        print("headlines: FAIL", file=sys.stderr)
        for line in bad:
            print("  " + line, file=sys.stderr)
        return 1
    print(f"headlines: OK ({len(published)} stories; source language keeps one headline)")
    return 0

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        sys.exit(check())
    sys.exit("usage: headlines.py check")
