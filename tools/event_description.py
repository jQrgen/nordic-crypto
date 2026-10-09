"""Event descriptions from the organiser's page.

The stored text is the source's own wording, trimmed. description.lang is the
language of that text. description.source_url is the page it was taken from.
data/event_description_i18n.json holds nn, nb, sv, da, fi and is, plus en when
the original is not English. An entry is used only while its source field is
the current text, the same rule as data/title_i18n.json.

show() is what the event page uses, the same way card_headline() works:
  * the description in the page language, when we have one
  * the original underneath, when it is a different text
  * the original only when the page language is the source language, or when
    that translation is missing

Other site languages (German, Spanish, …) use the English text when we have
one, with the original underneath. A predatory listing URL is not a source.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in __import__("sys").path:
    __import__("sys").path.insert(0, ROOT)

import event_block  # noqa: E402
import i18n  # noqa: E402
import site_url  # noqa: E402

PATH = os.path.join(ROOT, "data", "event_description_i18n.json")
NORDIC = ["nn", "nb", "sv", "da", "fi", "is"]
KNOWN = ["en"] + NORDIC
MAX = 600
MIN = 40

_EMOJI = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\uFE0F"
    "\u200D"
    "]+"
)
_MD_LINK = re.compile(r"\[([^\]]+)\]\((?:https?://[^)\s]+)\)")
_URL = re.compile(r"https?://\S+")
_WS = re.compile(r"\s+")
_SPONSOR = re.compile(r"^\s*sponsors?\b", re.I)
_KAUPR = re.compile(r"\bkaupr\b", re.I)
_TAG = re.compile(r"<[^>]+>")


def norm(text):
    return _WS.sub(" ", (text or "").strip()).casefold()


def lang_code(value):
    """BCP 47 tag to a site language we store. Norwegian without a variant is Bokmål."""
    if isinstance(value, list) and value:
        value = value[0]
    if isinstance(value, dict):
        value = value.get("alternateName") or value.get("name") or value.get("@value")
    if not isinstance(value, str) or not value.strip():
        return None
    code = value.strip().lower().replace("_", "-").split("-")[0]
    if code == "no":
        return "nb"
    if code in KNOWN:
        return code
    return None


def _scores(text):
    t = " " + norm(text) + " "
    bags = {
        "en": (" the ", " and ", " with ", " this ", " from ", " that ", " event ", " only ", " for "),
        "nb": (" og ", " ikke ", " som ", " det ", " til ", " skal ", " blir ", " ved ", " av ", " en "),
        "sv": (" och ", " att ", " inte ", " för ", " som ", " det ", " en ", " träff "),
        "da": (" og ", " at ", " ikke ", " med ", " det ", " en ", " for "),
        "fi": (" ja ", " on ", " että ", " ei ", " kanssa ", " tapahtuma "),
        "is": (" og ", " að ", " ekki ", " við ", " sem ", " fyrir ", " þetta ", " verður "),
    }
    return {lang: sum(w in t for w in words) for lang, words in bags.items()}


def guess_lang(text):
    """A language code when the wording is clear. None when it is not."""
    scores = _scores(text)
    top = max(scores.values())
    if top < 3:
        return None
    leaders = [lang for lang, score in scores.items() if score == top]
    # Norwegian and Danish share several words. A tie between them is read as Bokmål.
    if set(leaders) <= {"nb", "da"}:
        return "nb"
    if len(leaders) != 1:
        return None
    best = leaders[0]
    if best == "da" and scores["nb"] >= top - 1:
        return "nb"
    return best


def language_of(text, explicit=None, html_lang=None):
    code = lang_code(explicit)
    if code:
        return code
    guessed = guess_lang(text)
    page = lang_code(html_lang)
    if guessed and page and guessed != page:
        return guessed
    return page or guessed


def clean_description(text):
    """Plain text, a few sentences, no emoji and no sponsor lines. Empty when nothing is left."""
    if not isinstance(text, str) or not text.strip():
        return ""
    if "<" in text and ">" in text:
        text = _TAG.sub(" ", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _EMOJI.sub("", text)
    kept = []
    for line in re.split(r"[\n\r]+", text):
        line = _URL.sub("", line)
        line = _WS.sub(" ", line).strip(" -•*|")
        if not line:
            continue
        if _SPONSOR.search(line):
            continue
        if _KAUPR.search(line):
            continue
        kept.append(line)
    text = site_url.brand(_WS.sub(" ", " ".join(kept)).strip())
    if len(text) > MAX:
        chunk = text[: MAX + 1]
        idx = max(chunk.rfind(". "), chunk.rfind("! "), chunk.rfind("? "))
        if idx >= 180:
            text = chunk[: idx + 1].strip()
        else:
            sp = chunk.rfind(" ")
            text = (chunk[:sp] if sp >= 180 else text[:MAX]).rstrip(" ,;:-").strip()
    return text


def usable(text, title=None):
    text = clean_description(text)
    if len(text) < MIN:
        return ""
    if title and norm(text) == norm(title):
        return ""
    return text


def blocked_source(url, name=None):
    if event_block.host_blocked(event_block.host_of(url or "")):
        return True
    return event_block.blocked_event({"url": url or "", "source": name or "", "source_url": url or ""})


def record(text, lang, source_url, source_name, retrieved, title=None):
    """The object stored on an event, or None when there is nothing we may keep."""
    if blocked_source(source_url, source_name):
        return None
    if not isinstance(source_url, str) or not source_url.startswith(("http://", "https://")):
        return None
    text = usable(text, title)
    if not text:
        return None
    code = lang if lang in KNOWN else lang_code(lang)
    return {
        "text": text,
        "lang": code,
        "source_url": source_url,
        "source_name": source_name or "",
        "retrieved": retrieved,
    }


def prefer(old, new):
    """Keep a longer description from a later read. A shorter one does not replace it."""
    if not isinstance(old, dict) or not new:
        return
    cur = old.get("description") if isinstance(old.get("description"), dict) else None
    if not cur or not (cur.get("text") or "").strip():
        old["description"] = new
        return
    if len(new.get("text") or "") > len(cur.get("text") or ""):
        old["description"] = new


def load(path=None):
    path = path or PATH
    try:
        data = json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        return {}
    items = data.get("items") or {}
    return items if isinstance(items, dict) else {}


def _translations(event, text, catalogue=None):
    """Page-language texts that still belong to this description."""
    if catalogue is None:
        catalogue = load()
    out = {}
    cat = catalogue.get(event.get("id")) or {}
    if isinstance(cat, dict) and (cat.get("source") or "") == text:
        for lang in KNOWN:
            line = (cat.get(lang) or "").strip()
            if line:
                out[lang] = site_url.brand(line)
    rec = event.get("description") if isinstance(event.get("description"), dict) else {}
    item_map = rec.get("i18n") or {}
    item_src = rec.get("i18n_source")
    if item_map and (item_src is None or item_src == text):
        for lang, line in item_map.items():
            if lang in KNOWN and isinstance(line, str) and line.strip():
                out[lang] = site_url.brand(line.strip())
    src = rec.get("lang")
    if src:
        out.pop(src, None)
    return {k: v for k, v in out.items() if v and norm(v) != norm(text)}


def stored(event):
    """(text, lang) from the event, or ('', None) when there is nothing to show."""
    if not isinstance(event, dict):
        return "", None
    rec = event.get("description")
    if not isinstance(rec, dict):
        return "", None
    if blocked_source(rec.get("source_url"), rec.get("source_name")):
        return "", None
    text = (rec.get("text") or "").strip()
    if not text:
        return "", None
    return site_url.brand(text), rec.get("lang")


def show(event, lang, catalogue=None):
    """(text, language code of that text, original or '').

    The original is empty when the page should show a single paragraph.
    """
    text, src = stored(event)
    if not text:
        return "", "", ""

    def source_only():
        return text, src or lang, ""

    if not src or lang == src:
        return source_only()
    trans = _translations(event, text, catalogue)
    if lang == "en":
        en = (trans.get("en") or "").strip()
        if en:
            return en, "en", text
        return source_only()
    if lang in NORDIC:
        line = (trans.get(lang) or "").strip()
        if line:
            return line, lang, text
    en = (trans.get("en") or "").strip()
    if en:
        return en, "en", text
    return source_only()


def public(event, catalogue=None):
    """Description object for the public JSON, or None when the event has none."""
    text, src = stored(event)
    if not text:
        return None
    rec = event.get("description") or {}
    return {
        "text": text,
        "lang": src,
        "source_url": rec.get("source_url"),
        "source_name": rec.get("source_name") or None,
        "retrieved": rec.get("retrieved"),
        "i18n": _translations(event, text, catalogue),
    }


def problems(row):
    """Reasons a backfill description must not be published. Empty means it is fine or absent."""
    if not isinstance(row, dict) or not row.get("description"):
        return []
    rec = row.get("description")
    if not isinstance(rec, dict):
        return ["description is not an object"]
    out = []
    if not (rec.get("text") or "").strip():
        out.append("description text missing")
    url = rec.get("source_url") or ""
    if not str(url).startswith(("http://", "https://")):
        out.append("description has no source URL")
    elif blocked_source(url, rec.get("source_name")):
        out.append("description source is a predatory listing")
    if rec.get("lang") not in KNOWN:
        out.append("description language missing")
    if _KAUPR.search(rec.get("text") or ""):
        out.append("description names Kaupr")
    return out
