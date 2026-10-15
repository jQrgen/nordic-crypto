#!/usr/bin/env python3
"""Post each new Nordic Crypto newsletter issue to the Nordic Crypto Facebook Page as one video post, once.

Uploads the newsreel with Graph API POST /{page-id}/videos. By default it passes file_url (the issue's video.url), so
Facebook fetches the file. With --upload, or when there is no video.url, the local/downloaded MP4 is sent as a
multipart `source`. The title is the headline. The description holds the intro, every story (headline, short summary,
link) and the issue link. Facebook has no 280-char limit, so it is a single post.

Before a real post the issue page must answer 200.
State: data/fb_posted.json maps issue id -> {"video_id", "posted_at"}; a posted issue is never posted again.
Secrets (env, never printed): FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN (long-lived Page token). If either is missing, the
script logs one line and exits 0.

  python3 tools/fb_newsletter.py [--issue 002] [--dry-run] [--upload] [--state data/fb_posted.json]
"""
import argparse, datetime as dt, hashlib, html, json, os, re, secrets, sys, tempfile, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLISHED = os.path.join(ROOT, "newsletter", "published")
SITE = "https://nordiccrypto.no"
UA = "nordic-crypto-fb-newsletter/1 (+https://nordiccrypto.no/)"

STATE = os.path.join(ROOT, "data", "fb_posted.json")
GRAPH = "https://graph-video.facebook.com/v21.0"
ENV = ("FB_PAGE_ID", "FB_PAGE_ACCESS_TOKEN")


STORY_RE = re.compile(r'<p[^>]*>\s*<a href="(?P<url>https?://[^"]+)"[^>]*font-weight:bold[^>]*>(?P<title>.*?)</a>(?P<rest>.*?)</p>', re.S)


def strip_tags(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", s)).split())


STORY_RE = re.compile(r'<p[^>]*>\s*<a href="(?P<url>https?://[^"]+)"[^>]*font-weight:bold[^>]*>(?P<title>.*?)</a>(?P<rest>.*?)</p>', re.S)


def parse_stories(issue_html):
    out = []
    for m in STORY_RE.finditer(issue_html):
        segs = re.split(r"<br\s*/?>", m.group("rest"))
        summary = strip_tags(segs[1]) if len(segs) > 1 else ""
        out.append({"title": strip_tags(m.group("title")), "summary": summary, "url": m.group("url")})
    return out


def first_sentences(text, n=2):
    parts = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    return " ".join(parts[:n])


def load_issue(issue_id=None):
    with open(os.path.join(PUBLISHED, "issues.json"), encoding="utf-8") as fh:
        issues = json.load(fh)["issues"]
    if issue_id is None:
        meta = max(issues, key=lambda i: (i.get("date", ""), i["id"]))
    else:
        issue_id = issue_id.zfill(3)
        meta = next((i for i in issues if i["id"] == issue_id), None)
        if not meta:
            raise SystemExit(f"issue {issue_id} not in newsletter/published/issues.json")
    with open(os.path.join(PUBLISHED, meta["id"], "issue.html"), encoding="utf-8") as fh:
        meta = dict(meta, stories_list=parse_stories(fh.read()))
    return meta


def issue_url(meta):
    return f"{SITE}/newsletter/{meta['id']}/"


def load_state(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}


def save_state(path, state):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def fetch_video(meta):
    v = meta.get("video") or {}
    local = os.path.join(PUBLISHED, meta["id"], v.get("file", "video.mp4"))
    if os.path.exists(local):
        return local
    if not v.get("url"):
        return None
    dst = os.path.join(tempfile.gettempdir(), f"nordic-crypto-{meta['id']}-video.mp4")
    log(f"downloading {v['url']}")
    req = urllib.request.Request(v["url"], headers={"User-Agent": UA})
    h = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=300) as r, open(dst, "wb") as fh:
        while b := r.read(1 << 20):
            h.update(b); fh.write(b)
    if v.get("sha256") and h.hexdigest() != v["sha256"]:
        raise RuntimeError(f"video sha256 mismatch for issue {meta['id']}")
    return dst


def is_live(url):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except Exception:
        return False


def log(msg):
    print(f"[fb-newsletter] {msg}", file=sys.stderr, flush=True)


def build_post(meta):
    n = meta.get("number") or int(meta["id"])
    title = f"Nordic Crypto #{n}: " + re.sub(rf"^Nordic Crypto #{n}:\s*", "", meta["title"])
    lines = [meta.get("subtitle", ""), "", "Watch the newsreel, and read the full issue here:", issue_url(meta), "", "This week's stories:"]
    for i, s in enumerate(meta["stories_list"], 1):
        lines += ["", f"{i}. {s['title']}"]
        if s["summary"]:
            lines.append(first_sentences(s["summary"]))
        lines.append(s["url"])
    lines += ["", "Every issue: https://nordiccrypto.no/newsletter/"]
    return {"title": title[:255], "description": "\n".join(lines)}


def graph_post(url, fields, file_path=None):
    if file_path:
        b = "nc" + secrets.token_hex(12)
        parts = [f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in fields.items()]
        with open(file_path, "rb") as fh:
            parts.append(f"--{b}\r\nContent-Disposition: form-data; name=\"source\"; filename=\"video.mp4\"\r\nContent-Type: video/mp4\r\n\r\n".encode() + fh.read() + b"\r\n")
        data, ctype = b"".join(parts) + f"--{b}--\r\n".encode(), f"multipart/form-data; boundary={b}"
    else:
        data, ctype = urllib.parse.urlencode(fields).encode(), "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": ctype, "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Graph API -> {e.code}: {e.read()[:500].decode('utf-8', 'replace')}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--issue")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--upload", action="store_true", help="send the MP4 bytes instead of file_url")
    ap.add_argument("--state", default=STATE)
    a = ap.parse_args(argv)

    meta = load_issue(a.issue)
    post = build_post(meta)
    state = load_state(a.state)
    v = meta.get("video") or {}
    if a.dry_run:
        how = "none" if not v else ("upload video.mp4" if a.upload or not v.get("url") else f"file_url {v['url']}")
        print(f"# Issue {meta['id']} ({meta['date']}): Facebook Page video post [{how}]"
              f"{' [already posted, a real run would skip]' if meta['id'] in state else ''}")
        print(f"\nTitle: {post['title']}\n\nDescription:\n{post['description']}")
        return 0
    if meta["id"] in state:
        log(f"issue {meta['id']} already posted ({state[meta['id']].get('posted_at')}); nothing to do")
        return 0
    missing = [k for k in ENV if not os.environ.get(k)]
    if missing:
        log(f"skipping: missing {', '.join(missing)}")
        return 0
    if not v:
        log(f"skipping: issue {meta['id']} has no video")
        return 0
    if not is_live(issue_url(meta)):
        log(f"skipping: {issue_url(meta)} is not live yet")
        return 0
    page, token = os.environ["FB_PAGE_ID"], os.environ["FB_PAGE_ACCESS_TOKEN"]
    fields = {"title": post["title"], "description": post["description"], "access_token": token}
    url = f"{GRAPH}/{page}/videos"
    if a.upload or not v.get("url"):
        res = graph_post(url, fields, fetch_video(meta))
    else:
        res = graph_post(url, dict(fields, file_url=v["url"]))
    vid = res["id"]
    state[meta["id"]] = {"video_id": vid, "posted_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                         "url": f"https://www.facebook.com/{page}/videos/{vid}"}
    save_state(a.state, state)
    log(f"done: video {vid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
