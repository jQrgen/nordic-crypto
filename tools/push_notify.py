#!/usr/bin/env python3
"""Tell the push Worker about stories that were not on the previous gh-pages tree.

Read-only. Compares two public news.json files. Does not fetch feeds, does not
import tips, and does not change story status. One HTTP call, one batch.

Exit 0 when there is nothing to send, when the Worker URL or PUSH_PUBLISH_TOKEN
is unset, or when the previous file is missing (that would otherwise notify the
whole archive). Pass --allow-initial only when you mean to send every current story.
Exit 1 when a configured Worker rejects the call.
"""
import argparse, json, os, sys, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = "https://cryptonordic.no/"
LANG_OF = {
    "Norwegian": ("nn", "nb"), "Swedish": ("sv",), "Danish": ("da",),
    "Finnish": ("fi",), "Icelandic": ("is",), "English": ("en",),
}

def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def short(text, n=180):
    text = " ".join((text or "").split())
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0]
    return (cut or text[:n]).rstrip(".,;:") + "…"

def absolute(url):
    url = (url or "").strip()
    if url.startswith("https://") or url.startswith("http://"):
        return url
    return PUBLIC + url.lstrip("/")

def story_key(item):
    return item.get("id") or item.get("url") or ""

def published(items):
    out = {}
    for item in items or []:
        if item.get("status") not in (None, "published"):
            continue
        if not (item.get("summary") or "").strip() and not item.get("own_story"):
            continue
        key = story_key(item)
        if key:
            out[key] = item
    return out

def to_payload(item):
    title_en = (item.get("title_en") or item.get("title") or "").strip()
    titles = {"en": title_en}
    for code in LANG_OF.get(item.get("language") or "", ()):
        if item.get("title"):
            titles[code] = item["title"]
    summaries = {}
    en = short(item.get("summary") or "")
    if en:
        summaries["en"] = en
    for code, text in (item.get("summary_i18n") or {}).items():
        bit = short(text)
        if bit:
            summaries[code] = bit
    country = item.get("country") if item.get("country") in ("NO", "SE", "DK", "FI", "IS") else None
    return {
        "title": title_en,
        "summary": summaries.get("en") or "",
        "url": absolute(item.get("url")),
        "country": country,
        "titles": titles,
        "summaries": summaries,
    }

def new_stories(previous, current):
    old, new = published(previous.get("items")), published(current.get("items"))
    return [to_payload(new[k]) for k in new if k not in old]

def worker_url():
    env = (os.environ.get("PUSH_WORKER_URL") or "").strip().rstrip("/")
    if env:
        return env
    path = os.path.join(ROOT, "workers", "push", "public.json")
    try:
        cfg = json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        return ""
    return (cfg.get("public_endpoint") or "").strip().rstrip("/")

def main(argv=None):
    p = argparse.ArgumentParser(description="Notify the push Worker about newly published stories")
    p.add_argument("--previous", required=True, help="news.json from the gh-pages tree before this publish")
    p.add_argument("--current", required=True, help="news.json from the site/ just built")
    p.add_argument("--dry-run", action="store_true", help="print the JSON body and do not call the Worker")
    p.add_argument("--allow-initial", action="store_true", help="send every current story when the previous file has none")
    args = p.parse_args(argv)
    if not os.path.exists(args.previous):
        print("push notify: previous news.json is missing; not sending (that would notify the whole archive)")
        return 0
    previous, current = load(args.previous), load(args.current)
    if not previous.get("items") and not args.allow_initial:
        print("push notify: previous news.json has no stories; not sending the full archive (pass --allow-initial to override)")
        return 0
    stories = [s for s in new_stories(previous, current) if s["title"] and s["url"].startswith("https://")]
    if not stories:
        print("push notify: no newly published stories")
        return 0
    body = json.dumps({"stories": stories}, ensure_ascii=False).encode("utf-8")
    if args.dry_run:
        sys.stdout.buffer.write(body + b"\n")
        print(f"push notify: dry run, {len(stories)} stories, not sent", file=sys.stderr)
        return 0
    url = worker_url()
    token = (os.environ.get("PUSH_PUBLISH_TOKEN") or "").strip()
    if not url or not token:
        print("push notify: PUSH_WORKER_URL/public_endpoint or PUSH_PUBLISH_TOKEN is unset; skipped")
        return 0
    req = urllib.request.Request(
        url + "/api/push/publish",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            raw = res.read().decode("utf-8", "replace")
            print(f"push notify: HTTP {res.status} {raw[:300]}")
            return 0 if res.status == 200 else 1
    except urllib.error.HTTPError as ex:
        print(f"push notify: HTTP {ex.code} {ex.read()[:300]!r}", file=sys.stderr)
        return 1
    except urllib.error.URLError as ex:
        print(f"push notify: {ex.reason}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
