#!/usr/bin/env python3
"""Public-talk videos for the Nordic Crypto talks archive.

Metadata comes from the platform: YouTube oEmbed, the watch-page ytInitialData
(title, publish date, channel, description) and, when the watch-page player is
login-walled and omits lengthSeconds, the lengthText on YouTube's own search
result for that video id. Unknown fields stay null. This module does not write
descriptions; those are ours and live in data/talks.json.

  python3 tools/talks.py URL     # print platform metadata as JSON

After new rows are written to data/talks.json, run `python3 tools/event_backfill.py`.
That pass looks up an existing event (series, date span, city, country, organiser)
and creates a previous event when the video page states the day, the place, the
type and the organiser. A talk that cannot be dated or placed stays unlinked.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

UA = "NordicCryptoTalks/0.1 (+https://nordiccrypto.no/about/; public talk archive)"
MONTHS = {name: i for i, name in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}

# Predatory conference mills. A hit in the title, channel or description is not a talk we list.
PREDATORY = re.compile(
    r"\bWASET\b|world academy of science|international conference alerts|conferenceindex|"
    r"\bIRAJ\b|\bIIERD?\b|\bISER\b|\bISSER\b|academics\s+world|scholars\s+forum|research\s+plus",
    re.I,
)


def fetch(url, timeout=30, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept-Language": "en", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def extract_json_assignment(html, marker):
    """Parse the object assigned after `marker` (for example ytInitialData)."""
    i = html.find(marker)
    if i < 0:
        return None
    start = html.find("{", i)
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for j, ch in enumerate(html[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start:j + 1])
                except json.JSONDecodeError:
                    return None
    return None


def text_of(node):
    if not isinstance(node, dict):
        return None
    if isinstance(node.get("simpleText"), str):
        return node["simpleText"]
    runs = node.get("runs")
    if isinstance(runs, list):
        return "".join(r.get("text", "") for r in runs if isinstance(r, dict))
    content = node.get("content")
    if isinstance(content, str):
        return content
    return None


def parse_yt_date(value):
    """YouTube dateText such as 'Aug 13, 2017' or 'Premiered Aug 13, 2017' -> YYYY-MM-DD."""
    if not value:
        return None
    m = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),\s+(\d{4})", value)
    if not m:
        return None
    return f"{int(m.group(3)):04d}-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}"


def length_to_iso(value):
    """YouTube lengthText '1:02:04' or '14:03' -> ISO 8601 duration. None if it does not match."""
    if not value:
        return None
    m = re.fullmatch(r"(?:(\d+):)?(\d{1,2}):(\d{2})", value.strip())
    if not m:
        return None
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2))
    seconds = int(m.group(3))
    if minutes > 59 or seconds > 59:
        return None
    parts = []
    if hours:
        parts.append(f"{hours}H")
    if minutes or hours:
        parts.append(f"{minutes}M")
    parts.append(f"{seconds}S")
    return "PT" + "".join(parts)


def youtube_id(url):
    if not url:
        return None
    try:
        parsed = urllib.parse.urlparse(url.strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if host in ("youtu.be", "www.youtu.be"):
        vid = parsed.path.strip("/").split("/")[0]
        return vid or None
    if host.endswith("youtube.com") or host.endswith("youtube-nocookie.com"):
        q = urllib.parse.parse_qs(parsed.query).get("v")
        if q and q[0]:
            return q[0]
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] in ("embed", "shorts", "live", "v"):
            return parts[1]
    return None


def vimeo_id(url):
    if not url:
        return None
    try:
        parsed = urllib.parse.urlparse(url.strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if not host.endswith("vimeo.com"):
        return None
    m = re.search(r"/(\d+)", parsed.path)
    return m.group(1) if m else None


def parse_search_html(html):
    """Video rows from a YouTube results page. Length is YouTube's lengthText."""
    data = extract_json_assignment(html, "ytInitialData")
    if not data:
        return []
    rows = []

    def walk(node):
        if isinstance(node, dict):
            vr = node.get("videoRenderer")
            if isinstance(vr, dict) and vr.get("videoId"):
                owner = vr.get("ownerText") or {}
                channel_url = None
                runs = owner.get("runs") if isinstance(owner, dict) else None
                if runs and isinstance(runs[0], dict):
                    nav = (((runs[0].get("navigationEndpoint") or {}).get("commandMetadata") or {}).get("webCommandMetadata") or {})
                    channel_url = nav.get("url")
                rows.append({
                    "video_id": vr.get("videoId"),
                    "title": text_of(vr.get("title")),
                    "channel": text_of(vr.get("ownerText")),
                    "channel_path": channel_url,
                    "duration": length_to_iso(text_of(vr.get("lengthText"))),
                    "length_text": text_of(vr.get("lengthText")),
                    "published_text": text_of(vr.get("publishedTimeText")),
                })
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    # YouTube repeats the same renderer in overlays. Keep the first of each id.
    seen = set()
    out = []
    for row in rows:
        if row["video_id"] in seen:
            continue
        seen.add(row["video_id"])
        out.append(row)
    return out


def parse_watch_html(html):
    """Title, publish date, channel and description from a YouTube watch page.

    Returns None when the page has no primary video info (consent wall, or a removed video).
    """
    data = extract_json_assignment(html, "ytInitialData")
    if not data:
        return None
    try:
        contents = data["contents"]["twoColumnWatchNextResults"]["results"]["results"]["contents"]
    except (KeyError, TypeError):
        return None
    primary = next((c["videoPrimaryInfoRenderer"] for c in contents if isinstance(c, dict) and "videoPrimaryInfoRenderer" in c), None)
    secondary = next((c["videoSecondaryInfoRenderer"] for c in contents if isinstance(c, dict) and "videoSecondaryInfoRenderer" in c), None)
    if not primary or not secondary:
        return None
    owner = ((secondary.get("owner") or {}).get("videoOwnerRenderer") or {})
    nav = ((owner.get("navigationEndpoint") or {}).get("commandMetadata") or {}).get("webCommandMetadata") or {}
    desc = (secondary.get("attributedDescription") or {}).get("content")
    if not isinstance(desc, str):
        desc = None
    return {
        "title": text_of(primary.get("title")),
        "published": parse_yt_date(text_of(primary.get("dateText"))),
        "published_text": text_of(primary.get("dateText")),
        "channel": text_of(owner.get("title")),
        "channel_path": nav.get("url"),
        "description": desc,
    }


def description_urls(html):
    """Absolute http(s) links expanded from the watch-page description redirects."""
    data = extract_json_assignment(html, "ytInitialData")
    if not data:
        return []
    found = []

    def walk(node):
        if isinstance(node, dict):
            url = node.get("url")
            if isinstance(url, str) and url.startswith("http"):
                found.append(url)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    try:
        contents = data["contents"]["twoColumnWatchNextResults"]["results"]["results"]["contents"]
    except (KeyError, TypeError):
        return []
    secondary = next((c["videoSecondaryInfoRenderer"] for c in contents if isinstance(c, dict) and "videoSecondaryInfoRenderer" in c), None)
    if not secondary:
        return []
    walk(secondary.get("attributedDescription") or {})
    out = []
    for url in found:
        if "googlevideo.com" in url:
            continue
        parsed = urllib.parse.urlparse(url)
        if "youtube.com" in (parsed.hostname or "") and parsed.path.startswith("/redirect"):
            q = urllib.parse.parse_qs(parsed.query).get("q")
            if q:
                url = q[0]
        if url not in out:
            out.append(url)
    return out


def oembed_youtube(video_id):
    """YouTube oEmbed. None when the video does not exist or embedding is refused."""
    watch = f"https://www.youtube.com/watch?v={urllib.parse.quote(video_id)}"
    url = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(watch, safe="")
    try:
        status, body = fetch(url)
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "source_url": url}
    except urllib.error.URLError:
        return {"ok": False, "status": None, "source_url": url}
    if status != 200:
        return {"ok": False, "status": status, "source_url": url}
    try:
        data = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "status": status, "source_url": url}
    html = data.get("html") or ""
    return {
        "ok": True,
        "status": status,
        "source_url": url,
        "title": data.get("title") or None,
        "channel": data.get("author_name") or None,
        "author_url": data.get("author_url") or None,
        "provider": data.get("provider_name") or None,
        "embed": isinstance(html, str) and "iframe" in html.lower() and "youtube.com/embed/" in html,
    }


def oembed_vimeo(video_id):
    page = f"https://vimeo.com/{video_id}"
    url = "https://vimeo.com/api/oembed.json?url=" + urllib.parse.quote(page, safe="")
    try:
        status, body = fetch(url)
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "source_url": url}
    except urllib.error.URLError:
        return {"ok": False, "status": None, "source_url": url}
    try:
        data = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return {"ok": False, "status": status, "source_url": url}
    html = data.get("html") or ""
    duration = data.get("duration")
    iso = None
    if isinstance(duration, int) and duration >= 0:
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        iso = "PT" + (f"{hours}H" if hours else "") + (f"{minutes}M" if minutes or hours else "") + f"{seconds}S"
    upload = data.get("upload_date")
    published = upload[:10] if isinstance(upload, str) and len(upload) >= 10 else None
    return {
        "ok": True,
        "status": status,
        "source_url": url,
        "title": data.get("title") or None,
        "channel": data.get("author_name") or None,
        "author_url": data.get("author_url") or None,
        "provider": data.get("provider_name") or None,
        "description": data.get("description") or None,
        "published": published,
        "duration": iso,
        "embed": isinstance(html, str) and "player.vimeo.com" in html,
    }


def search_youtube(query):
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query) + "&sp=EgIQAQ%3D%3D"
    status, body = fetch(url)
    html = body.decode("utf-8", errors="replace")
    return {"status": status, "url": url, "videos": parse_search_html(html)}


def watch_youtube(video_id):
    url = f"https://www.youtube.com/watch?v={urllib.parse.quote(video_id)}&hl=en"
    status, body = fetch(url)
    html = body.decode("utf-8", errors="replace")
    parsed = parse_watch_html(html) or {}
    parsed["source_url"] = url
    parsed["http_status"] = status
    parsed["urls"] = description_urls(html)
    parsed["video_id"] = video_id
    return parsed


def main():
    import sys
    if len(sys.argv) < 2:
        print("usage: python3 tools/talks.py VIDEO_URL", file=sys.stderr)
        sys.exit(2)
    url = sys.argv[1]
    vid = youtube_id(url)
    if not vid:
        print("not a YouTube URL", file=sys.stderr)
        sys.exit(1)
    meta = watch_youtube(vid)
    oe = oembed_youtube(vid)
    meta["oembed"] = {k: oe.get(k) for k in ("ok", "title", "channel", "embed", "source_url", "status")}
    # The description can be long. Print it; callers that archive talks must not copy it verbatim.
    print(json.dumps(meta, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
