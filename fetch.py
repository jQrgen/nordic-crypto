#!/usr/bin/env python3
"""Nordic Crypto – fetches feeds and public list pages for Norway, Sweden, Denmark, Finland and Iceland,
filters on crypto keywords (Norwegian, Swedish, Danish, Finnish, Icelandic, English), de-duplicates and updates
data/news.json and the editor queue queue/review.json. Events are searched in the same run (events.py).

  .venv/bin/python fetch.py            # normal daily run (looks 7 days back)
  .venv/bin/python fetch.py --days 30  # first run / look-back

New items get status "pending" and are NOT published until the editor has written a summary in English
in our own words (queue/approved.json) – see README.md. The front page needs two to four sentences of what the story says; a one-sentence intro is not enough. The feed teaser is stored only locally in
state/teasers.json as working material for the editor and is never published. Article text is never fetched
(we respect paywalls and robots.txt). Article pictures are never stored either:
og:image, RSS media:content, media:thumbnail and image enclosures are ignored.
See tools/press_images.py and docs/image-policy.md.
"""
import argparse, datetime as dt, hashlib, json, os, re, sys, time, urllib.parse, urllib.robotparser
import requests, feedparser
from bs4 import BeautifulSoup
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
import coverage
import event_block
from tools.press_images import entry_carries_article_image, ignored_count, note_og_image, strip_press_images

ROOT = os.path.dirname(os.path.abspath(__file__))
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
    s = " ".join(str(x) for x in a); print(s, flush=True); LOG.write(s + "\n"); LOG.flush()

# ---------- polite HTTP: robots.txt, per-host rate limit, ETag cache ----------
_robots, _last = {}, {}
http_cache = load(P("state", "http_cache.json"), {})
def robots_ok(url):
    p = urllib.parse.urlparse(url); base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers={"User-Agent": UA}, timeout=15)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception: rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch(UA, url)
def get(url):
    host = urllib.parse.urlparse(url).netloc
    wait = DELAY - (time.time() - _last.get(host, 0))
    if wait > 0: time.sleep(wait)
    h = {"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, text/html, */*"}
    c = http_cache.get(url, {})
    if c.get("etag"): h["If-None-Match"] = c["etag"]
    if c.get("lm"): h["If-Modified-Since"] = c["lm"]
    r = requests.get(url, headers=h, timeout=25); _last[host] = time.time()
    if r.status_code == 200:
        http_cache[url] = {"etag": r.headers.get("ETag"), "lm": r.headers.get("Last-Modified")}
    return r

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
    # Nordic crypto companies
    (r"\bBare Bitcoin\b", re.I), (r"\bFiri\b", 0), (r"\bNBX\b", 0), (r"\bK33\b", 0), (r"\bNexa\b", 0),
    (r"\bSafello\b", 0), (r"\bVirtune\b", 0), (r"\bValuno\b", 0), (r"\bGreenMerc\b", re.I), (r"\bTrijo\b", 0),
    (r"\bCoinmotion\b", 0), (r"\bNorthcrypto\b", re.I), (r"\bKvarn X\b", 0), (r"\bMyntkaup\b", 0), (r"\bMonerium\b", 0),
    # merged from Kryptonytt (2026-10-04) so Norwegian coverage is not lost
    (r"\bBitmynt\b", re.I), (r"\bH100\b", 0),
]
KW = [(re.compile(r, f), r) for r, f in KW]
TOPICS = {
    "bitcoin": r"\bbitcoin|\bBTC\b|\bsatoshi|\butvinning|\bmining\b|\bminer|\blouhinta|\bgröftur",
    "blockchain": r"\bblokkjede|\bblockchain|\bblockkedj|\blohkoketju|\bbálkakeðj|\bNFT|\btoken|\bweb3|\bethereum|\bsolana|\bNexa\b|\bsmart ?contract",
    "crypto": r"\bkrypto(?!graf)|\bcrypto|\bstablecoin|\brafmynt|\bsýndar|\bcoin\b",
    "regulation": r"tilsyn|inspektionen|valvonta|\bMiCA|regul|regelverk|\bskatt|\bvero\b|\bverotus|forbud|förbud|\blov(?:en|forslag)?\b|\blag(?:en|förslag)?\b|\blaki\b|\blög\b|økokrim|hvitvask|penningtvätt|rahanpesu|peningaþvætt|sanksjon|norges bank|riksbank|suomen pankki|seðlabank|central ?bank|sentralbank|\bsvindel|\bbedrägeri|\bhuijaus|\bCBDC|\bpoliti|\bpolis|\bpoliisi|\blögregl",
    "companies": r"\bFiri\b|bare bitcoin|\bK33\b|\bNBX\b|Safello|Virtune|Valuno|Coinmotion|Northcrypto|Kvarn|Myntkaup|Monerium|selskap|bolag|yhtiö|fyrirtæki|\bbørs\b|\bbörs|pörssi|oppkjøp|förvärv|emisjon|nyemission|investor|gründer|grundare|\bASA\b|\bAB\b|\bOyj?\b|\behf\b|omsetning|omsättning|liikevaihto",
}
TOPICS = {k: re.compile(v, re.I) for k, v in TOPICS.items()}
# Gambling/affiliate list pages are advertising, not news (editor ruling 2026-10-04).
GAMBLING = re.compile(r"\bcasino\w*|\bkasino\w*|\bkasinot?\b|\bspilleside\w*|\bspelsajt\w*|\bnettcasino|\bnätcasino|\bnettikasino|\bodds(?:bolag|sider)?\b|\bbetting\b|\bsportsbook|\bbonuskod\w*|\bfree ?spins?\b|\bbästa\b.*\bcasino|\bgambling\b|\bspillavhengig\w*", re.I)
# Gambling regulators: such stories are kept (real news), never dropped.
GAMBLING_REGULATOR = re.compile(r"lotteritilsyn|spelinspektion|spillemyndighed|poliisihallitus|arpajais|happdrætt|sýslumað|\bMGA\b|gaming authority|gambling authority", re.I)
def is_gambling(text, url=""): return bool(GAMBLING.search(text) or re.search(r"casino|kasino|betting", url, re.I))
def matches(text, extra=()):
    return sorted({r for c, r in KW if c.search(text)} | {e for e in extra if e.lower() in text.lower()})
def topics_of(text):
    return [k for k, c in TOPICS.items() if c.search(text)] or ["crypto"]

def clean(html):
    return re.sub(r"\s+", " ", BeautifulSoup(html or "", "lxml").get_text(" ")).strip()
def canon(url):
    p = urllib.parse.urlparse(url.strip())
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query) if not k.lower().startswith(("utm_", "fbclid", "gclid", "ref"))]
    return urllib.parse.urlunparse((p.scheme.lower() or "https", p.netloc.lower().removeprefix("www."), p.path.rstrip("/") or "/", "", urllib.parse.urlencode(q), ""))
def norm_title(t): return re.sub(r"[^\w]+", " ", t.lower()).strip()
def iid(url): return hashlib.sha1(canon(url).encode()).hexdigest()[:12]
def when(e):
    for k in ("published_parsed", "updated_parsed"):
        if e.get(k): return dt.datetime(*e[k][:6], tzinfo=dt.timezone.utc)
    return None

# ---------- source map (domain -> outlet, country) ----------
SRC = {s["id"]: s for s in CFG["sources"]}
DOMAIN2OUT = {}
for s in CFG["sources"]:
    if s.get("type") == "bing": continue
    d = urllib.parse.urlparse(s["url"]).netloc.removeprefix("www.")
    DOMAIN2OUT.setdefault(d, s.get("outlet", s["id"]))
TLD2C = {".no": "NO", ".se": "SE", ".dk": "DK", ".fi": "FI", ".is": "IS"}
def country_of_url(url, fallback=None):
    d = urllib.parse.urlparse(url).netloc.lower()
    return next((c for t, c in TLD2C.items() if d.endswith(t)), fallback)
def outlet_for(url, fallback_name):
    d = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    for dom, out in DOMAIN2OUT.items():
        if d == dom or d.endswith("." + dom): return out, SRC[out]["name"] if out in SRC else fallback_name
    return d, fallback_name or d
LANG = {"NO": "Norwegian", "SE": "Swedish", "DK": "Danish", "FI": "Finnish", "IS": "Icelandic"}

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
    """Fetches only public metadata (title, description, date) from a page. Never article text.
    og:image is seen and dropped. The picture URL is not returned."""
    if not robots_ok(url): raise RuntimeError("robots.txt disallows")
    r = get(url); r.raise_for_status(); soup = BeautifulSoup(r.text, "lxml")
    m = lambda **k: (soup.find("meta", attrs=k) or {}).get("content")
    title = m(property="og:title") or (soup.title.string if soup.title else "") or ""
    desc = m(property="og:description") or m(name="description") or ""
    note_og_image(m(property="og:image"))
    date = None
    iso = m(property="article:published_time") or m(name="date") or m(name="DC.date") or m(name="dcterms.date") or m(itemprop="datePublished")
    if not iso:
        t = soup.find("time", attrs={"datetime": True}); iso = t["datetime"] if t else None
    if iso:
        try: date = dt.datetime.fromisoformat(iso.strip().replace("Z", "+00:00"))
        except ValueError: date = None
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
    return clean(title), clean(desc), date

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

    def add(url, title, teaser, published, src, outlet, outlet_name, country, extra=(), all_rel=False, lang=None):
        pu = urllib.parse.urlparse(url)
        url = urllib.parse.urlunparse(pu._replace(query=urllib.parse.urlencode([(k, v) for k, v in urllib.parse.parse_qsl(pu.query) if not k.lower().startswith(("utm_", "fbclid", "gclid"))])))
        text = f"{title}. {teaser}"
        hits = matches(text, extra)
        if not hits and not all_rel: return
        if is_gambling(text, url):
            if not GAMBLING_REGULATOR.search(text):
                with open(P("state", "dropped_gambling.jsonl"), "a") as fh:
                    fh.write(json.dumps({"dropped_at": NOW.isoformat(timespec="seconds"), "url": url, "title": title, "source": src, "country": country}, ensure_ascii=False) + "\n")
                return
        if not title or not published or published < cutoff: return
        cu = canon(url)
        if cu in by_url:
            ex = by_url[cu]
            if src not in ex.setdefault("seen_via", []): ex["seen_via"].append(src)
            return
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
              "topics": topics_of(text), "matched": hits, "paywall": bool(SRC.get(outlet, {}).get("paywall", False)),
              "status": "pending", "summary": None}
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
    seen_html = load(P("state", "html_seen.json"), {})
    for s in CFG["sources"]:
        if not s.get("enabled") or not s.get("feed"): continue
        if a.only and s["id"] not in a.only.split(","): continue
        if s["type"] == "html":
            n_ok = 0; n_meta = 0; err = None; links = []
            try:
                if robots_ok(s["feed"]):
                    r = get(s["feed"]); r.raise_for_status(); n_ok = 1
                    soup = BeautifulSoup(r.text, "lxml")
                    links = sorted({urllib.parse.urljoin(s["feed"], x["href"]) for x in soup.find_all("a", href=True) if re.search(s["link_pattern"], x["href"])})
                else: err = "robots.txt disallows"
                for u in links[: s.get("max_new_per_run", 40)]:
                    if u in seen_html: continue  # seen before (Kaupr lists can overlap; the first country page wins)
                    n_meta += 1
                    t, d, date = page_meta(u)
                    seen_html[u] = {"title": t, "date": date.isoformat() if date else None}
                    out = s.get("outlet", s["id"])
                    add(u, t, d, date, s["id"], out, SRC.get(out, s)["name"].split(" (")[0], s["country"], s.get("match_extra", ()), all_rel=s.get("all_relevant", False), lang=s.get("language"))
            except Exception as ex: err = f"{type(ex).__name__}: {ex}"[:200]; log("ERR", s["id"], err)
            status[s["id"]] = {"checked": NOW.isoformat(timespec="seconds"), "ok": n_ok > 0, "requests": 1 + n_meta, "ok_requests": n_ok, "entries": len(links), "error": err}
            log(f"{s['id']:<22} html links={len(links)} err={err}"); continue
        urls = ([s["feed"].format(q=urllib.parse.quote(q)) for q in s.get("queries", [])]
                + [s["feed"].format(q=urllib.parse.quote(f"{t} site:{site}")) for site in s.get("sites", []) for t in s.get("site_terms", [])]) if s["type"] == "bing" else [s["feed"]]  # sites x site_terms: Kryptonytt's per-site search (bing-no-kn)
        n_ok = n_items = 0; err = None
        for u in urls:
            if not robots_ok(u): err = "robots.txt disallows"; log("SKIP robots", s["id"], u); continue
            try:
                r = get(u)
                if r.status_code == 304: n_ok += 1; continue
                if r.status_code != 200: err = f"HTTP {r.status_code}"; continue
                f = feedparser.parse(r.content); n_ok += 1; n_items += len(f.entries)
                for e in f.entries:
                    entry_carries_article_image(e)  # media:content / enclosure: counted, URL not stored
                    link = e.get("link") or ""
                    title = clean(e.get("title"))
                    teaser = clean(e.get("summary") or e.get("description") or "")
                    if s["type"] == "bing":
                        qs = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                        link = (qs.get("url") or [link])[0]
                        if not urllib.parse.urlparse(link).netloc.endswith(s["allowed_tld"]): continue
                        out, oname = outlet_for(link, (e.get("news_source") or "").strip())
                        add(link, title, teaser, when(e), s["id"], out, oname, s["country"])
                    else:
                        out = s.get("outlet", s["id"]); oname = SRC.get(out, s)["name"]
                        add(link, title, teaser, when(e), s["id"], out, oname, s["country"], s.get("match_extra", ()), s["type"] == "rss-all", lang=s.get("language"))
            except Exception as ex:
                err = f"{type(ex).__name__}: {ex}"[:200]; log("ERR", s["id"], u, err)
        status[s["id"]] = {"checked": NOW.isoformat(timespec="seconds"), "ok": n_ok > 0, "requests": len(urls),
                           "ok_requests": n_ok, "entries": n_items, "error": err}
        log(f"{s['id']:<22} ok={n_ok}/{len(urls)} entries={n_items} err={err}")

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
    save(P("state", "source_status.json"), status); save(P("state", "http_cache.json"), http_cache); save(P("state", "html_seen.json"), seen_html)
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
