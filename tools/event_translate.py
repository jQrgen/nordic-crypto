#!/usr/bin/env python3
"""Fill data/event_description_i18n.json for event descriptions that have no current translation.

Same model endpoint as tools/social_translate.py (SOCIAL_TRANSLATE_URL, _KEY, _MODEL). Without it nothing is written.
An entry is replaced only when its source no longer matches the description; existing languages are kept.

  python3 tools/event_translate.py [--dry-run]
"""
import json, os, re, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import event_description as ed  # noqa: E402

NAMES = {"en": "English", "nn": "Norwegian Nynorsk", "nb": "Norwegian Bokmål", "sv": "Swedish", "da": "Danish", "fi": "Finnish", "is": "Icelandic"}
PROMPT = ("Translate this event description from {src} into each language below. Return JSON only: {{code: text}} for "
          "the codes {codes}. Keep names of people, venues, organisers and Nordic Crypto unchanged. Plain style, nothing added.")


def missing(event, catalogue):
    text, src = ed.stored(event)
    if not text or src not in ed.KNOWN:
        return text, src, []
    cur = catalogue.get(event.get("id")) or {}
    have = cur if cur.get("source") == text else {}
    return text, src, [l for l in ed.KNOWN if l != src and not (have.get(l) or "").strip()]


def call_model(text, src, langs):
    url, key, model = (os.environ.get(k) for k in ("SOCIAL_TRANSLATE_URL", "SOCIAL_TRANSLATE_KEY", "SOCIAL_TRANSLATE_MODEL"))
    body = {"model": model, "temperature": 0.2, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": PROMPT.format(src=NAMES[src], codes=", ".join(f"{l} ({NAMES[l]})" for l in langs))},
                         {"role": "user", "content": text}]}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        out = json.load(r)["choices"][0]["message"]["content"]
    return json.loads(re.sub(r"^```(?:json)?|```$", "", out.strip()).strip())


def fill(events, catalogue, translate=call_model, log=print):
    """Adds translations to catalogue in place. Returns the ids that changed."""
    changed = []
    for e in events:
        text, src, langs = missing(e, catalogue)
        if not langs:
            continue
        try:
            got = translate(text, src, langs)
        except Exception as err:  # one bad event must not stop the fetch
            log(f"event-translate {e.get('id')}: {err}")
            continue
        cur = catalogue.get(e["id"]) or {}
        entry = dict(cur) if cur.get("source") == text else {"source": text}
        for l in langs:
            v = ed.clean_description(got.get(l) or "") if isinstance(got, dict) else ""
            if v and ed.norm(v) != ed.norm(text):
                entry[l] = v
        if len(entry) > 1:
            catalogue[e["id"]] = entry
            changed.append(e["id"])
    return changed


def run(root=ROOT, log=print, translate=None, dry=False):
    if translate is None:
        if not all(os.environ.get(k) for k in ("SOCIAL_TRANSLATE_URL", "SOCIAL_TRANSLATE_KEY", "SOCIAL_TRANSLATE_MODEL")):
            log("event-translate: SOCIAL_TRANSLATE_* not set, skipped")
            return []
        translate = call_model
    path = os.path.join(root, "data", "event_description_i18n.json")
    doc = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"items": {}}
    events = json.load(open(os.path.join(root, "data", "events.json"), encoding="utf-8")).get("events", [])
    changed = fill(events, doc.setdefault("items", {}), translate, log)
    if changed and not dry:
        tmp = path + ".tmp"
        json.dump(doc, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    log(f"event-translate: {len(changed)} descriptions translated")
    return changed


if __name__ == "__main__":
    run(dry="--dry-run" in sys.argv)
