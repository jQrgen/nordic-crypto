#!/usr/bin/env python3
"""Write newsletter/published/<id>/social.zh.json and social.ru.json for a newsletter issue, for the Weibo and VK posters.

This works like the rest of the site's AI-assisted translations (i18n/*.py, summary_i18n): the translation is made
once from the English source and committed next to it. `source_sha` records which English text it came from, and a
human can mark it `"reviewed": true`. The repo had no live translation service, so the model call goes to any
OpenAI-compatible chat-completions endpoint:

  SOCIAL_TRANSLATE_URL    e.g. https://api.x.ai/v1/chat/completions (or any compatible endpoint)
  SOCIAL_TRANSLATE_KEY    API key (never printed)
  SOCIAL_TRANSLATE_MODEL  model name
If any is missing it logs one line and exits 0. The posters then skip the issue rather than post English.

Never overwrites human work. A file is regenerated only if all of these hold:
  * it has no "reviewed": true
  * its `content_sha` still matches its text (any hand edit changes that hash; files without one count as human)
  * its `source_sha` differs from the current English, or --force is given

Rules applied to every result:
  * "Nordic Crypto" is masked before translation and restored after, so the model never translates it
  * the title is "Nordic Crypto 第N期：…" (zh) or "Nordic Crypto №N: …" (ru)
  * text with banned phrases is refused ("made with AI" and translations, "Crypto Nordic", Kaupr as a sponsor)
  * zh: "【title】intro" plus the issue-link line fits Weibo's 140 characters. The intro is cut at a sentence, then at a
    character; if the title alone is too long, the run fails instead of posting a cut headline.

  python3 tools/social_translate.py [--issue 002 | --all] [--lang zh,ru] [--dry-run] [--force]
"""
import argparse, datetime as dt, hashlib, html, json, os, re, sys, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLISHED = os.path.join(ROOT, "newsletter", "published")
SITE = "https://nordiccrypto.no"
BRAND, MASK = "Nordic Crypto", "⟦NC⟧"
LANGS = {"zh": "Simplified Chinese (zh-CN, mainland usage)", "ru": "Russian"}
WEIBO_LIMIT = 140
WEIBO_TAIL = "\n完整内容和新闻视频：{url}"
BANNED = [r"made with ai", r"ai[- ]generated", r"由\s*ai\s*(生成|制作)", r"人工智能(生成|制作)", r"сделано( с помощью)? (ии|ai)",
          r"сгенерирован\w* (ии|ai)", r"crypto nordic", r"kaupr[^.。\n]{0,40}(赞助|спонсор|sponsor)", r"(赞助|спонсор|sponsor)[^.。\n]{0,40}kaupr"]


def log(msg):
    print(f"[social-translate] {msg}", file=sys.stderr, flush=True)


# ------------------------------------------------------------ English source (same parsing as the posters)
STORY_RE = re.compile(r'<p[^>]*>\s*<a href="(?P<url>https?://[^"]+)"[^>]*font-weight:bold[^>]*>(?P<title>.*?)</a>(?P<rest>.*?)</p>', re.S)


def strip_tags(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", s)).split())


def first_sentences(text, n=2):
    return " ".join(re.split(r"(?<=[.!?])\s+", " ".join(text.split()))[:n])


def issues():
    with open(os.path.join(PUBLISHED, "issues.json"), encoding="utf-8") as fh:
        return json.load(fh)["issues"]


def english(meta):
    with open(os.path.join(PUBLISHED, meta["id"], "issue.html"), encoding="utf-8") as fh:
        h = fh.read()
    stories = []
    for m in STORY_RE.finditer(h):
        segs = re.split(r"<br\s*/?>", m.group("rest"))
        stories.append({"title": strip_tags(m.group("title")), "summary": first_sentences(strip_tags(segs[1])) if len(segs) > 1 else ""})
    n = meta.get("number") or int(meta["id"])
    headline = re.sub(rf"^{BRAND} #{n}:\s*", "", meta["title"])
    return {"number": n, "headline": headline, "intro": meta.get("subtitle", ""), "stories": stories}


def sha(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def content_of(doc):
    return {"title": doc.get("title"), "intro": doc.get("intro"), "stories": doc.get("stories")}


# ------------------------------------------------------------ rules
def weibo_len(text):
    return (sum(1 if ord(c) < 128 else 2 for c in text) + 1) // 2


def fit_weibo(title, intro, url):
    tail = WEIBO_TAIL.format(url=url)
    if weibo_len(f"【{title}】" + tail) > WEIBO_LIMIT:
        raise ValueError(f"zh title too long for Weibo ({weibo_len(title)} chars)")
    while intro and weibo_len(f"【{title}】{intro}" + tail) > WEIBO_LIMIT:
        cut = re.split(r"(?<=[。！？])", intro)
        intro = "".join(cut[:-2]) if len([c for c in cut if c]) > 1 else intro[:-2].rstrip("，、；：") + "…"
    return intro


def check_rules(doc):
    text = json.dumps(content_of(doc), ensure_ascii=False)
    if MASK in text:
        raise ValueError("brand mask left in translation")
    for pat in BANNED:
        if re.search(pat, text, re.I):
            raise ValueError(f"banned phrase /{pat}/ in translation")
    if not doc["title"].startswith(BRAND):
        raise ValueError("title must start with 'Nordic Crypto'")


def assemble(lang, src, tr, meta):
    unmask = lambda s: " ".join(str(s).replace(MASK, BRAND).split())
    head = unmask(tr["headline"])
    title = f"{BRAND} 第{src['number']}期：{head}" if lang == "zh" else f"{BRAND} №{src['number']}: {head}"
    stories = [{"title": unmask(s["title"]), "summary": unmask(s["summary"])} for s in tr["stories"]]
    if len(stories) != len(src["stories"]):
        raise ValueError(f"{lang}: got {len(stories)} stories, expected {len(src['stories'])}")
    intro = unmask(tr["intro"])
    if lang == "zh":
        intro = fit_weibo(title, intro, f"{SITE}/newsletter/{meta['id']}/")
    doc = {"title": title, "intro": intro, "stories": stories}
    check_rules(doc)
    return doc


# ------------------------------------------------------------ model
PROMPT = """Translate this newsletter copy from English into {lang}. Return JSON only, with the same keys and the same
number of stories, in the same order: {{"headline": str, "intro": str, "stories": [{{"title": str, "summary": str}}]}}.
Rules: keep the token {mask} exactly as is (it is the brand name). Keep names of people, companies, exchanges,
parties, authorities and media (e.g. Firi, Arctic Core, Finansinspektionen, AMLA, Kaupr) in their usual form. Plain,
neutral news style. Do not add anything: no mention of AI, no sponsorship or endorsement wording, no hashtags or emoji.
{extra}"""
EXTRA = {"zh": "Keep the headline short (at most 40 Chinese characters) and the intro to one short sentence (at most 40 characters).",
         "ru": "Use standard Russian news style."}


def call_model(lang, src):
    url, key, model = (os.environ.get(k) for k in ("SOCIAL_TRANSLATE_URL", "SOCIAL_TRANSLATE_KEY", "SOCIAL_TRANSLATE_MODEL"))
    mask = lambda s: s.replace(BRAND, MASK)
    payload = {"headline": mask(src["headline"]), "intro": mask(src["intro"]),
               "stories": [{"title": mask(s["title"]), "summary": mask(s["summary"])} for s in src["stories"]]}
    body = {"model": model, "temperature": 0.2, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": PROMPT.format(lang=LANGS[lang], mask=MASK, extra=EXTRA[lang])},
                         {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            out = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"translation endpoint -> {e.code}: {e.read()[:300].decode('utf-8', 'replace')}")
    text = out["choices"][0]["message"]["content"]
    return json.loads(re.sub(r"^```(?:json)?|```$", "", text.strip()).strip()), model


# ------------------------------------------------------------ main
def decide(path, src_sha, force):
    """-> (should_write, reason)"""
    if not os.path.exists(path):
        return True, "missing"
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("reviewed") is True:
        return False, "reviewed: true"
    if doc.get("content_sha") != sha(content_of(doc)):
        return False, "edited by hand (no matching content_sha); set it again or delete the file to regenerate"
    if doc.get("source_sha") == src_sha and not force:
        return False, "up to date"
    return True, "English changed" if doc.get("source_sha") != src_sha else "--force"


def run(meta, langs, dry, force, translate=call_model):
    src = english(meta)
    src_sha = sha(src)
    rc = 0
    for lang in langs:
        path = os.path.join(PUBLISHED, meta["id"], f"social.{lang}.json")
        ok, why = decide(path, src_sha, force)
        rel = os.path.relpath(path, ROOT)
        if not ok:
            log(f"{rel}: keep ({why})"); continue
        if dry:
            log(f"{rel}: would generate ({why})"); continue
        try:
            tr, model = translate(lang, src)
            doc = assemble(lang, src, tr, meta)
        except Exception as e:
            log(f"{rel}: FAILED, not written: {e}"); rc = 1; continue
        out = {"_note": f"Generated by tools/social_translate.py from the English issue. Edit freely; set \"reviewed\": true to lock it.",
               "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "model": model,
               "reviewed": False, "source_sha": src_sha, **doc, "content_sha": sha(doc)}
        with open(path + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1); fh.write("\n")
        os.replace(path + ".tmp", path)
        log(f"{rel}: written ({why})")
    return rc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--issue", help="issue id (default: newest)")
    g.add_argument("--all", action="store_true", help="every published issue")
    ap.add_argument("--lang", default="zh,ru")
    ap.add_argument("--dry-run", action="store_true", help="say what would be generated; no API call, no writes")
    ap.add_argument("--force", action="store_true", help="regenerate even if up to date (never touches reviewed or hand-edited files)")
    a = ap.parse_args(argv)
    langs = [l for l in a.lang.split(",") if l]
    bad = [l for l in langs if l not in LANGS]
    if bad:
        raise SystemExit(f"unsupported language(s): {', '.join(bad)}")
    all_issues = issues()
    if a.all:
        chosen = all_issues
    elif a.issue:
        chosen = [i for i in all_issues if i["id"] == a.issue.zfill(3)] or SystemExit(f"issue {a.issue} not found")
    else:
        chosen = [max(all_issues, key=lambda i: (i.get("date", ""), i["id"]))]
    if not a.dry_run:
        missing = [k for k in ("SOCIAL_TRANSLATE_URL", "SOCIAL_TRANSLATE_KEY", "SOCIAL_TRANSLATE_MODEL") if not os.environ.get(k)]
        if missing:
            log(f"skipping: missing {', '.join(missing)}"); return 0
    return max([run(m, langs, a.dry_run, a.force) for m in chosen] or [0])


if __name__ == "__main__":
    sys.exit(main())
