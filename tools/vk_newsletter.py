#!/usr/bin/env python3
"""Post each new Nordic Crypto newsletter issue to the Nordic Crypto VK community in Russian, once.

Copy: newsletter/published/<id>/social.ru.json (editor-supplied translation of the headline, intro and each story's
headline and summary; the brand stays "Nordic Crypto"). Without that file the issue is skipped, never posted in English.

Flow (VK API 5.199):
  1. video.save(group_id, name, description, wallpost=0) -> upload_url; POST the MP4 there (multipart "video_file").
  2. wall.post(owner_id=-GROUP_ID, from_group=1, message=..., attachments=video<owner>_<id>,<issue link>).
Message: translated headline, intro, every story (headline, summary, link) and the issue link.

Before a real post the issue page must answer 200. State: data/vk_posted.json (issue id -> {"post_id", "video"}); a
video already uploaded is reused if wall.post failed. Secrets: VK_GROUP_ID (numeric, no minus) and VK_ACCESS_TOKEN
(community or user token with video and wall access; never printed). Missing -> one log line, exit 0.

  python3 tools/vk_newsletter.py [--issue 002] [--dry-run] [--state data/vk_posted.json]
"""
import argparse, datetime as dt, hashlib, html, json, os, re, secrets, sys, tempfile, time, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLISHED = os.path.join(ROOT, "newsletter", "published")
SITE = "https://nordiccrypto.no"

UA = "nordic-crypto-vk-newsletter/1 (+https://nordiccrypto.no/)"
STATE = os.path.join(ROOT, "data", "vk_posted.json")
API = "https://api.vk.com/method/"

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


V = "5.199"
ENV = ("VK_GROUP_ID", "VK_ACCESS_TOKEN")


def log(msg):
    print(f"[vk-newsletter] {msg}", file=sys.stderr, flush=True)


def build_post(meta, tr):
    lines = [tr["title"], "", tr["intro"], "", f"Видеообзор и полный выпуск: {issue_url(meta)}", "", "Новости недели:"]
    for i, (s, src) in enumerate(zip(tr["stories"], meta["stories_list"]), 1):
        lines += ["", f"{i}. {s['title']}", s["summary"], src["url"]]
    lines += ["", f"Все выпуски: {SITE}/newsletter/"]
    return {"name": tr["title"][:128], "message": "\n".join(lines)}


def vk(method, token, **params):
    res = http_json(API + method, urllib.parse.urlencode(dict(params, access_token=token, v=V)).encode(),
                    "application/x-www-form-urlencoded")
    if "error" in res:
        raise RuntimeError(f"VK {method}: {res['error'].get('error_code')} {res['error'].get('error_msg')}")
    return res["response"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--issue")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--state", default=STATE)
    a = ap.parse_args(argv)
    meta = load_issue(a.issue)
    tr, why = load_social(meta, "ru")
    state = load_state(a.state)
    done = state.get(meta["id"], {})
    if a.dry_run:
        if not tr:
            print(f"# Issue {meta['id']}: would skip ({why})"); return 0
        p = build_post(meta, tr)
        print(f"# Issue {meta['id']} ({meta['date']}): VK wall post on -VK_GROUP_ID with video "
              f"[{'video.save + upload' if meta.get('video') else 'no video'}]{' [already posted]' if done.get('post_id') else ''}")
        print(f"# video name: {p['name']}\n\n{p['message']}")
        return 0
    if done.get("post_id"):
        log(f"issue {meta['id']} already posted; nothing to do"); return 0
    missing = [k for k in ENV if not os.environ.get(k)]
    if missing:
        log(f"skipping: missing {', '.join(missing)}"); return 0
    if not tr:
        log(f"skipping: {why}"); return 0
    if not is_live(issue_url(meta)):
        log(f"skipping: {issue_url(meta)} is not live yet"); return 0
    gid, token = os.environ["VK_GROUP_ID"].lstrip("-"), os.environ["VK_ACCESS_TOKEN"]
    p = build_post(meta, tr)
    attach = done.get("video")
    if not attach and meta.get("video"):
        up = vk("video.save", token, group_id=gid, name=p["name"], description=f"{tr['intro']}\n{issue_url(meta)}", wallpost=0)
        with open(fetch_video(meta), "rb") as fh:
            body, ct = multipart({}, {"video_file": ("video.mp4", "video/mp4", fh.read())})
        http_json(up["upload_url"], body, ct)
        attach = f"video{up.get('owner_id', '-' + gid)}_{up['video_id']}"
        state[meta["id"]] = {"video": attach}
        save_state(a.state, state)
        log(f"uploaded {attach}")
    attachments = ",".join(x for x in (attach, issue_url(meta)) if x)
    res = vk("wall.post", token, owner_id=f"-{gid}", from_group=1, message=p["message"], attachments=attachments)
    state[meta["id"]] = {"video": attach, "post_id": res["post_id"],
                         "url": f"https://vk.com/wall-{gid}_{res['post_id']}",
                         "posted_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    save_state(a.state, state)
    log(f"done: https://vk.com/wall-{gid}_{res['post_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
