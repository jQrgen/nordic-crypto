#!/usr/bin/env python3
"""Post each new Nordic Crypto newsletter issue to X (@nordiccryptobot) as a thread, with the newsreel video, once.

Thread shape:
  1. Headline, short intro, issue link, and the issue's video.mp4 attached natively.
  2..n. One reply per story: headline, a 1-2 sentence summary, the source link.
Every post fits 280 characters, with each URL counted as 23 (X's t.co length). Long summaries are cut at a sentence
or word boundary, never mid-word.

Source: newsletter/published/issues.json and newsletter/published/<id>/issue.html. The video is the local
newsletter/published/<id>/video.mp4 when present, otherwise video.url from issues.json (checked against video.sha256).
Before a real post the issue page on nordiccrypto.no must answer 200, so nothing is posted before the issue is live.

State: data/x_posted.json maps issue id -> {"posted_at", "tweet_ids"}. A posted issue is never posted again. If a
thread fails midway, the posts made so far are saved and the next run continues as replies to the last one.

Secrets (env, never printed): X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET (OAuth 1.0a user context of
@nordiccryptobot, app with Read and Write). If any is missing the script logs one line and exits 0 without posting.

  python3 tools/x_newsletter.py [--issue 002] [--dry-run] [--state data/x_posted.json] [--no-video]
Without --issue the newest issue in issues.json is used.
"""
import argparse, base64, datetime as dt, hashlib, hmac, html, json, os, re, secrets, sys, tempfile, time
import urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLISHED = os.path.join(ROOT, "newsletter", "published")
STATE = os.path.join(ROOT, "data", "x_posted.json")
SITE = "https://nordiccrypto.no"
UPLOAD = "https://upload.twitter.com/1.1/media/upload.json"
TWEETS = "https://api.twitter.com/2/tweets"
UA = "nordic-crypto-x-newsletter/1 (+https://nordiccrypto.no/)"
LIMIT, URL_LEN = 280, 23
CHUNK = 4 * 1024 * 1024
ENV = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")
URL_RE = re.compile(r"https?://\S+")


def log(msg):
    print(f"[x-newsletter] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------- text
def x_len(text):
    """Length as X counts it: every URL is 23 characters."""
    n, last = 0, 0
    for m in URL_RE.finditer(text):
        n += len(text[last:m.start()]) + URL_LEN
        last = m.end()
    return n + len(text[last:])


def clip(text, budget):
    """Fit text into budget chars: whole sentences first, then whole words plus an ellipsis."""
    text = " ".join(text.split())
    if len(text) <= budget:
        return text
    out = ""
    for s in re.split(r"(?<=[.!?])\s+", text):
        cand = (out + " " + s).strip()
        if len(cand) > budget:
            break
        out = cand
    if out:
        return out
    words, out = text.split(), ""
    for w in words:
        cand = (out + " " + w).strip()
        if len(cand) + 1 > budget:
            break
        out = cand
    return (out.rstrip(",;:—-") + "…") if out else ""


def first_sentences(text, n=2):
    parts = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    return " ".join(parts[:n])


def compose(head, body, url, tail=""):
    """head\n\nbody\n\nurl, clipping body (then head) so x_len <= 280."""
    fixed = x_len(f"{head}\n\n\n\n{url}") + (len(tail) + 1 if tail else 0)
    if fixed > LIMIT:
        head = clip(head, LIMIT - (fixed - len(head)) - 4)
        fixed = x_len(f"{head}\n\n\n\n{url}") + (len(tail) + 1 if tail else 0)
    body = clip(body, LIMIT - fixed) if body else ""
    parts = [head] + ([body] if body else []) + [url]
    txt = "\n\n".join(parts) + (f"\n{tail}" if tail else "")
    assert x_len(txt) <= LIMIT, txt
    return txt


# ---------------------------------------------------------------- issue
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


def build_thread(meta):
    n = meta.get("number") or int(meta["id"])
    title = meta["title"]
    title = re.sub(rf"^Nordic Crypto #{n}:\s*", "", title)
    head = f"Nordic Crypto #{n}: {title}"
    intro = meta.get("subtitle", "") + " Watch the newsreel below, and the full issue at the link. 🧵"
    posts = [compose(head, intro, issue_url(meta))]
    stories = meta["stories_list"]
    for i, s in enumerate(stories, 1):
        posts.append(compose(f"{i}/{len(stories)} {s['title']}", first_sentences(s["summary"]), s["url"]))
    posts.append(compose("That's the week in Nordic crypto.", "Subscribe and read every issue on Nordic Crypto:", f"{SITE}/newsletter/"))
    return posts


# ---------------------------------------------------------------- state
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


# ---------------------------------------------------------------- X API
def _pct(s):
    return urllib.parse.quote(str(s), safe="~-._")


def oauth_header(method, url, creds, params=None):
    """OAuth 1.0a HMAC-SHA1. params = query/form params that are part of the signature (not JSON or multipart)."""
    key, secret, token, token_secret = creds
    oauth = {"oauth_consumer_key": key, "oauth_nonce": secrets.token_hex(16), "oauth_signature_method": "HMAC-SHA1",
             "oauth_timestamp": str(int(time.time())), "oauth_token": token, "oauth_version": "1.0"}
    allp = dict(params or {}, **oauth)
    pstr = "&".join(f"{_pct(k)}={_pct(v)}" for k, v in sorted((_pct(k), _pct(v)) for k, v in allp.items()))
    base = "&".join([method.upper(), _pct(url), _pct(pstr)])
    sig = base64.b64encode(hmac.new(f"{_pct(secret)}&{_pct(token_secret)}".encode(), base.encode(), hashlib.sha1).digest()).decode()
    oauth["oauth_signature"] = sig
    return "OAuth " + ", ".join(f'{_pct(k)}="{_pct(v)}"' for k, v in sorted(oauth.items()))


def _call(req):
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"X API {req.get_method()} {req.full_url.split('?')[0]} -> {e.code}: {e.read()[:500].decode('utf-8', 'replace')}")


def x_form(creds, url, params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": oauth_header("POST", url, creds, params), "Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA})
    return _call(req)


def x_get(creds, url, params):
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers={
        "Authorization": oauth_header("GET", url, creds, params), "User-Agent": UA})
    return _call(req)


def upload_video(creds, path):
    """v1.1 chunked upload: INIT, APPEND (4 MB segments), FINALIZE, then poll STATUS until processing succeeds."""
    size = os.path.getsize(path)
    init = x_form(creds, UPLOAD, {"command": "INIT", "total_bytes": size, "media_type": "video/mp4", "media_category": "tweet_video"})
    mid = init["media_id_string"]
    log(f"INIT media {mid} ({size} bytes)")
    with open(path, "rb") as fh:
        seg = 0
        while chunk := fh.read(CHUNK):
            q = {"command": "APPEND", "media_id": mid, "segment_index": seg}
            boundary = "nc" + secrets.token_hex(12)
            body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"media\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode() \
                + chunk + f"\r\n--{boundary}--\r\n".encode()
            req = urllib.request.Request(UPLOAD + "?" + urllib.parse.urlencode(q), data=body, method="POST", headers={
                "Authorization": oauth_header("POST", UPLOAD, creds, q), "Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": UA})
            _call(req)
            seg += 1
    log(f"APPEND {seg} segments")
    info = x_form(creds, UPLOAD, {"command": "FINALIZE", "media_id": mid}).get("processing_info")
    deadline = time.time() + 600
    while info and info.get("state") in ("pending", "in_progress"):
        if time.time() > deadline:
            raise RuntimeError("video processing timed out")
        time.sleep(max(1, int(info.get("check_after_secs", 5))))
        info = x_get(creds, UPLOAD, {"command": "STATUS", "media_id": mid}).get("processing_info")
        log(f"STATUS {info and info.get('state')} {info and info.get('progress_percent', '')}")
    if info and info.get("state") == "failed":
        raise RuntimeError(f"video processing failed: {info.get('error')}")
    return mid


def create_post(creds, text, reply_to=None, media_id=None):
    payload = {"text": text}
    if reply_to:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to}
    if media_id:
        payload["media"] = {"media_ids": [media_id]}
    req = urllib.request.Request(TWEETS, data=json.dumps(payload).encode(), method="POST", headers={
        "Authorization": oauth_header("POST", TWEETS, creds), "Content-Type": "application/json", "User-Agent": UA})
    return _call(req)["data"]["id"]


# ---------------------------------------------------------------- video / liveness
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


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--issue", help="issue id, e.g. 002 (default: newest)")
    ap.add_argument("--dry-run", action="store_true", help="print the thread, post nothing, leave the state file alone")
    ap.add_argument("--state", default=STATE)
    ap.add_argument("--no-video", action="store_true", help="post without the video")
    a = ap.parse_args(argv)

    meta = load_issue(a.issue)
    posts = build_thread(meta)
    state = load_state(a.state)
    done = state.get(meta["id"], {})
    has_video = bool(meta.get("video")) and not a.no_video

    if a.dry_run:
        print(f"# Issue {meta['id']} ({meta['date']}): {len(posts)} posts{' + video' if has_video else ''}"
              f"{' [already posted, a real run would skip]' if done.get('complete') else ''}")
        for i, p in enumerate(posts, 1):
            media = "  [+ video.mp4]" if i == 1 and has_video else ""
            print(f"\n--- {i}/{len(posts)} ({x_len(p)}/280){media}\n{p}")
        return 0

    if done.get("complete"):
        log(f"issue {meta['id']} already posted ({done.get('posted_at')}); nothing to do")
        return 0
    missing = [k for k in ENV if not os.environ.get(k)]
    if missing:
        log(f"skipping: missing {', '.join(missing)}")
        return 0
    creds = tuple(os.environ[k] for k in ENV)
    if not is_live(issue_url(meta)):
        log(f"skipping: {issue_url(meta)} is not live yet")
        return 0

    ids = list(done.get("tweet_ids", []))
    media_id = None
    if not ids and has_video:
        path = fetch_video(meta)
        if path:
            media_id = upload_video(creds, path)
    for i, text in enumerate(posts):
        if i < len(ids):
            continue  # resumed after a partial run
        tid = create_post(creds, text, reply_to=ids[-1] if ids else None, media_id=media_id if i == 0 else None)
        ids.append(tid)
        state[meta["id"]] = {"tweet_ids": ids, "complete": False}
        save_state(a.state, state)
        log(f"posted {i + 1}/{len(posts)}: {tid}")
        time.sleep(2)
    state[meta["id"]] = {"tweet_ids": ids, "complete": True,
                         "posted_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                         "url": f"https://x.com/nordiccryptobot/status/{ids[0]}"}
    save_state(a.state, state)
    log(f"done: https://x.com/nordiccryptobot/status/{ids[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
