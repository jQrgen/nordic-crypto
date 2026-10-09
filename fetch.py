#!/usr/bin/env python3
"""Nordic Crypto – fetches feeds and public list pages for Norway, Sweden, Denmark, Finland and Iceland,
filters on crypto keywords (Norwegian, Swedish, Danish, Finnish, Icelandic, English), de-duplicates and updates
data/news.json and the editor queue queue/review.json. Events are searched in the same run (events.py).

  .venv/bin/python fetch.py            # normal daily run (looks 7 days back)
  .venv/bin/python fetch.py --days 30  # first run / look-back

New items get status "pending" and are NOT published until the editor has written a summary in English
in our own words (queue/approved.json) – see README.md. The front page needs two to four sentences of what the story says; a one-sentence intro is not enough. The feed teaser is stored only locally in
state/teasers.json as working material for the editor and is never published. The article page is read
only for public metadata (title, description, publish time). Article text is never stored. robots.txt
and the per-host delay are respected. Article pictures are never stored either:
og:image, RSS media:content, media:thumbnail and image enclosures are ignored.
See tools/press_images.py and docs/image-policy.md.

The published time is the article's own time: article:published_time, then JSON-LD datePublished,
then <time datetime>, then the outlet's own feed, and only then another feed date. Updated, modified
and fetch times are not used. Bing News RSS stamps Pacific wall time and labels it GMT; that clock
is corrected and marked unverified, and a page time or the outlet feed wins when one can be read.
Naive times are read in the publisher's zone (Europe/Oslo and Europe/Stockholm, and the
other Nordic zones) including daylight saving time, and stored as UTC. See tools/published_time.py.
"""
import argparse, datetime as dt, hashlib, json, os, re, sys, threading, time, urllib.parse, urllib.robotparser
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests, feedparser
from bs4 import BeautifulSoup
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
import coverage
import event_block
import published_time as pubtime
from tools.press_images import entry_carries_article_image, ignored_count, note_og_image, strip_press_images

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import listing  # noqa: E402
P = lambda *a: os.path.join(ROOT, *a)
NOW = dt.datetime.now(dt.timezone.utc)
for d in ("data", "state", "queue", "logs"): os.makedirs(P(d), exist_ok=True)

def load(path, default):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except FileNotFoundError: return default
def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=1); f.write("\n")
    os.replace(tmp, path)

CFG = load(P("sources.json"), None)
import site_url
UA = site_url.expand(CFG["user_agent"]); DELAY = CFG.get("min_delay_seconds", 2)
LOG = open(P("logs", dt.datetime.now().strftime("fetch-%Y%m%d-%H%M%S.log")), "w", encoding="utf-8")
def log(*a):
    s = " ".join(str(x) for x in a)
    with _io:
        print(s, flush=True); LOG.write(s + "\n"); LOG.flush()
def guarded_call(fn):
    """Run fn. Return None, or a short error string. A raised error does not escape."""
    try:
        fn()
        return None
    except Exception as ex:
        return f"{type(ex).__name__}: {ex}"[:200]

# ---------- polite HTTP: robots.txt, per-host rate limit, ETag cache ----------
# Hundreds of feeds run in a small pool. One host is never hit faster than min_delay_seconds.
# A dead feed is recorded and skipped; it does not stop the run.
_robots, _last = {}, {}
_io = threading.Lock()
_host_locks, _host_guard = {}, threading.Lock()
def _host_lock(host):
    with _host_guard:
        return _host_locks.setdefault(host, threading.Lock())
def _pace(host):
    """Caller holds the host lock. Spaces requests to this host."""
    wait = DELAY - (time.time() - _last.get(host, 0))
    if wait > 0: time.sleep(wait)
    _last[host] = time.time()
http_cache = load(P("state", "http_cache.json"), {})
def robots_ok(url):
    p = urllib.parse.urlparse(url); base = f"{p.scheme}://{p.netloc}"
    with _host_lock(p.netloc):
        with _io:
            rp = _robots.get(base)
        if rp is None:
            _pace(p.netloc)
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = requests.get(base + "/robots.txt", headers={"User-Agent": UA}, timeout=15)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except Exception: rp.parse([])
            with _io:
                _robots[base] = rp
        return rp.can_fetch(UA, url)
def get(url, conditional=True):
    host = urllib.parse.urlparse(url).netloc
    with _host_lock(host):
        _pace(host)
        h = {"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, text/html, */*"}
        with _io:
            c = dict(http_cache.get(url, {}))
        if conditional and c.get("parsed"):
            if c.get("etag"): h["If-None-Match"] = c["etag"]
            if c.get("lm"): h["If-Modified-Since"] = c["lm"]
        r = requests.get(url, headers=h, timeout=25)
        return r
def remember_response(url, response):
    """Store validators only after the body has been parsed.

    A 200 that is cached before parsing, then crashes (for example a missing
    lxml parser), makes the next fetch send If-Modified-Since. The server
    answers 304 with an empty body, and an empty body is not an empty page.
    Entries written before this rule have no ``parsed`` flag and are ignored.
    """
    if response is None or getattr(response, "status_code", None) != 200:
        return
    headers = getattr(response, "headers", None) or {}
    with _io:
        http_cache[url] = {"etag": headers.get("ETag"), "lm": headers.get("Last-Modified"), "parsed": True}
PAGE_REDIRECTS = 6
_CONSENT = (("cookieconsent_status", "dismiss"), ("CookieConsent", "true"), ("consent", "accepted"))
def follow_redirects(start, fetch, limit=PAGE_REDIRECTS):
    """Follow a short redirect chain. ``fetch(url)`` returns ``(status, location, body)``.

    A repeated URL is a loop and stops the walk. Returns ``(body, error)``.
    """
    url, seen, last = start, [], ""
    for _ in range(max(1, limit)):
        status, location, body = fetch(url)
        if body and ("<html" in body[:4000].lower() or status == 200):
            last = body
        if status == 200 and body:
            return body, None
        if status in (301, 302, 303, 307, 308) and location:
            nxt = urllib.parse.urljoin(url, location)
            if nxt in seen or nxt == url:
                return last, "redirect loop"
            seen.append(url)
            url = nxt
            continue
        if status and status >= 400:
            return last, f"HTTP {status}"
        return last or body, None
    return last, "too many redirects"
def _page_fetch(sess, url):
    r = sess.get(url, timeout=25, allow_redirects=False)
    return r.status_code, r.headers.get("Location") or "", r.text or ""
def _html_session(host, consent):
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    sess.headers["Accept"] = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"
    bare = (host or "").lower().removeprefix("www.").split(":")[0]
    if consent and bare:
        for name, value in _CONSENT:
            sess.cookies.set(name, value, domain=bare, path="/")
    return sess
def read_html(url):
    """Public HTML for metadata. A redirect loop falls back to a browser read; a robots block does not.

    Article pages are followed at most PAGE_REDIRECTS times, with the cookie jar kept across hops.
    Finansavisen and similar sites loop until a consent cookie is stored, so a loop is retried once
    with that cookie before giving up.
    """
    if not robots_ok(url):
        raise RuntimeError("robots.txt disallows")
    host = urllib.parse.urlparse(url).netloc
    with _host_lock(host):
        _pace(host)
        sess = _html_session(host, consent=False)
        body, err = follow_redirects(url, lambda u: _page_fetch(sess, u))
        if err and not body:
            sess = _html_session(host, consent=True)
            body, err = follow_redirects(url, lambda u: _page_fetch(sess, u))
        if body and not err:
            return body
        if body and err == "redirect loop":
            return body
        html = pubtime.browser_html(url, UA)
        if html:
            return html
        if body:
            return body
        raise requests.TooManyRedirects(err or "too many redirects")

# ---------- keywords (NO, SE, DK, FI, IS, EN) ----------
KW = [
    # shared / English
    (r"\bbitcoin\w*", re.I), (r"\bcrypto\w*", re.I), (r"\bblockchain\w*", re.I), (r"\bstablecoin\w*", re.I),
    (r"\bNFT(?:-?\w*)?\b", 0), (r"\bMiCAR?\b", 0), (r"\bMica-\w+", 0), (r"\bethereum\b", re.I), (r"\bBTC\b", 0),
    (r"\bweb3\b", re.I), (r"\bsolana\b", re.I), (r"\bCBDC\b", 0), (r"\bsatoshi\w*", re.I), (r"\btokeni[sz]\w*", re.I),
    # Norwegian / Swedish stems
    (r"\bkrypto(?!graf)\w*", re.I), (r"\bblokkjede\w*", re.I), (r"\bblockkedj\w*", re.I), (r"\bkryptotillgång\w*", re.I),
    (r"\bsentralbankpenger\b", re.I), (r"\bdigitale penger\b", re.I), (r"\be-krona\w*", re.I),
    # Danish
    (r"\bblokkæde\w*", re.I), (r"\bkryptoaktiv\w*", re.I),
    # Finnish
    (r"\blohkoketju\w*", re.I), (r"\bvirtuaalivaluut\w*", re.I),
    # Icelandic
    (r"\brafmynt\w*", re.I), (r"\bsýndareign\w*", re.I), (r"\bsýndarf[ée]\w*", re.I), (r"\bbálkakeðj\w*", re.I),
    # explicit stems the local and justice feeds are filtered on (all Nordic languages)
    (r"\bkryptovaluta\w*", re.I), (r"\bkryptovaluutta\w*", re.I),
    (r"\bdark\s?nets?\b", re.I), (r"\bdark\s?webs?\b", re.I),
    (r"\bmørkenettet\b", re.I), (r"\bdet mørke nett\w*", re.I), (r"\bmörka nätet\b", re.I),
    (r"\bpimeä verkko\b", re.I), (r"\bmyrkur vefur\b", re.I),
    (r"\bCASPs?\b", re.I),
    # Nordic crypto companies
    (r"\bBare Bitcoin\b", re.I), (r"\bFiri\b", 0), (r"\bNBX\b", 0), (r"\bK33\b", 0), (r"\bNexa\b", 0),
    (r"\bSafello\b", 0), (r"\bVirtune\b", 0), (r"\bValuno\b", 0), (r"\bGreenMerc\b", re.I), (r"\bTrijo\b", 0),
    (r"\bCoinmotion\b", 0), (r"\bNorthcrypto\b", re.I), (r"\bKvarn X\b", 0), (r"\bMyntkaup\b", 0), (r"\bMonerium\b", 0),
    (r"\bAce Digital\b", re.I), (r"\bbitcoin[ -]treasury\b", re.I),
    # merged from Kryptonytt (2026-10-04) so Norwegian coverage is not lost
    (r"\bBitmynt\b", re.I), (r"\bH100\b", 0),
]
# Money-laundering words alone are ordinary crime news. They count only together with a crypto term.
AML_KW = [
    (r"\bhvitvask\w*", re.I), (r"\bpenningtvätt\w*", re.I), (r"\bpenningtvatt\w*", re.I),
    (r"\bhvidvask\w*", re.I), (r"\brahanpesu\w*", re.I),
    (r"\bpeningaþvætt\w*", re.I), (r"\bpeningathvaett\w*", re.I),
]
KW = [(re.compile(r, f), r) for r, f in KW]
AML_KW = [(re.compile(r, f), r) for r, f in AML_KW]
TOPICS = {
    "bitcoin": r"\bbitcoin|\bBTC\b|\bsatoshi|\butvinning|\bmining\b|\bminer|\blouhinta|\bgröftur",
    "blockchain": r"\bblokkjede|\bblockchain|\bblockkedj|\blohkoketju|\bbálkakeðj|\bNFT|\btoken|\bweb3|\bethereum|\bsolana|\bNexa\b|\bsmart ?contract",
    "crypto": r"\bkrypto(?!graf)|\bcrypto|\bstablecoin|\brafmynt|\bsýndar|\bcoin\b",
    "regulation": r"tilsyn|inspektionen|valvonta|\bMiCA|regul|regelverk|\bskatt|\bvero\b|\bverotus|forbud|förbud|\blov(?:en|forslag)?\b|\blag(?:en|förslag)?\b|\blaki\b|\blög\b|økokrim|hvitvask|hvidvask|penningtvätt|rahanpesu|peningaþvætt|dark\s?net|sanksjon|norges bank|riksbank|suomen pankki|seðlabank|central ?bank|sentralbank|\bsvindel|\bbedrägeri|\bhuijaus|\bCBDC|\bpoliti|\bpolis|\bpoliisi|\blögregl",
    "companies": r"\bFiri\b|bare bitcoin|\bK33\b|\bNBX\b|Safello|Virtune|Valuno|Coinmotion|Northcrypto|Kvarn|Myntkaup|Monerium|Ace Digital|bitcoin[ -]treasury|selskap|bolag|yhtiö|fyrirtæki|\bbørs\b|\bbörs|pörssi|oppkjøp|förvärv|emisjon|nyemission|investor|gründer|grundare|\bASA\b|\bAB\b|\bOyj?\b|\behf\b|omsetning|omsättning|liikevaihto",
}
TOPICS = {k: re.compile(v, re.I) for k, v in TOPICS.items()}
# Gambling/affiliate list pages are advertising, not news (editor ruling 2026-10-04).
GAMBLING = re.compile(r"\bcasino\w*|\bkasino\w*|\bkasinot?\b|\bspilleside\w*|\bspelsajt\w*|\bnettcasino|\bnätcasino|\bnettikasino|\bodds(?:bolag|sider)?\b|\bbetting\b|\bsportsbook|\bbonuskod\w*|\bfree ?spins?\b|\bbästa\b.*\bcasino|\bgambling\b|\bspillavhengig\w*", re.I)
# Gambling regulators: such stories are kept (real news), never dropped.
GAMBLING_REGULATOR = re.compile(r"lotteritilsyn|spelinspektion|spillemyndighed|poliisihallitus|arpajais|happdrætt|sýslumað|\bMGA\b|gaming authority|gambling authority", re.I)
def is_gambling(text, url=""): return bool(GAMBLING.search(text) or re.search(r"casino|kasino|betting", url, re.I))
def _extra_is_crypto(phrase):
    """A source match_extra unlocks an AML hit only when that extra is itself a crypto term."""
    blob = phrase or ""
    if any(c.search(blob) for c, _ in AML_KW) and not any(c.search(blob) for c, _ in KW):
        return False
    return bool(any(c.search(blob) for c, _ in KW) or re.search(
        r"krypto|crypto|bitcoin|blockchain|blokkj|blockkedj|blokkæ|lohkoket|rafmynt|mica|casp|stablecoin|cbdc|web3|ethereum|solana",
        blob, re.I))
def matches(text, extra=()):
    """Crypto terms, plus money-laundering words only when a crypto term is present too."""
    crypto = {r for c, r in KW if c.search(text)}
    extra_hits = {e for e in extra if e.lower() in (text or "").lower() and _extra_is_crypto(e)}
    aml = {r for c, r in AML_KW if c.search(text)} if (crypto or extra_hits) else set()
    plain_extra = {e for e in extra if e.lower() in (text or "").lower() and not any(c.search(e) for c, _ in AML_KW)}
    return sorted(crypto | aml | plain_extra)
def topics_of(text):
    return [k for k, c in TOPICS.items() if c.search(text)] or ["crypto"]

def clean(html):
    return re.sub(r"\s+", " ", BeautifulSoup(html or "", "lxml").get_text(" ")).strip()

# Press-ethics footers and consent banners are not the lead.
_BOILER = re.compile(
    r"vær varsom|vaer varsom|være varsom|pressens faglige utvalg|\bpfu\b|god presseskikk|"
    r"cookie|informasjonskapsler|eväste|kakor|personvern|samtykke|cookiebot|"
    r"denne nettsiden bruker|vi bruker cookies|we use cookies",
    re.I,
)
def is_boilerplate(text):
    text = (text or "").strip()
    if not text:
        return True
    return bool(_BOILER.search(text)) and len(_BOILER.sub("", text).strip()) < 40
def strip_boilerplate(text):
    """Drop a Vær Varsom / PFU / cookie footer. Keep the lead that came before it."""
    raw = text or ""
    soup = BeautifulSoup(raw, "lxml")
    paras = [clean(p.get_text(" ")) for p in soup.find_all("p")]
    if not paras:
        paras = [clean(raw)]
    kept = []
    for part in paras:
        cut = _BOILER.search(part)
        if cut and cut.start() > 40:
            part = part[:cut.start()].strip(" .–-")
        elif is_boilerplate(part) or (cut and cut.start() <= 40):
            continue
        if part and not is_boilerplate(part):
            kept.append(part)
    return " ".join(kept)[:600].strip()
def teaser_from_html(html):
    """og:description, then the article lead. Never the ethics footer or a cookie banner."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    def meta(**attrs):
        tag = soup.find("meta", attrs=attrs)
        return (tag.get("content") if tag else "") or ""
    for raw in (meta(property="og:description"), meta(name="description")):
        text = strip_boilerplate(raw)
        if text and not is_boilerplate(text):
            return text[:600]
    for sel in (".ingress", ".article-ingress", ".article__lead", ".lead", "p.standfirst", "[itemprop=description]"):
        tag = soup.select_one(sel)
        if not tag:
            continue
        text = strip_boilerplate(tag.get_text(" "))
        if text and not is_boilerplate(text):
            return text[:600]
    root = soup.find("article") or soup.find("main")
    if root:
        for p in root.find_all("p"):
            text = strip_boilerplate(p.get_text(" "))
            if len(text) < 40 or is_boilerplate(text):
                continue
            return text[:600]
    return ""
def choose_teaser(feed_teaser, page_html=None):
    """Prefer the page lead. A feed teaser is kept only after the footer is removed."""
    if page_html:
        lead = teaser_from_html(page_html)
        if lead:
            return lead
    return strip_boilerplate(feed_teaser)

_TRACK_KEYS = ("utm_", "fbclid", "gclid", "ocid", "cmpid", "srsltid")
def unwrap_news_url(url):
    """Article URL behind a Bing or Google News redirect. Other URLs pass through."""
    current = (url or "").strip()
    seen = set()
    for _ in range(4):
        if not current or current in seen:
            break
        seen.add(current)
        parsed = urllib.parse.urlparse(current)
        host = (parsed.netloc or "").lower()
        if not any(part in host for part in ("bing.com", "news.google.", "google.com")):
            break
        qs = urllib.parse.parse_qs(parsed.query)
        nxt = ""
        for key in ("url", "u", "r", "q"):
            values = qs.get(key) or qs.get(key.upper()) or []
            if values and str(values[0]).startswith("http"):
                nxt = values[0]
                break
        if not nxt:
            break
        current = nxt
    return current
def canon(url):
    url = unwrap_news_url(url)
    p = urllib.parse.urlparse((url or "").strip())
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query)
         if not k.lower().startswith(_TRACK_KEYS) and k.lower() not in ("ref", "ref_src")]
    scheme = (p.scheme or "https").lower()
    if scheme not in ("http", "https"):
        scheme = "https"
    return urllib.parse.urlunparse((scheme, p.netloc.lower().removeprefix("www."), p.path.rstrip("/") or "/", "", urllib.parse.urlencode(q), ""))
def story_key(url):
    """Key shared with coverage.index_urls. Scheme and a www prefix do not make a second story."""
    return coverage.canon(unwrap_news_url(url))
def is_duplicate(url, items):
    """True when this URL is already the primary or an extra outlet on a stored story."""
    key = story_key(url)
    if key and key in coverage.index_urls(items):
        return True
    want = iid(url)
    return any(i.get("id") == want for i in items or [])
def norm_title(t): return re.sub(r"[^\w]+", " ", t.lower()).strip()
def iid(url): return hashlib.sha1(canon(url).encode()).hexdigest()[:12]
def when(e, country=None, url=None):
    """Feed published time only. Updated/modified is not a publish time."""
    inst = pubtime.from_feed_entry(e, pubtime.zone_for(country=country, url=url))
    return inst.dt if inst else None
def pick_published(page, outlet, feed, bing=False):
    """Page clock, else the outlet's own feed, else the feed time.

    A Bing stamp is unverified unless the page or the outlet feed supplied the clock.
    Returns ``(utc datetime or None, unverified)``.
    """
    page_clock = page and not page.date_only
    outlet_clock = outlet and not outlet.date_only
    if page_clock:
        return page.dt, False
    if outlet_clock and not (page and page.date_only):
        return outlet.dt, False
    if page and page.date_only and (outlet_clock or (feed and not bing)):
        chosen = pubtime.choose_published(page, outlet or feed)
        return chosen, False
    if page and page.date_only and bing and feed:
        zone = page.zone or dt.timezone.utc
        if feed.dt.astimezone(zone).date() != page.civil_date:
            return page.dt, False
        return feed.dt, True
    if outlet_clock:
        return outlet.dt, False
    if page:
        return page.dt, False
    if feed:
        return feed.dt, bool(bing)
    return None, False
_feed_times = {}
def outlet_feed_time(url, outlet_id):
    """Publish time from the outlet's own RSS, if that feed lists this URL. Not a sitemap lastmod."""
    src = SRC.get(outlet_id) or {}
    if src.get("type") not in ("rss", "rss-all"):
        return None
    feed = src.get("feed") or ""
    if not str(feed).startswith("http") or "{q}" in feed:
        return None
    if outlet_id not in _feed_times:
        found = {}
        try:
            if robots_ok(feed):
                r = get(feed)
                if r.status_code == 304:
                    r = get(feed, conditional=False)
                if r.status_code == 200:
                    zone = pubtime.zone_for(country=src.get("country"), url=url)
                    parsed = feedparser.parse(r.content)
                    remember_response(feed, r)
                    for entry in parsed.entries:
                        link = unwrap_news_url(entry.get("link") or "")
                        inst = pubtime.from_feed_entry(entry, zone)
                        if link and inst:
                            found[coverage.canon(link)] = inst
        except Exception:
            found = {}
        _feed_times[outlet_id] = found
    return _feed_times[outlet_id].get(coverage.canon(unwrap_news_url(url)))

# ---------- source map (domain -> outlet, country) ----------
SRC = {s["id"]: s for s in CFG["sources"]}
DOMAIN2OUT = {}
for s in CFG["sources"]:
    if s.get("type") == "bing": continue
    d = urllib.parse.urlparse(s["url"]).netloc.removeprefix("www.")
    DOMAIN2OUT.setdefault(d, s.get("outlet", s["id"]))
TLD2C = {".no": "NO", ".se": "SE", ".dk": "DK", ".fi": "FI", ".is": "IS", ".fo": "FO", ".gl": "GL", ".ax": "AX"}
def country_of_url(url, fallback=None):
    d = urllib.parse.urlparse(url).netloc.lower()
    return next((c for t, c in TLD2C.items() if d.endswith(t)), fallback)
def outlet_for(url, fallback_name=None):
    """Source id and name for an article URL.

    A section path (Aamuposti's /aihe/Nurmijärvi) does not claim the whole host.
    The longest matching path on an enabled source wins. The site root is the fallback on that host.
    """
    parsed = urllib.parse.urlparse(unwrap_news_url(url or ""))
    host = (parsed.netloc or "").lower().removeprefix("www.")
    path = parsed.path or "/"
    best, best_score = None, -1
    for s in CFG["sources"]:
        if s.get("type") == "bing" or not s.get("enabled") or not s.get("url"):
            continue
        sp = urllib.parse.urlparse(s["url"])
        shost = (sp.netloc or "").lower().removeprefix("www.")
        if not shost or not (host == shost or host.endswith("." + shost)):
            continue
        spath = sp.path or "/"
        if spath not in ("", "/"):
            base = spath.rstrip("/")
            if path != base and not path.startswith(base + "/"):
                continue
            score = len(base)
        else:
            score = 0
        if score > best_score:
            best, best_score = s, score
    if not best:
        return host, fallback_name or host
    out = best.get("outlet") or best["id"]
    src = SRC.get(out) or best
    name = (src.get("name") or fallback_name or out).split(" (")[0]
    return out, name
def named_outlet(url, source, fallback_name=None):
    """Outlet id and display name for an article. The feed's own source is used when the URL maps nowhere."""
    fallback = fallback_name or (source.get("name") or "").split(" (")[0]
    out, oname = outlet_for(url, fallback)
    if out not in SRC:
        out = source.get("outlet", source["id"])
        oname = (SRC.get(out, source).get("name") or fallback).split(" (")[0]
    return out, oname
LANG = {"NO": "Norwegian", "SE": "Swedish", "DK": "Danish", "FI": "Finnish", "IS": "Icelandic", "FO": "Faroese", "GL": "Greenlandic", "AX": "Swedish"}

# ---------- candidate entities for the queue (never auto-published) ----------
KNOWN = ["Firi", "Bare Bitcoin", "K33", "NBX", "Norwegian Block Exchange", "Týr Markets", "Kaupr", "Nexa", "Seetee",
 "Finanstilsynet", "Norges Bank", "Skatteetaten", "Økokrim", "Safello", "Virtune", "Valuno", "GreenMerc", "Trijo", "Goobit",
 "BTCX", "Finansinspektionen", "Riksbanken", "Skatteverket", "Finanspolisen", "Svenska Bitcoinföreningen",
 "Coinmotion", "Northcrypto", "Kvarn", "Tesseract", "Bittimaatti", "Paxos", "Finanssivalvonta", "Suomen Pankki", "Verohallinto",
 "Myntkaup", "Monerium", "Seðlabanki", "Skatturinn", "Danmarks Nationalbank", "Nationalbanken", "Skattestyrelsen", "Erhvervsministeriet", "Coinify", "Nordic Blockchain Association",
 "Coinbase", "Binance", "Kraken", "Bitpanda", "Revolut", "Nordnet", "Avanza", "DNB", "Nordea", "SEB", "Swedbank", "Handelsbanken", "OP"]
ROLE = r"(?:daglig leder|administrerende direktør|toppsjef|gründer|medgründer|grunnlegger|styreleder|direktør|sentralbanksjef|finansminister|vd|grundare|styrelseordförande|generaldirektör|riksbankschef|toimitusjohtaja|perustaja|hallituksen puheenjohtaja|pääjohtaja|framkvæmdastjóri|seðlabankastjóri|stjórnarformaður|CEO|founder|co-founder|chair(?:man|person)?|governor|director general)"
NAME = r"[A-ZÆØÅÄÖÞÐ][a-zæøåäöüéðþáíóúý]+(?:[- ][A-ZÆØÅÄÖÞÐ][a-zæøåäöüéðþáíóúý\.]+){1,3}"
PAT = [re.compile(rf"(?P<role>{ROLE}) (?:i|for|hos|på|ved|of|at|för) (?P<org>[A-ZÆØÅÄÖ0-9][\w\.&-]*(?: [A-ZÆØÅÄÖ0-9][\w\.&-]*){{0,3}}),? (?P<name>{NAME})"),
       re.compile(rf"(?P<name>{NAME}),? (?:er |är |is |on )?(?P<role>{ROLE}) (?:i|for|hos|på|ved|of|at|för) (?P<org>[A-ZÆØÅÄÖ0-9][\w\.&-]*(?: [A-ZÆØÅÄÖ0-9][\w\.&-]*){{0,3}})")]
def candidates(text):
    out = []
    for o in KNOWN:
        if re.search(rf"\b{re.escape(o)}\b", text): out.append({"kind": "organisation", "name": o})
    for p in PAT:
        for m in p.finditer(text):
            g = m.groupdict(); out.append({"kind": "person", "name": g["name"].strip(" ."), "role": g["role"], "org": g["org"].strip(" .,")})
    return out

EN_MONTHS = {m: i for i, m in enumerate(["January","February","March","April","May","June","July","August","September","October","November","December"], 1)}
def page_meta(url):
    """Public metadata only (title, description, publish time). Article text is not stored.
    og:image is seen and dropped. The picture URL is not returned."""
    html = read_html(url); soup = BeautifulSoup(html, "lxml")
    m = lambda **k: (soup.find("meta", attrs=k) or {}).get("content")
    title = m(property="og:title") or (soup.title.string if soup.title else "") or ""
    desc = teaser_from_html(html)
    note_og_image(m(property="og:image"))
    zone = pubtime.zone_for(url=url)
    inst = pubtime.published_from_soup(soup, zone)
    date = inst.dt if inst else None
    if not date:
        # Last resort for official pages that publish neither the three signals nor a feed.
        iso = m(name="DC.date") or m(name="dcterms.date") or m(name="date")
        if iso and not re.search(r"modif", iso, re.I):
            legacy = pubtime.parse_instant(iso, zone)
            date = legacy.dt if legacy else None
    if not date:
        t = soup.get_text(" ", strip=True)
        main = soup.find("main") or soup.find("article")
        lab = re.search(r"(?:News release|Press release|Release|Published|Tiedote|Lehdistötiedote|Pressmeddelande|Publicerad|Fréttatilkynning)\s*:?\s*(\d{1,2}\.?\s*\w+\.?\s*20\d\d|\d{1,2}\.\d{1,2}\.20\d\d)", t)
        if lab: t = lab.group(1) + " " + t
        elif main: t = main.get_text(" ", strip=True) + " " + t
        x = re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2}), (20\d\d)", t) \
            or re.search(r"\b(\d{1,2}) (January|February|March|April|May|June|July|August|September|October|November|December) (20\d\d)", t)
        if x:
            g = x.groups(); mon, day = (g[0], g[1]) if g[0] in EN_MONTHS else (g[1], g[0])
            date = dt.datetime(int(g[2]), EN_MONTHS[mon], int(day), 12, tzinfo=dt.timezone.utc)
        else:
            x = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(20\d\d)\b", t)
            if x: date = dt.datetime(int(x[3]), int(x[2]), int(x[1]), 12, tzinfo=dt.timezone.utc)
    if date and date.tzinfo is None: date = date.replace(tzinfo=dt.timezone.utc)
    if date: date = dt.datetime.fromisoformat(pubtime.utc_iso(date))
    return clean(title), clean(desc), date

def html_story_links(html, base, pattern):
    """Story links in the order the page lists them. Duplicates are dropped once."""
    soup = BeautifulSoup(html or "", "lxml")
    rx = re.compile(pattern or "")
    out, seen = [], set()
    for tag in soup.find_all("a", href=True):
        href = tag.get("href") or ""
        if not rx.search(href):
            continue
        url = urllib.parse.urljoin(base, href).split("#")[0]
        if not url.startswith("http") or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out
def fresh_html_links(links, seen, limit):
    """Drop links already opened, then keep at most ``limit`` in that same order.

    The cap used to run on an alphabetical sort before the seen-filter, so a
    new story past the first 30 names was never opened.
    """
    fresh = []
    seen = set(seen or ())
    for url in links or []:
        if url in seen:
            continue
        fresh.append(url)
        if limit is not None and len(fresh) >= limit:
            break
    return fresh
def read_html_links(url, pattern, saved):
    """Return ``(links, error)``.

    A 304 keeps the last parsed link list. A 304 with no saved list is fetched
    again without validators, so an empty 304 body is not stored as zero links.
    Validators are stored only after the HTML parses.
    """
    r = get(url)
    if r.status_code == 304 and not saved:
        r = get(url, conditional=False)
    if r.status_code == 304:
        return list(saved or []), None
    if r.status_code != 200:
        return [], f"HTTP {r.status_code}"
    links = html_story_links(r.text or "", url, pattern)
    remember_response(url, r)
    return links, None
_DOK8_DATA = re.compile(r"\bdatasentr\w*|\bdata-?cent(?:er|re)s?\b", re.I)
_DOK8_MINING = re.compile(r"\bmining\b|\bcrypto-?mining\b|\bkrypto-?utvinning\w*|\butvinning av krypto\w*", re.I)
_NO_MONTHS = {n: i for i, n in enumerate(
    ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august", "september", "oktober", "november", "desember"], 1)}
def storting_sessions(now, days):
    """Storting session ids that can overlap the look-back window.

    A session is ``YYYY-(YYYY+1)`` and opens in October. The previous session
    is included when the window starts before 1 October.
    """
    now = now if getattr(now, "tzinfo", None) else now.replace(tzinfo=dt.timezone.utc)
    year = now.year if now.month >= 10 else now.year - 1
    sessions = [f"{year}-{year + 1}"]
    cutoff = now - dt.timedelta(days=max(0, int(days)))
    if cutoff < dt.datetime(year, 10, 1, tzinfo=dt.timezone.utc):
        prev = year - 1
        sessions.append(f"{prev}-{prev + 1}")
    return sessions
def dok8_list_url(feed, session):
    """Open-data list for one session. ``sesjonid`` in the stored feed is replaced."""
    base = feed or "https://data.stortinget.no/eksport/publikasjoner?publikasjontype=dok8&format=json"
    parsed = urllib.parse.urlparse(base)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True) if k.lower() != "sesjonid"]
    if not any(k.lower() == "publikasjontype" for k, _ in query):
        query.append(("publikasjontype", "dok8"))
    if not any(k.lower() == "format" for k, _ in query):
        query.append(("format", "json"))
    query.append(("sesjonid", session))
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))
def dok8_url(session, pid):
    return f"https://www.stortinget.no/no/Saker-og-publikasjoner/Publikasjoner/Representantforslag/{session}/{pid}/"
def parse_dotnet_date(value):
    """ASP.NET ``/Date(ms)/``. The year-1 sentinel (``dato`` on the list) is not a date."""
    m = re.search(r"/Date\((-?\d+)", str(value or ""))
    if not m:
        return None
    ms = int(m.group(1))
    if ms < 0:
        return None
    when = dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc)
    if when.year < 1990:
        return None
    return when
def parse_no_date(text):
    """``5. oktober 2026`` as noon UTC. There is no clock time on the document."""
    m = re.search(r"\b(\d{1,2})\.?\s+([A-Za-zæøåÆØÅ]+)\s+(20\d\d)\b", text or "")
    if not m:
        return None
    mon = _NO_MONTHS.get(m.group(2).lower().replace("é", "e"))
    if not mon:
        return None
    try:
        return dt.datetime(int(m.group(3)), mon, int(m.group(1)), 12, tzinfo=dt.timezone.utc)
    except ValueError:
        return None
def _xml_text(block):
    text = re.sub(r"<[^>]+>", " ", block or "")
    return re.sub(r"\s+", " ", text).strip()
def dok8_title(ingress):
    """Short title. The list only says ``Dokument 8:9 S``."""
    text = re.sub(r"\s+", " ", ingress or "").strip()
    m = re.search(r".*\bom\s+(.+)$", text, re.I)
    if m and text.lower().startswith("representantforslag"):
        return "Representantforslag om " + m.group(1).strip(" .")
    return text[:180]
def dok8_hits(text):
    """Crypto terms, plus data centres and mining. Used only for dok8 proposals.

    ``miner`` as a substring matches ``mineralske`` and is not used.
    Data-centre wording is not a global news keyword.
    """
    blob = text or ""
    hits = matches(blob)
    if _DOK8_DATA.search(blob) and "datasenter" not in hits:
        hits.append("datasenter")
    if _DOK8_MINING.search(blob) and "mining" not in hits:
        hits.append("mining")
    return hits
def parse_dok8_list(payload):
    data = json.loads(payload) if isinstance(payload, str) else (payload or {})
    rows = []
    for item in data.get("publikasjoner_liste") or []:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        rows.append({
            "id": item.get("id"),
            "available": parse_dotnet_date(item.get("tilgjengelig_dato")),
            "listed_date": parse_dotnet_date(item.get("dato")),
        })
    return rows
def dok8_due(rows, cutoff, slack_days=21, limit=40):
    """Proposals that might fall inside the look-back window.

    ``tilgjengelig_dato`` is when the file appeared in the export, not the
    printed date, so the window is widened. A missing availability date is kept.
    """
    floor = cutoff - dt.timedelta(days=slack_days)
    kept = []
    for row in rows or []:
        avail = row.get("available")
        if avail is not None and avail < floor:
            continue
        kept.append(row)
    kept.sort(key=lambda row: row.get("available") or dt.datetime.max.replace(tzinfo=dt.timezone.utc), reverse=True)
    return kept[:limit]
def parse_dok8_publication(xml):
    """Title, teaser, date and match terms. The publication body is not returned."""
    raw = xml or ""
    date_m = re.search(r"<Dato>(.*?)</Dato>", raw, re.S)
    ing_m = re.search(r"<Ingress>(.*?)</Ingress>", raw, re.S)
    ingress = _xml_text(ing_m.group(1) if ing_m else "")
    body = _xml_text(raw)
    hits = dok8_hits(body)
    return {
        "title": dok8_title(ingress),
        "teaser": ingress[:500],
        "published": parse_no_date(_xml_text(date_m.group(1) if date_m else "")),
        "hits": hits,
        "topics": topics_of(body) if hits else [],
        "relevant": bool(hits),
    }
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--only", help="comma-separated source ids")
    ap.add_argument("--add", metavar="URL", help="add one story manually (researcher): reads title/date from the page metadata")
    ap.add_argument("--source-name", help="source name for --add (otherwise from sources.json or the domain)")
    ap.add_argument("--country", help="country code for --add (NO, SE, DK, FI, IS) if not clear from the domain")
    ap.add_argument("--date", help="publication date for --add (YYYY-MM-DD) if the page does not give one")
    ap.add_argument("--title", help="title for --add if the page does not give one")
    ap.add_argument("--no-events", action="store_true", help="skip the event search"); a = ap.parse_args()
    cutoff = NOW - dt.timedelta(days=a.days)
    news = load(P("data", "news.json"), {"items": []})
    teasers = load(P("state", "teasers.json"), {})
    queue = load(P("queue", "review.json"), {"items_needing_summary": [], "candidate_entities": []})
    org = load(P("data", "orgchart.json"), {"entities": [], "relations": []})
    known_names = {e["name"].lower() for e in org["entities"]}
    by_url = coverage.index_urls(news["items"])
    by_title = {norm_title(i["title"]): i for i in news["items"]}
    status = load(P("state", "source_status.json"), {})
    new = []

    def add(url, title, teaser, published, src, outlet, outlet_name, country, extra=(), all_rel=False, lang=None, unverified=False, extra_hits=(), topics=None):
        if isinstance(published, dt.datetime):
            published = dt.datetime.fromisoformat(pubtime.utc_iso(published))
        with _io:
            _add(url, title, teaser, published, src, outlet, outlet_name, country, extra, all_rel, lang, unverified, extra_hits, topics)
    def _add(url, title, teaser, published, src, outlet, outlet_name, country, extra=(), all_rel=False, lang=None, unverified=False, extra_hits=(), topics=None):
        url = canon(url)
        cu = story_key(url)
        ex = by_url.get(cu)
        if ex is None:
            want = iid(url)
            ex = next((i for i in news["items"] if i.get("id") == want), None)
        if ex is not None:
            if src not in ex.setdefault("seen_via", []): ex["seen_via"].append(src)
            by_url[cu] = ex
            return
        text = f"{title}. {teaser}"
        hits = matches(text, extra)
        for hit in extra_hits or ():
            if hit not in hits:
                hits.append(hit)
        if not hits and not all_rel: return
        if is_gambling(text, url):
            if not GAMBLING_REGULATOR.search(text):
                with open(P("state", "dropped_gambling.jsonl"), "a") as fh:
                    fh.write(json.dumps({"dropped_at": NOW.isoformat(timespec="seconds"), "url": url, "title": title, "source": src, "country": country}, ensure_ascii=False) + "\n")
                return
        if not title or not published or published < cutoff: return
        cand = {"url": url, "title": title, "published": published.isoformat(), "text": f"{title}. {teaser}"}
        match, why = coverage.find_match(cand, news["items"], teasers)
        if match:
            rec = coverage.record_from_parts(outlet, outlet_name, url, title, published, lang or LANG.get(country), country,
                                             paywall=bool(SRC.get(outlet, {}).get("paywall", False)))
            if coverage.attach(match, rec):
                note = {"url": url, "title": title, "outlet": outlet, "outlet_name": outlet_name,
                        "attached_to": match.get("id"), "reason": why, "at": NOW.isoformat(timespec="seconds")}
                got = queue.setdefault("coverage_attached", [])
                got[:] = [n for n in got if coverage.canon(n.get("url")) != cu] + [note]
                log(f"ATTACHED {outlet_name} to {match.get('id')} ({why}): {title[:80]}")
            by_url[cu] = match
            return
        it = {"id": iid(url), "url": url, "title": title, "title_en": None, "source": outlet, "source_name": outlet_name,
              "country": country, "language": lang or LANG.get(country), "via": src, "seen_via": [src],
              "published": published.isoformat(), "fetched": NOW.isoformat(timespec="seconds"),
              "topics": list(topics) if topics is not None else topics_of(text), "matched": sorted(set(hits)), "paywall": bool(SRC.get(outlet, {}).get("paywall", False)),
              "status": "pending", "summary": None}
        if unverified: it["published_unverified"] = True
        strip_press_images(it)
        news["items"].append(it); by_url[cu] = it; by_title[norm_title(title)] = it
        teasers[it["id"]] = teaser[:600]; new.append(it)

    if a.add:
        title, desc, date = page_meta(a.add)
        if a.title: title = a.title
        if a.date: date = dt.datetime.fromisoformat(a.date).replace(hour=12, tzinfo=dt.timezone.utc)
        if not date: sys.exit("no date found on the page; use --date YYYY-MM-DD")
        out, oname = outlet_for(a.add, a.source_name or urllib.parse.urlparse(a.add).netloc.removeprefix("www."))
        if a.source_name: oname = a.source_name
        c = a.country or country_of_url(a.add, SRC.get(out, {}).get("country"))
        if not c: sys.exit("could not tell the country from the domain; use --country NO|SE|DK|FI|IS")
        before = len(new)
        add(a.add, title, desc, date, "manual", out, oname, c, all_rel=True)
        log(("ADDED: " if len(new) > before else "ALREADY THERE / OUTSIDE PERIOD (--days): ") + f"{title} ({date.date()}, {oname}, {c})")
        a.only = "__none__"
    def resolve_published(url, title, teaser, entry, country, extra, all_rel, bing=False, outlet_id=None):
        """Page publish time, else the outlet's own feed, else the feed date.

        Bing's pubDate is Pacific time mislabelled GMT. It is used only when the page
        and the outlet feed are missing, and then marked unverified. Returns
        ``(datetime or None, unverified, html or None)``.
        """
        zone = pubtime.zone_for(country=country, url=url)
        feed = pubtime.bing_instant(entry) if bing else pubtime.from_feed_entry(entry, zone)
        feed_dt = feed.dt if feed else None
        html = None
        text = f"{title}. {teaser}"
        def finish(page, outlet_inst):
            chosen, unverified = pick_published(page, outlet_inst, feed, bing=bing)
            if page and feed_dt and chosen and abs((chosen - feed_dt).total_seconds()) >= 1:
                log(f"DATE {pubtime.utc_iso(feed_dt)} -> {pubtime.utc_iso(chosen)} ({page.source}) {url[:90]}")
            elif bing and unverified and chosen:
                log(f"DATE unverified {pubtime.utc_iso(chosen)} (Bing Pacific, page unread) {url[:90]}")
            return chosen, unverified, html
        if not url or (not matches(text, extra) and not all_rel):
            return finish(None, None)
        if is_gambling(text, url) and not GAMBLING_REGULATOR.search(text):
            return finish(None, None)
        if feed_dt and feed_dt < cutoff - dt.timedelta(days=2):
            return finish(None, None)
        page = None
        try:
            if robots_ok(url):
                html = read_html(url)
                page = pubtime.published_from_html(html, zone)
        except Exception as ex:
            log("DATE", type(ex).__name__, str(ex)[:80], url[:100])
        outlet_inst = None
        if bing and not (page and not page.date_only):
            mapped = outlet_id if outlet_id in SRC else None
            if not mapped:
                guessed, _name = outlet_for(url)
                mapped = guessed if guessed in SRC else None
            if mapped and mapped != (entry or {}).get("_skip_outlet"):
                outlet_inst = outlet_feed_time(url, mapped)
        return finish(page, outlet_inst)

    seen_html = load(P("state", "html_seen.json"), {})
    html_lists = load(P("state", "html_lists.json"), {})
    def ingest(s):
        """One source. Any failure is stored on that source and does not stop the others."""
        err = guarded_call(lambda: _ingest(s))
        if err:
            log("ERR", s.get("id"), err)
            with _io:
                status[s["id"]] = {"checked": NOW.isoformat(timespec="seconds"), "ok": False, "requests": 0, "ok_requests": 0, "entries": 0, "error": err}
    def _ingest_listing(s):
        """Sitemap, then a public index page. Title, date, URL and summary only."""
        n_ok = n_items = 0
        err = None
        method = s.get("method") or "sitemap"
        try:
            remembered = []
            def http_get(url):
                r = get(url)
                if r.status_code == 304:
                    r = get(url, conditional=False)
                if r.status_code == 200:
                    remembered.append((url, r))
                    return 200, r.text or ""
                return r.status_code, ""
            entries, used, err = listing.collect(
                s.get("url") or s.get("feed") or "", http_get, robots_ok,
                limit=max(8, s.get("max_new_per_run", 8) * 3),
                zone=pubtime.zone_for(country=s.get("country"), url=s.get("url")),
            )
            if entries:
                for got_url, got in remembered:
                    remember_response(got_url, got)
            if used:
                method = used
            cap = s.get("max_new_per_run", 8)
            fetched = 0
            for e in entries:
                pub = e.get("published")
                if pub and pub < cutoff:
                    continue
                title = e.get("title") or ""
                raw_summary = e.get("summary") or ""
                summary = strip_boilerplate(raw_summary)
                if title and not matches(f"{title}. {summary}") and not s.get("all_relevant"):
                    continue
                # A Vær Varsom / cookie footer is not the lead. Read the page for og:description.
                want_lead = bool(raw_summary) and (is_boilerplate(raw_summary) or not summary)
                if (not title or not pub or want_lead) and fetched < cap:
                    fetched += 1
                    t, d, date = page_meta(e["url"])
                    title = title or t
                    summary = d or summary
                    pub = pub or date
                if not title:
                    continue
                n_items += 1
                out, oname = named_outlet(e["url"], s)
                add(e["url"], title, summary, pub, s["id"], out, oname, s["country"], s.get("match_extra", ()), all_rel=s.get("all_relevant", False), lang=s.get("language"))
            n_ok = 1 if entries else 0
        except Exception as ex:
            err = f"{type(ex).__name__}: {ex}"[:200]
            log("ERR", s["id"], err)
        with _io:
            status[s["id"]] = {"checked": NOW.isoformat(timespec="seconds"), "ok": n_ok > 0, "requests": 1,
                               "ok_requests": n_ok, "entries": n_items, "error": err, "method": method}
        log(f"{s['id']:<22} {method} entries={n_items} err={err}")

    def _ingest_dok8(s):
        """Storting representative proposals. The list has no publication date.

        ``dato`` is a year-1 sentinel. The printed date and the wording used
        for matching come from each publication. The body is not stored.
        """
        n_ok = n_items = 0
        err = None
        try:
            for session in storting_sessions(NOW, a.days):
                list_url = dok8_list_url(s.get("feed"), session)
                if not robots_ok(list_url):
                    err = "robots.txt disallows"
                    continue
                with _io:
                    saved = list(html_lists.get(list_url) or [])
                r = get(list_url)
                if r.status_code == 304 and not saved:
                    r = get(list_url, conditional=False)
                if r.status_code == 304:
                    n_ok += 1
                    n_items += len(saved)
                    continue
                if r.status_code != 200:
                    err = f"HTTP {r.status_code}"
                    continue
                due = dok8_due(parse_dok8_list(r.text), cutoff)
                relevant = []
                for row in due:
                    pid = row.get("id") or ""
                    page = dok8_url(session, pid)
                    with _io:
                        known = story_key(page) in by_url
                    if known:
                        relevant.append(page)
                        continue
                    pub_url = "https://data.stortinget.no/eksport/publikasjon?publikasjonid=" + urllib.parse.quote(pid) + "&format=xml"
                    if not robots_ok(pub_url):
                        continue
                    pr = get(pub_url, conditional=False)
                    if pr.status_code != 200 or not pr.text:
                        continue
                    doc = parse_dok8_publication(pr.text)
                    if not doc["relevant"] or not doc["published"] or doc["published"] < cutoff:
                        continue
                    relevant.append(page)
                    add(page, doc["title"], doc["teaser"], doc["published"], s["id"], s["id"], s.get("name") or "Stortinget",
                        s.get("country") or "NO", lang=s.get("language"), extra_hits=doc["hits"], topics=doc["topics"])
                remember_response(list_url, r)
                with _io:
                    html_lists[list_url] = relevant
                n_ok += 1
                n_items += len(relevant)
        except Exception as ex:
            err = f"{type(ex).__name__}: {ex}"[:200]
            log("ERR", s["id"], err)
        with _io:
            status[s["id"]] = {"checked": NOW.isoformat(timespec="seconds"), "ok": n_ok > 0, "requests": n_ok,
                               "ok_requests": n_ok, "entries": n_items, "error": err, "method": "html"}
        log(f"{s['id']:<22} dok8 entries={n_items} err={err}")

    def _ingest(s):
        if s.get("type") == "dok8":
            _ingest_dok8(s)
            return
        if s.get("type") == "sitemap" or (s.get("method") == "sitemap" and not s.get("link_pattern")):
            _ingest_listing(s)
            return
        if s["type"] == "html" and not s.get("link_pattern"):
            _ingest_listing(s)
            return
        if s["type"] == "html":
            n_ok = 0; n_meta = 0; err = None; links = []
            try:
                if not robots_ok(s["feed"]):
                    err = "robots.txt disallows"
                else:
                    with _io:
                        saved = list(html_lists.get(s["feed"]) or [])
                    links, err = read_html_links(s["feed"], s.get("link_pattern") or "", saved)
                    if not links and not err and saved:
                        links = saved
                    if links or not err:
                        n_ok = 1
                    if links:
                        with _io:
                            html_lists[s["feed"]] = list(links)
                cap = s.get("max_new_per_run", 40)
                with _io:
                    seen = set(seen_html)
                for u in fresh_html_links(links, seen, cap):
                    with _io:
                        if u in seen_html:
                            continue  # another Kaupr section already opened it
                    n_meta += 1
                    t, d, date = page_meta(u)
                    with _io:
                        seen_html[u] = {"title": t, "date": date.isoformat() if date else None}
                    out, oname = named_outlet(u, s)
                    add(u, t, d, date, s["id"], out, oname, s["country"], s.get("match_extra", ()), all_rel=s.get("all_relevant", False), lang=s.get("language"))
            except Exception as ex: err = f"{type(ex).__name__}: {ex}"[:200]; log("ERR", s["id"], err)
            with _io:
                status[s["id"]] = {"checked": NOW.isoformat(timespec="seconds"), "ok": n_ok > 0, "requests": 1 + n_meta, "ok_requests": n_ok, "entries": len(links), "error": err, "method": "html"}
            log(f"{s['id']:<22} html links={len(links)} err={err}"); return
        urls = ([s["feed"].format(q=urllib.parse.quote(q)) for q in s.get("queries", [])]
                + [s["feed"].format(q=urllib.parse.quote(f"{t} site:{site}")) for site in s.get("sites", []) for t in s.get("site_terms", [])]) if s["type"] == "bing" else [s["feed"]]  # sites x site_terms: Kryptonytt's per-site search (bing-no-kn)
        n_ok = n_items = 0; err = None
        for u in urls:
            if not robots_ok(u): err = "robots.txt disallows"; log("SKIP robots", s["id"], u); continue
            try:
                r = get(u)
                if r.status_code == 304: n_ok += 1; continue
                if r.status_code != 200: err = f"HTTP {r.status_code}"; continue
                f = feedparser.parse(r.content)
                remember_response(u, r)
                n_ok += 1; n_items += len(f.entries)
                for e in f.entries:
                    entry_carries_article_image(e)  # media:content / enclosure: counted, URL not stored
                    link = unwrap_news_url(e.get("link") or "")
                    title = clean(e.get("title"))
                    teaser = clean(e.get("summary") or e.get("description") or "")
                    bing = s["type"] == "bing"
                    if bing:
                        host = urllib.parse.urlparse(link).netloc.lower()
                        if not host.endswith(s["allowed_tld"]): continue
                        out, oname = outlet_for(link, (e.get("news_source") or "").strip())
                        if out not in SRC:
                            out = host.removeprefix("www.")
                        extra, all_rel, lang = (), False, None
                    else:
                        out, oname = named_outlet(link, s)
                        extra, all_rel, lang = s.get("match_extra", ()), s["type"] == "rss-all", s.get("language")
                    published, unverified, html = resolve_published(
                        link, title, teaser, e, s["country"], extra, all_rel, bing=bing, outlet_id=out if out in SRC else None)
                    teaser = choose_teaser(teaser, html)
                    add(link, title, teaser, published, s["id"], out, oname, s["country"], extra, all_rel, lang, unverified=unverified)
            except Exception as ex:
                err = f"{type(ex).__name__}: {ex}"[:200]; log("ERR", s["id"], u, err)
        with _io:
            status[s["id"]] = {"checked": NOW.isoformat(timespec="seconds"), "ok": n_ok > 0, "requests": len(urls),
                               "ok_requests": n_ok, "entries": n_items, "error": err, "method": "rss"}
        log(f"{s['id']:<22} ok={n_ok}/{len(urls)} entries={n_items} err={err}")

    selected = [s for s in CFG["sources"] if s.get("enabled") and s.get("feed") and (not a.only or s["id"] in set(a.only.split(",")))]
    workers = max(1, int(CFG.get("fetch_workers") or 6))
    log(f"fetching {len(selected)} feeds with {workers} workers, {DELAY}s per host")
    if workers == 1 or len(selected) <= 1:
        for s in selected: ingest(s)
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for fut in as_completed([ex.submit(ingest, s) for s in selected]):
                fut.result()

    # queue: stories without an editorial summary + candidate entities
    pend = {q["id"]: q for q in queue["items_needing_summary"]}
    for it in news["items"]:
        if it["status"] == "pending" and it["id"] not in pend:
            row = {"id": it["id"], "country": it.get("country"), "language": it.get("language"),
                "title": it["title"], "source": it["source_name"], "url": it["url"], "published": it["published"],
                "teaser_local_only": teasers.get(it["id"], "")}
            prev = pend.get(it["id"]) or {}
            if prev.get("duplicate_of"): row["duplicate_of"] = prev["duplicate_of"]
            queue["items_needing_summary"].append(row)
    queue["items_needing_summary"] = [q for q in queue["items_needing_summary"]
        if any(i["id"] == q["id"] and i["status"] == "pending" for i in news["items"])]
    seen_c = {(c["name"].lower(), c.get("item_id")) for c in queue["candidate_entities"]}
    for it in new:
        for c in candidates(f"{it['title']}. {teasers.get(it['id'], '')}"):
            if c["name"].lower() in known_names or (c["name"].lower(), it["id"]) in seen_c: continue
            c.update({"item_id": it["id"], "url": it["url"], "source": it["source_name"], "country": it.get("country"), "status": "new"})
            queue["candidate_entities"].append(c); seen_c.add((c["name"].lower(), it["id"]))
    queue["updated"] = NOW.isoformat(timespec="seconds")
    queue["_how_to"] = ("Editor: for each story in items_needing_summary, add an entry to queue/approved.json -> items with the url, "
        "a 2–4 sentence summary IN ENGLISH in our own words of what the story says (never copied or machine-copied text; not only a one-line intro), an optional title_en, and topics; "
        "or add it to rejected if it is not about crypto in NO/SE/DK/FI/IS. teaser_local_only is working material and is never published. "
        "Same event, another outlet: set duplicate_of to the existing story id or URL on this queue row (or on the approved.json item, with no summary). "
        "The next build adds it to also_covered_by on that story and does not publish a second story. "
        "A new article is attached on its own when the headline matches, the title is close within three days, or two known organisations appear in both texts (see coverage_attached). "
        "Candidate entities: add confirmed ones to data/orgchart_nordic.json with a source link, then set status accepted/rejected here. "
        "Events: see events_pending. Then run ./build.sh (local) – publishing needs jQrgen's OK.")
    n_stripped = 0
    for it in news["items"]:
        n_stripped += len(strip_press_images(it))
    if n_stripped or ignored_count():
        log(f"article images ignored: {ignored_count()} seen in feeds or pages, {n_stripped} fields removed from news rows (URLs not stored)")
    news["items"].sort(key=lambda i: i["published"], reverse=True); news["updated"] = NOW.isoformat(timespec="seconds")
    save(P("data", "news.json"), news); save(P("state", "teasers.json"), teasers); save(P("queue", "review.json"), queue)
    save(P("state", "source_status.json"), status); save(P("state", "http_cache.json"), http_cache); save(P("state", "html_seen.json"), seen_html); save(P("state", "html_lists.json"), html_lists)
    by_c = {}
    for i in new: by_c[i["country"]] = by_c.get(i["country"], 0) + 1
    log(f"DONE: {len(new)} new stories {by_c}, {len(news['items'])} total, "
        f"{len(queue['items_needing_summary'])} awaiting an English summary, "
        f"{sum(1 for c in queue['candidate_entities'] if c['status']=='new')} new candidate entities in queue/review.json")

def event_sources(cfg):
    """Event sources for this run, with predatory conference listings removed."""
    kept = []
    for src in (cfg or {}).get("event_sources") or []:
        if event_block.blocked_source(src):
            log(f"event source {src.get('id', '?')} blocked predatory conference listing")
            continue
        kept.append(src)
    return kept

if __name__ == "__main__":
    main()
    if "--add" not in sys.argv and "--no-events" not in sys.argv:  # events are searched in every run
        import events
        events.run(get, robots_ok, lambda t: bool(matches(t)), log, dict(CFG, event_sources=event_sources(CFG)))
