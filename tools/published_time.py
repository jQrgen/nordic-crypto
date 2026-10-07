"""Article publish time.

The same order is used for every source path:

- RSS/Atom feeds (and Bing News RSS, which is how newspapers without a working
  feed, and many justice and official outlets, are found)
- scraped non-RSS pages (HTML list sources, manual add, reader tips)
- each outlet on a multi-source story (also_covered_by keeps that outlet's own time)

Order, first hit wins:

1. ``article:published_time`` (property or name)
2. JSON-LD ``datePublished`` (then a meta ``itemprop="datePublished"``)
3. ``<time datetime>`` that is not a modified/updated time
4. the feed's published date (RSS ``pubDate`` / Atom ``published`` only)

``dateModified``, ``article:modified_time``, Atom/RSS updated, and the time we
fetched the page are never the published time.

A value with an offset is converted from that offset. A value with no offset is
read as wall time in the publisher's zone (Europe/Oslo, Europe/Stockholm,
Europe/Copenhagen, Europe/Helsinki, Atlantic/Reykjavik), including daylight
saving time, and stored as UTC.
"""
import datetime as dt
import json
import re
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

UTC = dt.timezone.utc
ZONES = {
    "NO": "Europe/Oslo",
    "SE": "Europe/Stockholm",
    "DK": "Europe/Copenhagen",
    "FI": "Europe/Helsinki",
    "IS": "Atlantic/Reykjavik",
}
TLD_COUNTRY = {".no": "NO", ".se": "SE", ".dk": "DK", ".fi": "FI", ".is": "IS", ".ax": "FI"}
ARTICLE_TYPES = {
    "newsarticle", "article", "reportagenewsarticle", "analysisnewsarticle",
    "blogposting", "liveblogposting", "report", "webpage", "newsmediaobject",
    "mediaobject",
}
SKIP_TYPES = {"comment", "commentaction", "usercomments", "answer", "question"}
_OFFSET = re.compile(r"([+-]\d{2})(\d{2})$")


class Instant:
    """A parsed publish time. ``date_only`` means the source gave a calendar day and no clock time."""

    def __init__(self, when, date_only, zone, civil_date, source):
        self.dt = when
        self.date_only = date_only
        self.zone = zone
        self.civil_date = civil_date
        self.source = source


def zone_for(country=None, url=None):
    """IANA zone for an article. The site's country TLD wins over the feed's country code."""
    if url:
        from urllib.parse import urlparse
        host = (urlparse(url).netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        for tld, code in TLD_COUNTRY.items():
            if host.endswith(tld):
                return ZONES[code]
    if country in ZONES:
        return ZONES[country]
    return None


def utc_iso(when):
    """UTC ISO-8601 with seconds and a numeric offset, matching the news file."""
    if when is None:
        return None
    if isinstance(when, Instant):
        when = when.dt
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return when.astimezone(UTC).replace(microsecond=0).isoformat(timespec="seconds")


def _zone(name):
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except Exception:
        return None


def parse_instant(value, zone=None):
    """Parse one timestamp. ``zone`` is an IANA name used only when ``value`` has no offset."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            inst = parse_instant(item, zone)
            if inst:
                return inst
        return None
    if isinstance(value, dict):
        return parse_instant(value.get("@value") or value.get("value"), zone)
    raw = str(value).strip()
    if not raw:
        return None
    zinfo = _zone(zone)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        day = dt.date.fromisoformat(raw)
        # Noon UTC keeps the calendar day. There is no clock time to convert.
        return Instant(dt.datetime(day.year, day.month, day.day, 12, tzinfo=UTC), True, zinfo, day, "date")
    text = raw.replace("Z", "+00:00").replace("z", "+00:00")
    text = _OFFSET.sub(r"\1:\2", text)
    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)
    try:
        when = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if when.tzinfo is None:
        if zinfo is not None:
            when = when.replace(tzinfo=zinfo)
        else:
            when = when.replace(tzinfo=UTC)
    when = when.astimezone(UTC)
    civil = when.astimezone(zinfo).date() if zinfo is not None else when.date()
    return Instant(when, False, zinfo, civil, "clock")


def _meta(soup, **attrs):
    tag = soup.find("meta", attrs=attrs)
    if not tag:
        return None
    content = (tag.get("content") or "").strip()
    return content or None


def _jsonld_values(soup):
    found = []

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        types = node.get("@type") or []
        if isinstance(types, str):
            types = [types]
        types = [t for t in types if isinstance(t, str)]
        if "datePublished" in node:
            found.append((types, node.get("datePublished")))
        for key, val in node.items():
            if key.startswith("date"):
                continue
            if isinstance(val, (dict, list)):
                walk(val)

    for script in soup.find_all("script"):
        kind = (script.get("type") or "").lower()
        if "ld+json" not in kind:
            continue
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        walk(data)
    return found


def _jsonld_published(soup, zone):
    rows = _jsonld_values(soup)

    def rank(types):
        low = [t.lower() for t in types]
        if any(t in SKIP_TYPES for t in low):
            return 9
        if any(t in ARTICLE_TYPES or t.endswith("article") for t in low):
            return 0
        return 1

    for types, raw in sorted(rows, key=lambda row: rank(row[0])):
        if rank(types) >= 9:
            continue
        inst = parse_instant(raw, zone)
        if inst:
            inst.source = "jsonld"
            return inst
    return None


def _time_published(soup, zone):
    found = []
    for index, tag in enumerate(soup.find_all("time")):
        raw = tag.get("datetime")
        if not raw:
            continue
        classes = tag.get("class") or []
        if isinstance(classes, str):
            classes = [classes]
        blob = " ".join([tag.get("itemprop") or "", " ".join(classes), tag.get("id") or ""]).lower()
        if any(word in blob for word in ("modified", "updated", "datemodified")):
            continue
        inst = parse_instant(raw, zone)
        if not inst:
            continue
        rank = 0 if ("published" in blob or "datepublished" in blob) else 1
        inst.source = "time"
        found.append((rank, index, inst))
    if not found:
        return None
    found.sort(key=lambda row: (row[0], row[1]))
    return found[0][2]


def published_from_soup(soup, zone=None):
    """Publish time from a parsed article page, or None when the page does not say.

    ``article:published_time`` may be a property (most outlets) or a name (DN).
    """
    raw = _meta(soup, property="article:published_time") or _meta_by_name(soup, "article:published_time")
    if raw:
        inst = parse_instant(raw, zone)
        if inst:
            inst.source = "article:published_time"
            return inst
    inst = _jsonld_published(soup, zone)
    if inst:
        return inst
    micro = _meta_by_itemprop(soup, "datePublished")
    if micro:
        inst = parse_instant(micro, zone)
        if inst:
            inst.source = "jsonld"
            return inst
    return _time_published(soup, zone)


def _meta_by_name(soup, name):
    for tag in soup.find_all("meta"):
        if (tag.get("name") or "").lower() == name.lower():
            content = (tag.get("content") or "").strip()
            if content:
                return content
    return None


def _meta_by_itemprop(soup, name):
    for tag in soup.find_all("meta"):
        if (tag.get("itemprop") or "").lower() == name.lower():
            content = (tag.get("content") or "").strip()
            if content:
                return content
    return None


def published_from_html(html, zone=None):
    if not html:
        return None
    return published_from_soup(BeautifulSoup(html, "lxml"), zone)


def from_feed_entry(entry, zone=None):
    """Publication time on an RSS/Atom entry. Ignores updated/modified."""
    if not entry:
        return None
    raw = entry.get("published") or entry.get("pubDate")
    inst = parse_instant(raw, zone) if raw else None
    if inst:
        inst.source = "feed"
        return inst
    parsed = entry.get("published_parsed")
    if not parsed:
        return None
    try:
        when = dt.datetime(*parsed[:6], tzinfo=UTC)
    except (TypeError, ValueError):
        return None
    return Instant(when, False, _zone(zone), when.date(), "feed")


def choose_published(page, feed):
    """Page clock time, else the feed time, else a date-only page day.

    A date-only page value does not wipe a feed clock time on that same local day.
    It does replace the feed when the calendar day disagrees. Returns a UTC datetime.
    """
    if page and not page.date_only:
        return page.dt
    if page and page.date_only and feed:
        zone = page.zone or UTC
        feed_day = feed.dt.astimezone(zone).date()
        if feed_day != page.civil_date:
            return page.dt
        return feed.dt
    if page:
        return page.dt
    if feed:
        return feed.dt
    return None


def browser_html(url, user_agent=None, timeout=25):
    """Read a public page with headless Chrome when the HTTP client is stuck in a redirect loop.

    Used only after robots.txt has already allowed the URL. Returns HTML or None.
    """
    import os
    import shutil
    import subprocess
    import tempfile

    chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
    if not chrome:
        return None
    cmd = [
        chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
        "--timeout=18000", "--virtual-time-budget=12000", "--dump-dom", url,
    ]
    if user_agent:
        cmd[1:1] = ["--user-agent=" + user_agent]
    fd, path = tempfile.mkstemp(suffix=".html")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as out:
            try:
                subprocess.run(cmd, stdout=out, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
            except subprocess.TimeoutExpired:
                pass
        html = open(path, encoding="utf-8", errors="replace").read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    if "<html" not in html.lower():
        return None
    return html
