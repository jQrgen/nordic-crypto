#!/usr/bin/env python3
"""Post each new Nordic Crypto newsletter issue to Weibo in Simplified Chinese, once.

Copy: newsletter/published/<id>/social.zh.json (editor-supplied translation of the headline, intro and each story's
headline and summary; the brand stays "Nordic Crypto"). Without that file the issue is skipped, never posted in English.
The file is generated at publish time by tools/social_translate.py (see docs/social-translate.md).

Weibo's public Open API (statuses/share.json) takes text plus ONE image and no video for ordinary apps, and the text
must be at most 140 Chinese characters (2 Latin characters count as 1) and contain a link on the app's safe domain
(nordiccrypto.no). So by default the post is: translated headline, intro, as many story headlines as fit, the issue
link (where the newsreel plays), with the issue's cover image (thumbnail.png) attached. This is the link + cover
fallback. If the app has been granted video upload, set WEIBO_VIDEO_UPLOAD_URL to that endpoint and the MP4 is
uploaded there first (multipart field "video", plus access_token); its returned "media_id"/"fid" is passed to
share.json as "media_id". Any failure there falls back to link + cover.

Before a real post the issue page must answer 200. State: data/weibo_posted.json (issue id -> {"weibo_id", ...}).
Secret: WEIBO_ACCESS_TOKEN (never printed). Missing -> one log line, exit 0.

  python3 tools/weibo_newsletter.py [--issue 002] [--dry-run] [--state data/weibo_posted.json]
"""
import argparse, datetime as dt, hashlib, html, json, os, re, secrets, sys, tempfile, time, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLISHED = os.path.join(ROOT, "newsletter", "published")
SITE = "https://nordiccrypto.no"

UA = "nordic-crypto-weibo-newsletter/1 (+https://nordiccrypto.no/)"
STATE = os.path.join(ROOT, "data", "weibo_posted.json")
SHARE = "https://api.weibo.com/2/statuses/share.json"

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


def copy_status(tr):
    """One line on where the translated copy came from (tools/social_translate.py)."""
    if tr.get("reviewed") is True:
        return "reviewed by a human"
    if tr.get("content_sha"):
        return f"generated ({tr.get('model', '?')}, {tr.get('generated_at', '?')[:10]}), not reviewed yet"
    return "written by hand"


def load_social(meta, lang):
    """Editor-supplied translation newsletter/published/<id>/social.<lang>.json, checked against the issue's stories."""
    path = os.path.join(PUBLISHED, meta["id"], f"social.{lang}.json")
    if not os.path.exists(path):
        return None, f"no {os.path.relpath(path, ROOT)}"
    with open(path, encoding="utf-8") as fh:
        tr = json.load(fh)
    if len(tr.get("stories", [])) != len(meta["stories_list"]):
        return None, f"{os.path.relpath(path, ROOT)} has {len(tr.get('stories', []))} stories, issue has {len(meta['stories_list'])}"
    return tr, ""


def multipart(fields, files):
    """files: {name: (filename, content_type, bytes)} -> (body, content_type)."""
    b = "nc" + secrets.token_hex(12)
    out = [f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in fields.items()]
    for name, (fn, ct, data) in files.items():
        out.append(f"--{b}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{fn}\"\r\nContent-Type: {ct}\r\n\r\n".encode() + data + b"\r\n")
    return b"".join(out) + f"--{b}--\r\n".encode(), f"multipart/form-data; boundary={b}"


def http_json(url, data=None, ctype=None, timeout=600):
    req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET",
                                 headers=dict({"User-Agent": UA}, **({"Content-Type": ctype} if ctype else {})))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{url.split('?')[0]} -> {e.code}: {e.read()[:500].decode('utf-8', 'replace')}")


ENV = ("WEIBO_ACCESS_TOKEN",)
LIMIT = 140


def log(msg):
    print(f"[weibo-newsletter] {msg}", file=sys.stderr, flush=True)


def weibo_len(text):
    """Weibo length: CJK/full-width = 1, ASCII = 0.5 (rounded up)."""
    half = sum(1 if ord(c) < 128 else 2 for c in text)
    return (half + 1) // 2


def build_post(meta, tr):
    url = issue_url(meta)
    head = f"【{tr['title']}】{tr['intro']}"
    tail = f"\n完整内容和新闻视频：{url}"
    lines = []
    for i, s in enumerate(tr["stories"], 1):
        cand = lines + [f"{i}. {s['title']}"]
        if weibo_len(head + "\n" + "\n".join(cand) + tail) > LIMIT:
            break
        lines = cand
    if weibo_len(head + tail) > LIMIT:
        head = f"【{tr['title']}】"
    more = len(tr["stories"]) - len(lines)
    if more and weibo_len(head + "\n" + "\n".join(lines + [f"……等{more}条"]) + tail) <= LIMIT:
        lines.append(f"……等{more}条")
    text = head + ("\n" + "\n".join(lines) if lines else "") + tail
    return text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--issue")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--state", default=STATE)
    a = ap.parse_args(argv)
    meta = load_issue(a.issue)
    tr, why = load_social(meta, "zh")
    state = load_state(a.state)
    cover = os.path.join(PUBLISHED, meta["id"], (meta.get("video") or {}).get("poster", "thumbnail.png"))
    video_url = os.environ.get("WEIBO_VIDEO_UPLOAD_URL")
    if a.dry_run:
        if not tr:
            print(f"# Issue {meta['id']}: would skip ({why}; run tools/social_translate.py --issue {meta['id']})"); return 0
        text = build_post(meta, tr)
        mode = "video upload, link + cover as fallback" if video_url else "link + cover image (no video upload endpoint set)"
        print(f"# Issue {meta['id']} ({meta['date']}): Weibo post [{mode}]{' [already posted]' if meta['id'] in state else ''}")
        print(f"# copy: social.zh.json, {copy_status(tr)}")
        print(f"# cover: {os.path.relpath(cover, ROOT)}  length: {weibo_len(text)}/{LIMIT}\n\n{text}")
        return 0
    if meta["id"] in state:
        log(f"issue {meta['id']} already posted; nothing to do"); return 0
    if not os.environ.get("WEIBO_ACCESS_TOKEN"):
        log("skipping: missing WEIBO_ACCESS_TOKEN"); return 0
    if not tr:
        log(f"skipping: {why}"); return 0
    if not is_live(issue_url(meta)):
        log(f"skipping: {issue_url(meta)} is not live yet"); return 0
    token, text = os.environ["WEIBO_ACCESS_TOKEN"], build_post(meta, tr)
    fields, files = {"access_token": token, "status": text}, {}
    if video_url and meta.get("video"):
        try:
            path = fetch_video(meta)
            with open(path, "rb") as fh:
                body, ct = multipart({"access_token": token}, {"video": ("video.mp4", "video/mp4", fh.read())})
            res = http_json(video_url, body, ct)
            mid = res.get("media_id") or res.get("fid")
            if mid:
                fields["media_id"] = mid
        except Exception as e:
            log(f"video upload failed, posting link + cover: {e}")
    if "media_id" not in fields and os.path.exists(cover):
        with open(cover, "rb") as fh:
            files["pic"] = ("cover.png", "image/png", fh.read())
    body, ct = multipart(fields, files)
    res = http_json(SHARE, body, ct)
    wid = str(res.get("idstr") or res.get("id"))
    state[meta["id"]] = {"weibo_id": wid, "video": "media_id" in fields,
                         "posted_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    save_state(a.state, state)
    log(f"done: weibo {wid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
