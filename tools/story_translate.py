#!/usr/bin/env python3
"""Headline, summary and front-page blurb of every published story in every site language.

The site has 23 languages (i18n.ALL_LANGS). English is the base: title_en (or the source title
for an English story), summary and the English blurb. This tool fills what is missing:

  data/title_i18n.json        headline per language, except the language the source headline is in
  data/news.json              summary_i18n on the story
  queue/approved.json         summary_i18n on the editor's item, when the file is here and the
                              English summary is the one the translations were made from
  data/frontpage_blurbs.json  blurb per language, for stories that have an English blurb

Existing text is never replaced. A headline entry is redone only when the source headline changed.
Model: Cloudflare Workers AI (CF_AI_TOKEN and CF_ACCOUNT_ID; CLOUDFLARE_AI_TOKEN and
CLOUDFLARE_ACCOUNT_ID also work). STORY_TRANSLATE_MODEL picks the model. Without credentials the
tool prints one line and exits 0, so a publish never stops on it.

  python3 tools/story_translate.py              # fill every published story
  python3 tools/story_translate.py --dry-run    # list what is missing; no model call, writes nothing
  python3 tools/story_translate.py --id ID      # one story

Rules: "Nordic Crypto" is never translated. Names of people, companies and outlets stay as they are.
Nothing is added to the English text. A reply in the wrong script, without the brand, or that names
Kaupr a sponsor (in the same sentence) is dropped and that language stays missing.
"""
import argparse, concurrent.futures as cf, json, os, re, sys, threading, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import i18n  # noqa: E402
from tools import headlines  # noqa: E402
from tools.frontpage_blurbs import sentences  # noqa: E402

P = lambda *a: os.path.join(ROOT, *a)
LANGS = [l for l in i18n.ALL_LANGS if l != "en"]
NAMES = {
    "nn": "Norwegian Nynorsk", "nb": "Norwegian Bokmål", "sv": "Swedish", "da": "Danish", "fi": "Finnish",
    "is": "Icelandic", "zh": "Simplified Chinese (zh-CN)", "hi": "Hindi", "es": "Spanish", "fr": "French",
    "ar": "Modern Standard Arabic", "bn": "Bengali", "pt": "Portuguese", "ru": "Russian", "ur": "Urdu",
    "id": "Indonesian", "de": "German", "ja": "Japanese", "sw": "Swahili", "mr": "Marathi", "fa": "Persian (Farsi)",
    "uk": "Ukrainian",
}
# A reply must be mostly in the script of its language.
SCRIPT = {
    "zh": r"[\u4e00-\u9fff]", "ja": r"[\u3040-\u30ff\u4e00-\u9fff]", "hi": r"[\u0900-\u097f]", "mr": r"[\u0900-\u097f]",
    "bn": r"[\u0980-\u09ff]", "ar": r"[\u0600-\u06ff]", "fa": r"[\u0600-\u06ff]", "ur": r"[\u0600-\u06ff]",
    "ru": r"[\u0400-\u04ff]", "uk": r"[\u0400-\u04ff]",
}
BRAND = "Nordic Crypto"
MODEL = "@cf/openai/gpt-oss-120b"
CHUNK = 4   # languages per model call
PROMPT = (
    "You translate short news texts for Nordic Crypto, a news site about Bitcoin, blockchain and crypto in the "
    "Nordic countries. Translate the English texts below into each requested language. Plain, neutral news style, "
    "the same facts, nothing added, nothing left out. Keep names of people, companies, outlets, authorities and "
    "products as they are (you may transliterate them where that is the norm for the language). Keep \"Nordic Crypto\" "
    "exactly as written, in Latin letters. Keep numbers, amounts and dates exact. Do not mention AI or translation. "
    "In Norwegian (nn, nb) write \"kunstig intelligens\" in full, never \"AI\" or \"KI\". "
    "Return JSON only, one object: {{\"<code>\": {{<field>: <text>}}}} with exactly these codes and fields:\n{spec}"
)
_lock = threading.Lock()


def load(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


def canon(url):
    import urllib.parse
    p = urllib.parse.urlparse((url or "").strip())
    q = urllib.parse.urlencode([(k, v) for k, v in urllib.parse.parse_qsl(p.query) if not k.lower().startswith(("utm_", "fbclid", "gclid"))])
    return p.netloc.lower().removeprefix("www.") + (p.path.rstrip("/") or "/") + ("?" + q if q else "")


def english(item):
    """English headline the translations are made from."""
    return (item.get("title_en") or "").strip() or (item.get("title") or "").strip()


def plan(item, catalogue, blurbs):
    """{lang: [fields]} still missing for one published story."""
    need = {}
    have_title = headlines.title_map(item, catalogue)
    for lang in headlines.needed_langs(item.get("language")):
        if not (have_title.get(lang) or "").strip():
            need.setdefault(lang, []).append("headline")
    have_sum = item.get("summary_i18n") or {}
    if (item.get("summary") or "").strip():
        for lang in LANGS:
            if not (have_sum.get(lang) or "").strip():
                need.setdefault(lang, []).append("summary")
    b = blurbs.get(item["id"]) or {}
    if (b.get("en") or "").strip():
        for lang in LANGS:
            if not (b.get(lang) or "").strip():
                need.setdefault(lang, []).append("blurb")
    return need


def _endpoint():
    account = os.environ.get("CF_ACCOUNT_ID") or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    token = os.environ.get("CF_AI_TOKEN") or os.environ.get("CLOUDFLARE_AI_TOKEN")
    return account, token


def call_model(system, user):
    account, token = _endpoint()
    model = os.environ.get("STORY_TRANSLATE_MODEL") or MODEL
    body = {"temperature": 0.2, "max_tokens": 8000, "reasoning_effort": "low",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request(f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}",
                                 data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        res = json.load(r)["result"]
    out = res.get("response")
    if out is None and res.get("choices"):
        out = res["choices"][0]["message"].get("content")
    if isinstance(out, dict):
        return out
    out = re.sub(r"^```(?:json)?|```$", "", (out or "").strip()).strip()
    return json.loads(out[out.find("{"):out.rfind("}") + 1])


def tidy(text):
    """Plain hyphens (models like U+2011), single spaces, no wrapping quotes."""
    text = (text or "").replace("\u2011", "-").replace("\u2010", "-")
    text = re.sub(r"[ \t]+", " ", text).strip()
    if len(text) > 1 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return text


SPONSOR = re.compile(r"sponsor|спонсор|اسپانسر|حامی مالی|راعي|प्रायोजक|赞助|スポンサー|patrocin|parrain|mfadhili|পৃষ্ঠপোষক|sponsori|स्पॉन्सर|اسپانسر", re.I)


NO_AI = re.compile(r"(?<![\w-])(?:AI|KI)(?![\w])|(?<![\w-])(?:AI|KI)-\w")   # same rule as tools/text_gate.py


def _sponsor_elsewhere(src):
    """The English text names a sponsor in a sentence that is not about Kaupr (e.g. a BIN sponsor)."""
    return any(SPONSOR.search(x) and "kaupr" not in x.lower() for x in sentences(src))


def valid(lang, field, text, src):
    """Why a reply is refused, or "" when it is fine."""
    text = (text or "").strip()
    if not text:
        return "empty"
    if "```" in text or text.startswith("{"):
        return "markup"
    if BRAND in src and BRAND not in text:
        return "brand missing"
    if re.search(r"crypto\s+nordic", text, re.I):
        return "brand reversed"
    if lang in ("nn", "nb") and NO_AI.search(text):
        return "AI/KI in Norwegian (tools/text_gate.py)"
    for sentence in sentences(text) or [text]:
        if "kaupr" in sentence.lower() and SPONSOR.search(sentence) and not ("kaupr" in src.lower() and _sponsor_elsewhere(src)):
            return "Kaupr named a sponsor"
        if "kaupr" in sentence.lower() and SPONSOR.search(sentence) and len(sentences(text)) < 2:
            return "Kaupr named a sponsor"
    pat = SCRIPT.get(lang)
    if pat:
        letters = [c for c in text if c.isalpha()]
        own = len(re.findall(pat, text))
        # headlines are short and often mostly names in Latin letters (Animoca Brands, Franklin Templeton, NUVA)
        if not letters or own / len(letters) < (0.25 if field == "headline" else 0.5):
            return "wrong script"
    elif headlines.norm(text) == headlines.norm(src) and len(src) > 30:
        return "not translated"
    # abbreviations such as "Mio. NOK" add a split, so a blurb may count up to six
    if field == "blurb" and not 2 <= len(sentences(text)) <= 6:
        return f"{len(sentences(text))} sentences"
    return ""


def translate_story(item, need, blurb_en, translate=call_model, log=print):
    """{lang: {field: text}} for the languages in need. A failed chunk is retried once, then left out."""
    src = {"headline": english(item), "summary": (item.get("summary") or "").strip(), "blurb": blurb_en}
    out = {}
    langs = sorted(need, key=LANGS.index)
    for n in range(0, len(langs), CHUNK):
        chunk = langs[n:n + CHUNK]
        for attempt in (1, 2):
            todo = [l for l in chunk if any(f not in out.get(l, {}) for f in need[l])]
            if not todo:
                break
            spec = "\n".join(f'- "{l}" ({NAMES[l]}): ' + ", ".join(f for f in need[l] if f not in out.get(l, {})) for l in todo)
            fields = sorted({f for l in todo for f in need[l]})
            user = "\n\n".join(f"{f.upper()} (English):\n{src[f]}" for f in fields)
            if "headline" in fields and (item.get("title") or "").strip() != src["headline"]:
                user += f"\n\nFor context only, the original {item.get('language') or ''} headline: {item.get('title')}"
            if "blurb" in fields:
                user += "\n\nThe BLURB must stay two to four sentences."
            try:
                got = translate(PROMPT.format(spec=spec), user)
            except Exception as err:  # one bad call must not stop the run
                log(f"story-translate {item['id']} {','.join(todo)} (try {attempt}): {str(err)[:200]}")
                continue
            for l in todo:
                row = got.get(l) if isinstance(got, dict) else None
                left = [f for f in need[l] if f not in out.get(l, {})]
                if isinstance(row, str) and len(left) == 1:
                    row = {left[0]: row}   # one field asked: some replies give {code: text}
                if not isinstance(row, dict):
                    if attempt == 2:
                        log(f"story-translate {item['id']} {l}: no reply")
                    continue
                for f in need[l]:
                    if f in out.get(l, {}):
                        continue
                    text = tidy(row.get(f)) if isinstance(row.get(f), str) else ""
                    why = valid(l, f, text, src[f])
                    if why:
                        if attempt == 2:
                            log(f"story-translate {item['id']} {l} {f}: dropped ({why})")
                        continue
                    out.setdefault(l, {})[f] = text
    return out


def run(root=ROOT, ids=None, dry=False, translate=None, log=print, workers=6):
    news_path = os.path.join(root, "data", "news.json")
    title_path = os.path.join(root, "data", "title_i18n.json")
    blurb_path = os.path.join(root, "data", "frontpage_blurbs.json")
    ap_path = os.path.join(root, "queue", "approved.json")
    news = load(news_path, {"items": []})
    tdoc = load(title_path, {"_note": "", "langs": [], "items": {}})
    bdoc = load(blurb_path, {"langs": [], "items": {}})
    catalogue = tdoc.setdefault("items", {})
    blurbs = bdoc.setdefault("items", {})
    stories = [i for i in news.get("items", []) if i.get("status") == "published" and i.get("id")
               and not i.get("own_story") and (not ids or i["id"] in ids)]
    todo = [(i, plan(i, catalogue, blurbs)) for i in stories]
    todo = [(i, need) for i, need in todo if need]
    n_texts = sum(len(f) for _, need in todo for f in need.values())
    log(f"story-translate: {len(todo)} of {len(stories)} published stories miss {n_texts} texts")
    if dry or not todo:
        for i, need in todo:
            log(f"  {i['id']}: " + " ".join(f"{l}:{'/'.join(f[0] for f in fs)}" for l, fs in sorted(need.items(), key=lambda x: LANGS.index(x[0]))))
        return {}
    if translate is None:
        if not all(_endpoint()):
            log("story-translate: CF_AI_TOKEN or CF_ACCOUNT_ID not set, skipped")
            return {}
        translate = call_model

    results = {}
    def one(pair):
        item, need = pair
        b_en = ((blurbs.get(item["id"]) or {}).get("en") or "").strip()
        return item["id"], translate_story(item, need, b_en, translate, log)
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for sid, got in ex.map(one, todo):
            results[sid] = got

    by_id = {i["id"]: i for i in news["items"] if i.get("id")}
    added = {"headline": 0, "summary": 0, "blurb": 0}
    for sid, got in results.items():
        item = by_id[sid]
        title = (item.get("title") or "").strip()
        entry = catalogue.get(sid) if isinstance(catalogue.get(sid), dict) else None
        if not entry or (entry.get("source") or "") != title:
            # keep a headline the editor set on the item; the catalogue entry is rebuilt from the current title
            entry = {"source": title}
        for lang, row in got.items():
            if row.get("headline") and not (entry.get(lang) or "").strip():
                entry[lang] = row["headline"]; added["headline"] += 1
            if row.get("summary"):
                sm = item.setdefault("summary_i18n", {})
                if not (sm.get(lang) or "").strip():
                    sm[lang] = row["summary"]; added["summary"] += 1
            if row.get("blurb"):
                slot = blurbs.setdefault(sid, {})
                if not (slot.get(lang) or "").strip():
                    slot[lang] = row["blurb"]; added["blurb"] += 1
        if len(entry) > 1:
            catalogue[sid] = {"source": entry["source"], **{l: entry[l] for l in LANGS if entry.get(l)}}
        if item.get("summary_i18n"):
            item["summary_i18n"] = {l: item["summary_i18n"][l] for l in LANGS if item["summary_i18n"].get(l)}
    tdoc["langs"] = list(LANGS)
    tdoc["_note"] = ("Headlines for story cards, in our own words, from the source headline. source is the stored title these "
                     "translations were made from; a changed title drops them until they are redone. Every site language except "
                     "English, and not the language the source headline is already in. English is title_en on the news item. "
                     "tools/story_translate.py fills missing languages. The card shows the page-language headline first and the "
                     "source headline underneath when they differ. One headline only when the page language is the source "
                     "language. We do not copy article text.")
    bdoc["langs"] = ["en"] + list(LANGS)
    save(title_path, tdoc)
    save(blurb_path, bdoc)
    save(news_path, news)

    # The editor's file is the source apply_approvals.py rebuilds news.json from. Same translations there.
    ap = load(ap_path, None)
    n_ap = 0
    if isinstance(ap, dict):
        for a in ap.get("items", []):
            it = next((i for i in news["items"] if i.get("url") and canon(i["url"]) == canon(a.get("url"))), None)
            if not it or it.get("id") not in results:
                continue
            s = (a.get("summary") or "").strip()
            if not s or s != (it.get("summary") or "").strip() or a.get("summary_i18n_source", s) != s:
                continue
            cur = dict(a.get("summary_i18n") or {})
            for l, text in (it.get("summary_i18n") or {}).items():
                if not (cur.get(l) or "").strip():
                    cur[l] = text; n_ap += 1
            a["summary_i18n"] = {l: cur[l] for l in LANGS if cur.get(l)}
            a["summary_i18n_source"] = s
        save(ap_path, ap)
    log(f"story-translate: added {added['headline']} headlines, {added['summary']} summaries, {added['blurb']} blurbs"
        + (f"; {n_ap} summaries copied to queue/approved.json" if n_ap else ""))
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--id", action="append")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    run(ids=set(a.id) if a.id else None, dry=a.dry_run, workers=a.workers, log=lambda m: print(m, flush=True))
