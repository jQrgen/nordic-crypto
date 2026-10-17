#!/usr/bin/env python3
"""Fill data/event_description_i18n.json for event descriptions that have no current translation.

Cloudflare Workers AI (CLOUDFLARE_API_TOKEN with Workers AI permission, CF_ACCOUNT_ID; model CF_AI_MODEL).
Without them, or when a call fails, nothing is written for that event.
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


MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
ENV = ("CLOUDFLARE_API_TOKEN", "CF_ACCOUNT_ID")


def call_model(text, src, langs):
    account, token = os.environ["CF_ACCOUNT_ID"], os.environ["CLOUDFLARE_API_TOKEN"]
    model = os.environ.get("CF_AI_MODEL") or MODEL
    body = {"temperature": 0.2, "max_tokens": 4096,
            "messages": [{"role": "system", "content": PROMPT.format(src=NAMES[src], codes=", ".join(f"{l} ({NAMES[l]})" for l in langs))},
                         {"role": "user", "content": text}]}
    req = urllib.request.Request(f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}",
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        out = json.load(r)["result"]["response"]
    if isinstance(out, dict):
        return out
    out = re.sub(r"^```(?:json)?|```$", "", out.strip()).strip()
    return json.loads(out[out.find("{"):out.rfind("}") + 1])


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
        if not all(os.environ.get(k) for k in ENV):
            log("event-translate: CLOUDFLARE_API_TOKEN or CF_ACCOUNT_ID not set, skipped")
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
