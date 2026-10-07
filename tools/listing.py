#!/usr/bin/env python3
"""Public listing reader for sources that have no RSS feed.

Order, first hit that yields article links: sitemap.xml (including one index
level), a CMS JSON feed robots.txt allows, then the public index page
(JSON-LD, __NEXT_DATA__, or article links). Only title, date, URL and summary.
No article body. Callers enforce robots.txt, the site delay and a small cap.
"""
import json, re, urllib.parse
from datetime import datetime, timezone

ARTICLE = re.compile(
    r"/(20\d{2})([-/]\d{1,2}){1,2}\b|"
    r"/(nyheter|nyhet|news|artikel|artikkel|artikkeli|frett\w*|blogg|blog|blogs|"
    r"press|tiedote|pressemelding|pressemeddelelse|innsikt|aktuelt|artikler|"
    r"gjesteinnlegg)/",
    re.I,
)
SKIP_PATH = re.compile(
    r"/(?:login|logg-inn|innlogget|sign-in|cookie|personvern|privacy|vilkar|vilkår|"
    r"terms|annonse|abonnement|wp-admin|wp-login|tag|tags|category|kategori|"
    r"forfatter|author|sok|search|kontakt|contact|om-oss|about)(?:/|$)",
    re.I,
)
INDEX_PATHS = ("", "/innsikt/nyheter", "/innsikt/blogg", "/nyheter", "/news", "/blogg", "/blog", "/aktuelt", "/press", "/artikler")
CMS_PATHS = ("/wp-json/wp/v2/posts?per_page=8",)
NO_RSS = re.compile(r"no working rss|no rss", re.I)
BLOCKED = re.compile(
    r"robots\.txt disallow|HTTP 403|\bblocked\b|Same feed as|not confirmed|Bonnier login|mediedatabasen",
    re.I,
)


def origin_of(url):
    p = urllib.parse.urlparse(url or "")
    if p.scheme not in ("http", "https") or not p.netloc:
        return ""
    return f"{p.scheme}://{p.netloc}"


def source_method(s):
    """rss, html, sitemap, search or manual. The sources table shows this."""
    m = s.get("method")
    if m in ("rss", "html", "sitemap", "search", "manual"):
        return m
    t = s.get("type") or ""
    if t in ("rss", "rss-all"):
        return "rss"
    if t == "sitemap":
        return "sitemap"
    if t == "html":
        return "html"
    if t == "bing":
        return "search"
    return "manual"


def _abs(base, href):
    if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
        return ""
    return urllib.parse.urljoin(base, href)


def _host(url):
    return (urllib.parse.urlparse(url).hostname or "").lower().removeprefix("www.")


def url_date(url):
    m = re.search(r"/(20\d{2})[-/](\d{1,2})[-/](\d{1,2})(?:\b|/|-)", url or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 12, tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_iso(value):
    if not value or not isinstance(value, str):
        return None
    value = value.strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(value)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def _article_like(url):
    path = urllib.parse.urlparse(url).path or "/"
    if SKIP_PATH.search(path):
        return False
    return bool(ARTICLE.search(path))


def parse_sitemap(text, base):
    """Return (child_sitemap_urls, entries). Entries have url and maybe title, summary, published."""
    if not text or "<html" in text[:400].lower():
        return [], []
    children = []
    if "<sitemapindex" in text.lower() or re.search(r"<sitemap\b", text, re.I):
        children = re.findall(r"<sitemap\b[^>]*>\s*<loc>\s*([^<]+?)\s*</loc>", text, re.I)
    entries = []
    for block in re.findall(r"<url\b[^>]*>(.*?)</url>", text, re.I | re.S):
        loc = re.search(r"<loc>\s*([^<]+?)\s*</loc>", block, re.I)
        if not loc:
            continue
        url = _abs(base, loc.group(1).strip())
        if not url.startswith("http"):
            continue
        title = re.search(r"<news:title>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</news:title>", block, re.I | re.S)
        when = re.search(r"<news:publication_date>\s*([^<]+)", block, re.I) or re.search(r"<lastmod>\s*([^<]+)", block, re.I)
        entries.append({
            "url": url,
            "title": re.sub(r"\s+", " ", title.group(1)).strip() if title else "",
            "summary": "",
            "published": _parse_iso(when.group(1)) if when else url_date(url),
        })
    if not entries and not children:
        # a urlset that the block regex missed (self-closing or odd spacing)
        for loc in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", text, re.I)[:500]:
            url = _abs(base, loc.strip())
            if url.startswith("http"):
                entries.append({"url": url, "title": "", "summary": "", "published": url_date(url)})
    return [c.strip() for c in children], entries


def _types(node):
    t = node.get("@type") if isinstance(node, dict) else None
    if isinstance(t, list):
        return {str(x).lower() for x in t}
    return {str(t).lower()} if t else set()


def _walk_jsonld(node, base, out):
    if isinstance(node, list):
        for x in node:
            _walk_jsonld(x, base, out)
        return
    if not isinstance(node, dict):
        return
    if "@graph" in node:
        _walk_jsonld(node["@graph"], base, out)
    types = _types(node)
    if types & {"newsarticle", "blogposting", "article", "report"}:
        url = node.get("url") or node.get("mainEntityOfPage") or ""
        if isinstance(url, dict):
            url = url.get("@id") or ""
        url = _abs(base, str(url))
        title = node.get("headline") or node.get("name") or ""
        summary = node.get("description") or ""
        if isinstance(summary, dict):
            summary = summary.get("text") or ""
        if url.startswith("http") and title:
            out.append({
                "url": url,
                "title": re.sub(r"\s+", " ", str(title)).strip(),
                "summary": re.sub(r"<[^>]+>", " ", str(summary)).strip()[:500],
                "published": _parse_iso(node.get("datePublished") or node.get("dateModified")) or url_date(url),
            })
    for v in node.values():
        if isinstance(v, (dict, list)):
            _walk_jsonld(v, base, out)


def parse_jsonld(html, base):
    out = []
    for raw in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html or "", re.I | re.S):
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        _walk_jsonld(data, base, out)
    return out


def _from_obj(node, base, out, depth=0):
    if depth > 8:
        return
    if isinstance(node, list):
        for x in node[:80]:
            _from_obj(x, base, out, depth + 1)
        return
    if not isinstance(node, dict):
        return
    title = node.get("title") or node.get("headline") or ""
    if isinstance(title, dict):
        title = title.get("rendered") or title.get("text") or ""
    url = node.get("url") or node.get("link") or node.get("path") or node.get("slug") or ""
    if isinstance(url, dict):
        url = url.get("rendered") or url.get("href") or ""
    url = str(url)
    if url and not url.startswith("http"):
        if url.startswith("/"):
            url = _abs(base, url)
        elif node.get("slug"):
            url = ""
    published = _parse_iso(node.get("date") or node.get("datePublished") or node.get("publishedAt") or node.get("published") or "") or url_date(url)
    summary = node.get("excerpt") or node.get("description") or node.get("summary") or ""
    if isinstance(summary, dict):
        summary = summary.get("rendered") or summary.get("text") or ""
    if url.startswith("http") and title and (published or _article_like(url)):
        out.append({
            "url": url,
            "title": re.sub(r"<[^>]+>", " ", str(title)).strip(),
            "summary": re.sub(r"<[^>]+>", " ", str(summary)).strip()[:500],
            "published": published,
        })
    for v in node.values():
        if isinstance(v, (dict, list)):
            _from_obj(v, base, out, depth + 1)


def parse_next_data(html, base):
    m = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html or "", re.I | re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    out = []
    _from_obj(data, base, out)
    return out


def parse_wp_posts(text, base):
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for node in data[:20]:
        if not isinstance(node, dict):
            continue
        title = (node.get("title") or {}).get("rendered") if isinstance(node.get("title"), dict) else node.get("title")
        url = node.get("link") or ""
        excerpt = (node.get("excerpt") or {}).get("rendered") if isinstance(node.get("excerpt"), dict) else ""
        if url and title:
            out.append({
                "url": _abs(base, url),
                "title": re.sub(r"<[^>]+>", " ", str(title)).strip(),
                "summary": re.sub(r"<[^>]+>", " ", str(excerpt or "")).strip()[:500],
                "published": _parse_iso(node.get("date")) or url_date(url),
            })
    return out


def parse_links(html, base):
    out = []
    host = _host(base)
    for href, inner in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html or "", re.I | re.S):
        url = _abs(base, href)
        if _host(url) != host or not _article_like(url):
            continue
        title = re.sub(r"<[^>]+>", " ", inner)
        title = re.sub(r"\s+", " ", title).strip()
        if not (8 <= len(title) <= 180):
            continue
        out.append({"url": url, "title": title, "summary": "", "published": url_date(url)})
    return out


def choose(entries, limit=30):
    """Prefer real article URLs, newest first, capped."""
    seen, rows = set(), []
    for e in entries:
        url = (e.get("url") or "").split("#")[0]
        if not url.startswith("http") or url in seen:
            continue
        seen.add(url)
        e = dict(e)
        e["url"] = url
        if not e.get("published"):
            e["published"] = url_date(url)
        rows.append(e)
    if any(_article_like(e["url"]) for e in rows):
        rows = [e for e in rows if _article_like(e["url"])]
    rows.sort(key=lambda e: e["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return rows[:limit]


def _rank_child(url):
    u = url.lower()
    if any(k in u for k in ("news", "post", "article", "blogg", "nyhet", "press")):
        return 0
    return 1


def collect(page_url, get, robots_ok, limit=30):
    """Return (entries, method, error). method is sitemap, html, or "".

    get(url) -> (status_code, text). robots_ok(url) -> bool.
    A disallowed or failed URL is skipped. Nothing is raised.
    """
    origin = origin_of(page_url)
    if not origin:
        return [], "", "no homepage"
    errors = []

    def fetch(url):
        if not robots_ok(url):
            errors.append("robots")
            return 0, ""
        try:
            return get(url)
        except Exception as ex:
            errors.append(type(ex).__name__)
            return 0, ""

    sitemap = origin.rstrip("/") + "/sitemap.xml"
    status, text = fetch(sitemap)
    children, entries = ([], [])
    if status == 200 and text:
        children, entries = parse_sitemap(text, sitemap)
    if not entries and children:
        ordered = sorted(children, key=_rank_child)[:2]
        for child in ordered:
            st, body = fetch(child)
            if st == 200 and body:
                _, more = parse_sitemap(body, child)
                entries.extend(more)
    picked = choose(entries, limit)
    if picked:
        # A sitemap often has the URL and the date, and not the headline.
        # Fill title and summary from the public index (JSON-LD or the link text)
        # so we do not have to open each article.
        if any(not e.get("title") for e in picked):
            extra = []
            home = page_url if str(page_url).startswith("http") else origin
            seen_pages = set()
            for path in ("", "/innsikt/nyheter", "/innsikt/blogg", "/nyheter", "/news", "/blogg", "/blog"):
                url = origin.rstrip("/") + path if path else home
                if url in seen_pages:
                    continue
                seen_pages.add(url)
                st, body = fetch(url)
                if st == 200 and body:
                    extra.extend(parse_jsonld(body, url))
                    extra.extend(parse_next_data(body, url))
                    extra.extend(parse_links(body, url))
                if all(e.get("title") or any(x["url"].split("#")[0] == e["url"] and x.get("title") for x in extra) for e in picked):
                    break
                if len(seen_pages) >= 3:
                    break
            by_url = {}
            for e in extra:
                by_url.setdefault(e["url"].split("#")[0], e)
            for e in picked:
                hit = by_url.get(e["url"])
                if not hit:
                    continue
                if not e.get("title"):
                    e["title"] = hit.get("title") or ""
                if not e.get("summary"):
                    e["summary"] = hit.get("summary") or ""
        return picked, "sitemap", None

    for path in CMS_PATHS:
        url = origin.rstrip("/") + path
        st, body = fetch(url)
        if st == 200 and body and body.lstrip().startswith(("[", "{")):
            picked = choose(parse_wp_posts(body, origin), limit)
            if picked:
                return picked, "html", None

    html_entries = []
    pages = []
    home = page_url if page_url.startswith("http") else origin
    for path in INDEX_PATHS:
        url = origin.rstrip("/") + path if path else home
        if url not in pages:
            pages.append(url)
    for url in pages[:4]:
        st, body = fetch(url)
        if st != 200 or not body:
            continue
        html_entries.extend(parse_jsonld(body, url))
        html_entries.extend(parse_next_data(body, url))
        html_entries.extend(parse_links(body, url))
        if len(choose(html_entries, limit)) >= 5:
            break
    picked = choose(html_entries, limit)
    if picked:
        return picked, "html", None
    return [], "", "no sitemap or index links" if not errors else "no sitemap or index links"


def apply_listing_sources(sources):
    """Turn on the sitemap/HTML reader for sources whose note says there is no RSS.

    Working RSS feeds, Kaupr-style HTML lists, blocked sites and shared feeds
    are left as they are. Returns the ids that were switched on.
    """
    changed = []
    for s in sources:
        if not isinstance(s, dict):
            continue
        if s.get("type") in ("rss", "rss-all") and s.get("enabled") and s.get("feed"):
            s["method"] = "rss"
            continue
        if s.get("type") == "html" and s.get("link_pattern"):
            s["method"] = "html"
            continue
        if s.get("type") == "bing":
            s["method"] = "search"
            continue
        status = s.get("status") or ""
        url = s.get("url") or ""
        if not NO_RSS.search(status) or BLOCKED.search(status) or BLOCKED.search(url):
            if not s.get("method"):
                # A feed we do not read (blocked, dead, or never confirmed) is manual.
                s["method"] = source_method(s) if s.get("enabled") and s.get("feed") else "manual"
            continue
        origin = origin_of(url)
        if not origin:
            s["method"] = "manual"
            continue
        s["type"] = "sitemap"
        s["method"] = "sitemap"
        s["enabled"] = True
        s["feed"] = origin.rstrip("/") + "/sitemap.xml"
        s["max_new_per_run"] = s.get("max_new_per_run") or 8
        note = "No RSS. The fetcher reads sitemap.xml, then the public index page, and keeps only title, date, link and summary."
        if "sitemap.xml" not in status:
            s["status"] = status.rstrip(". ") + ". " + note
        changed.append(s["id"])
    return changed
