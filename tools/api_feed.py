#!/usr/bin/env python3
"""Public static JSON API for Nordic Crypto, written into site/ at build time.

Versioned files live under api/v1/. No server, no auth. Only data the public site
already shows: approved news and own stories, published newsletter issues, the
events calendar (upcoming and past), sources, academia, the who's who, profiles,
licensed images, the rules map, the changelog and the article archive.

Not published: editor queue, pending drafts (except a preview build), rejected
stories, tip-server keys, subscriber lists, the analytics token, research notes,
and unpublished newsletter drafts.

GitHub Pages sends Access-Control-Allow-Origin: * on these files. A custom
headers file is not used, because GitHub Pages ignores it.

  python3 tools/api_feed.py            # write site/api from the committed public data
  # build.py calls write() on every build, including ./build.sh
"""
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import headlines as headlines_mod  # noqa: E402
import i18n  # noqa: E402
import illustrations  # noqa: E402
import press_images  # noqa: E402
import site_url  # noqa: E402
import source_logos  # noqa: E402
import event_block  # noqa: E402
import event_backfill  # noqa: E402
import event_select  # noqa: E402

API = "1"
SITE_NAME = "Nordic Crypto"
SIGN_OFF = "The Nordic Crypto team"
CUSTOM_BASE = site_url.BASE
# Brand accounts. The same URLs are linked from the site footer, About and the newsletter.
SITE_X_URL = "https://x.com/xcryptonordic"
SITE_TELEGRAM_URL = "https://t.me/nordiccryptochat"
NORDIC_UI = ("nn", "nb", "sv", "da", "fi", "is")
LANGS = list(i18n.ALL_LANGS)
COUNTRIES = ["NO", "SE", "DK", "FI", "IS", "NORDIC", "EU"]

def country_lang_map():
    """Country → default site language, the same object the switcher uses (tools/langselect.js BY_COUNTRY)."""
    path = os.path.join(ROOT, "tools", "langselect.js")
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r"var BY_COUNTRY = \{([\s\S]*?)\};", src)
    if not m:
        raise SystemExit("api: BY_COUNTRY missing from tools/langselect.js")
    pairs = re.findall(r"\b([A-Z]{2})\s*:\s*\"([a-z]{2})\"", m.group(1))
    if not pairs:
        raise SystemExit("api: BY_COUNTRY is empty")
    out = {}
    for country, lang in pairs:
        if lang not in i18n.ALL_LANGS:
            raise SystemExit(f"api: BY_COUNTRY {country} → {lang} is not a site language")
        out[country] = lang
    return out

def language_rows(feed):
    rows = []
    for lang in LANGS:
        rows.append({
            "code": lang,
            "name": i18n.NAME[lang],
            "native_name": i18n.NATIVE[lang],
            "english_name": i18n.ENGLISH[lang],
            "rtl": bool(i18n.RTL[lang]),
            "html_lang": i18n.HTML_LANG[lang],
            "og_locale": i18n.OG_LOCALE[lang],
            "home": feed.abs("" if lang == "en" else lang + "/"),
        })
    return rows

def _languages(feed):
    return feed.env(
        note=(
            "Site UI languages (chrome and presentation). English is the default; its home URL is the site root. "
            "native_name is the language-switcher label. rtl is true for Arabic and Urdu. "
            "Published article translations today are English plus summary_i18n for nn, nb, sv, da, fi and is. "
            "Other site languages fall back to the English field until a translation is published. "
            "These codes are not news-source languages, and this list does not add outlets."
        ),
        count=len(LANGS),
        languages=language_rows(feed),
    )

def _geo_language(feed):
    return feed.env(
        note=(
            "by_country is a default guess from the visitor's IP country. It is not a stored profile. "
            "The nc_lang cookie, set when the reader uses the language switcher, always wins. "
            "The same choice is also kept in localStorage under nc_lang; if the cookie is missing, that stored choice is the override. "
            "The country comes from the tipworker GET /api/geo, which returns Cloudflare's request.cf.country "
            "(XX and T1 count as unknown). Nothing about the lookup is stored or logged, and no third-party geo-IP service is used. "
            "If the Worker is unreachable, the browser's navigator.languages is used, then English. "
            "A country that is not listed defaults to en. "
            "Norwegian browser tags (no, nb, nn) default to nynorsk; bokmål stays one click away. "
            "India defaults to Hindi; Marathi (mr) has no country row. "
            "Mauritania (MR) defaults to Arabic (ar). The language code mr is Marathi, not Mauritania."
        ),
        cookie="nc_lang",
        storage="localStorage key nc_lang, the same switcher override. The cookie wins when both are set.",
        order=[
            "nc_lang cookie (language switcher; always wins)",
            "localStorage nc_lang (same override when the cookie is missing)",
            "GET /api/geo on the tipworker (Cloudflare request.cf.country)",
            "navigator.languages",
            "en",
        ],
        geo={
            "path": "/api/geo",
            "source": "tipworker, Cloudflare request.cf.country",
            "stored": False,
        },
        default="en",
        unmapped_country="en",
        by_country=country_lang_map(),
    )
DOCS_DESC = (
    "Public JSON feed of Nordic Crypto news, newsletters, events and the rest of the site data. "
    "No account. Start at /api/v1/index.json, the OpenAPI file, or /llms.txt."
)
# Keys that must never appear in a response. "review" is allowed on the rules document.
BANNED_KEYS = {
    "token", "secret", "password", "private_key", "api_key",
    "approved_by", "approved_at", "reject_reason", "editor_note",
    "summary_i18n_review", "summary_i18n_source", "title_i18n_source", "matched", "fetched", "seen_via", "via",
    "suggested_by", "suggested_status", "suggested_at", "merged_from", "site_terms",
    "removal_reason", "reviewed",
}

def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default

def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

def safe_id(value):
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip("-._")
    return s[:120]

def html_to_text(raw):
    s = raw or ""
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</p>", "\n\n", s)
    s = re.sub(r"(?i)</h[1-6]>", "\n\n", s)
    s = re.sub(r"(?i)</(li|tr)>", "\n", s)
    s = re.sub(r"(?i)<li[^>]*>", "- ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def language_code(name):
    return i18n.SRC_LANG.get(name or "", None)

def is_kaupr(source, source_name):
    return "kaupr" in f"{source or ''} {source_name or ''}".lower()

def sponsor_public(value):
    """Kaupr is a news source, never a sponsor. Drop that label if it ever appears."""
    if isinstance(value, str) and "kaupr" in value.lower():
        print("api: omitted a Kaupr sponsor label (Kaupr is a news source only)", file=sys.stderr)
        return None
    return value

def walk_banned(obj, where=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in BANNED_KEYS or str(k).startswith("_"):
                raise SystemExit(f"api: refused to publish key {where}.{k}")
            walk_banned(v, f"{where}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk_banned(v, f"{where}[{i}]")

def yaml_key(key):
    s = str(key)
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", s):
        return s
    return json.dumps(s, ensure_ascii=False)

def yaml_scalar(obj):
    if obj is None:
        return "null"
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        return str(obj)
    if isinstance(obj, str):
        if obj == "" or obj.strip() != obj or obj.lower() in {"true", "false", "null", "yes", "no", "~"} or re.match(r"^-?\d+(\.\d+)?$", obj) or any(c in obj for c in ":{}[]#&*!|>'\"%@`,"):
            return json.dumps(obj, ensure_ascii=False)
        return obj
    return json.dumps(obj, ensure_ascii=False)

def yaml_dump(obj, indent=0):
    """Small YAML writer for the OpenAPI document. Dicts and lists always break onto their own lines."""
    pad = " " * indent
    if isinstance(obj, str) and "\n" in obj:
        inner = "\n".join((" " * (indent + 2)) + line for line in obj.split("\n"))
        return "|-\n" + inner
    if isinstance(obj, list):
        if not obj:
            return "[]"
        lines = []
        for item in obj:
            if isinstance(item, (dict, list)) and item:
                rendered = yaml_dump(item, indent + 2)
                parts = rendered.split("\n")
                lines.append(f"{pad}- {parts[0].lstrip()}")
                lines.extend(parts[1:])
            elif isinstance(item, str) and "\n" in item:
                lines.append(f"{pad}- {yaml_dump(item, indent + 2)}")
            else:
                lines.append(f"{pad}- {yaml_scalar(item)}")
        return "\n".join(lines)
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        lines = []
        for k, v in obj.items():
            key = yaml_key(k)
            if isinstance(v, (dict, list)) and v:
                rendered = yaml_dump(v, indent + 2)
                lines.append(f"{pad}{key}:")
                lines.append(rendered if "\n" in rendered or rendered.startswith(" ") else (" " * (indent + 2)) + rendered)
            elif isinstance(v, str) and "\n" in v:
                lines.append(f"{pad}{key}: {yaml_dump(v, indent)}")
            else:
                lines.append(f"{pad}{key}: {yaml_scalar(v)}")
        return "\n".join(lines)
    return yaml_scalar(obj)


class Feed:
    def __init__(self, site, preview, base, now=None):
        self.site = site
        self.preview = bool(preview)
        self.base = base if base.endswith("/") else base + "/"
        self.custom = self.base
        self.generated = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
        self.now = event_select.clock(now)
        self.endpoints = []
        self.examples = {}

    def abs(self, path):
        return self.base + path.lstrip("/")

    def custom_abs(self, path):
        return self.custom + path.lstrip("/")

    def env(self, **kw):
        out = {
            "api_version": API,
            "name": SITE_NAME,
            "generated_at": self.generated,
            "preview": self.preview,
        }
        out.update(kw)
        return out

    def write_json(self, rel, obj):
        walk_banned(obj)
        dump(os.path.join(self.site, rel), obj)
        return rel

    def add_endpoint(self, id_, path, summary, schema, example=None, item_template=None):
        rec = {
            "id": id_,
            "method": "GET",
            "path": "/" + path.lstrip("/"),
            "url": self.abs(path),
            "url_custom_domain": self.custom_abs(path),
            "summary": summary,
            "schema": schema,
        }
        if example:
            rec["example_url"] = self.abs(example)
            rec["example_url_custom_domain"] = self.custom_abs(example)
        if item_template:
            rec["item_path"] = "/" + item_template.lstrip("/")
            rec["item_url_template"] = self.abs(item_template)
        self.endpoints.append(rec)

    def news_item(self, raw):
        item = dict(raw)
        url = item.get("url") or ""
        own = bool(item.get("own_story"))
        status = item.get("status") or "published"
        # Pending rows are listed in a preview build without the unpublished summary, matching the site.
        public = status in ("published", "owner")
        summary = item.get("summary") if public else None
        i18n_sum = item.get("summary_i18n") if public else None
        nid = item.get("id") or hashlib.sha256((url or item.get("title") or "").encode()).hexdigest()[:12]
        nid = safe_id(nid) or hashlib.sha256((url or "").encode()).hexdigest()[:12]
        press_images.strip_press_images(item)
        if not own:
            html_url = self.abs(f"stories/{nid}/")
        elif url and not str(url).startswith("http"):
            html_url = self.abs(url)
            url = html_url
            item["url"] = url
        elif url:
            html_url = self.abs(url)
            item["url"] = url
        else:
            html_url = None
        source = item.get("source")
        source_name = item.get("source_name")
        note = None
        if is_kaupr(source, source_name):
            note = "Kaupr is a news source only. Nordic Crypto does not treat Kaupr as a sponsor."
        import coverage as coverage_mod
        rows = coverage_mod.all_outlets(item)
        def api_outlet(row):
            logo = self.logo(source_logos.for_source(row.get("outlet"), preview=self.preview))
            rec = {
                "outlet": row.get("outlet"),
                "outlet_name": row.get("outlet_name"),
                "url": row.get("url"),
                "title": row.get("title"),
                "published": row.get("published"),
                "lang": row.get("lang"),
                "language_code": language_code(row.get("lang")),
                "country": row.get("country"),
                "source_type": row.get("source_type"),
                "paywall": bool(row.get("paywall")),
                "primary": bool(row.get("primary")),
                "logo": logo,
            }
            if is_kaupr(row.get("outlet"), row.get("outlet_name")):
                rec["source_note"] = "Kaupr is a news source only. Nordic Crypto does not treat Kaupr as a sponsor."
            return rec
        outlets = [api_outlet(r) for r in rows]
        out = {
            "id": nid,
            "url": url or None,
            "html_url": html_url,
            "api_url": self.abs(f"api/v1/news/{nid}.json"),
            "title": item.get("title"),
            "title_en": item.get("title_en"),
            "title_i18n": headlines_mod.public_title_i18n(item) if public else {},
            "source": source,
            "source_name": source_name,
            "source_logo": self.logo(source_logos.for_source(source, preview=self.preview)),
            "source_note": note,
            "country": item.get("country"),
            "language": item.get("language"),
            "language_code": language_code(item.get("language")),
            "published": item.get("published"),
            "topics": list(item.get("topics") or []),
            "summary": summary,
            "summary_i18n": {k: v for k, v in (i18n_sum or {}).items() if k in LANGS and v},
            "paywall": bool(item.get("paywall")),
            "links": [{"label": l.get("label"), "url": l.get("url")} for l in (item.get("links") or []) if l.get("url")],
            "own_story": own,
            "illustration": illustrations.api_record(illustrations.assign(item), self.abs),
            "primary_source": outlets[0] if outlets else None,
            "also_covered_by": outlets[1:],
            "sources": outlets,
            "coverage": coverage_mod.breakdown(rows),
        }
        # Raster URL of the same logo (PNG or WebP, never SVG) for apps that cannot draw SVG (SwiftUI AsyncImage).
        out["source_logo_url"] = None if own else (out["source_logo"] or {}).get("raster_url")
        if self.preview:
            out["status"] = "pending" if status not in ("published", "owner") else status
        return out

    def event_item(self, raw):
        eid = safe_id(raw.get("id"))
        if not eid:
            return None
        out = {
            "id": eid,
            "title": raw.get("title"),
            "title_original": raw.get("title_orig") or raw.get("title_original"),
            "start": raw.get("start"),
            "end": raw.get("end"),
            "place": raw.get("place"),
            "city": raw.get("city"),
            "country": raw.get("country"),
            "online": bool(raw.get("online")),
            "organiser": raw.get("organiser"),
            "url": raw.get("url"),
            "source": raw.get("source"),
            "paid": raw.get("paid"),
            "sponsored": sponsor_public(raw.get("sponsored")),
            "note": raw.get("note"),
            "note_i18n": {k: v for k, v in (raw.get("note_i18n") or {}).items() if k in LANGS and v} if raw.get("note") else {},
            "past": bool(raw.get("past")),
            "ongoing": event_select.classify(raw, self.now) == "ongoing",
            "html_url": self.abs(f"calendar/{eid}/"),
            "html_urls": {lang: self.abs(("" if lang == "en" else lang + "/") + f"calendar/{eid}/") for lang in i18n.ALL_LANGS},
            "api_url": self.abs(f"api/v1/events/{eid}.json"),
        }
        if raw.get("backfill"):
            out["backfill"] = True
            out["source"] = "backfill"
            if raw.get("event_type"):
                out["event_type"] = raw.get("event_type")
            if raw.get("language"):
                out["language"] = raw.get("language")
            speakers = event_backfill.speakers_fact(raw)
            if speakers:
                out["speakers_count"] = speakers["count"]
            videos = event_backfill.videos_fact(raw)
            if videos:
                out["videos_url"] = videos["url"]
            if raw.get("credits"):
                out["credits"] = raw.get("credits")
        fact = event_select.location_fact(raw)
        if fact:
            out["place_source"] = fact["credit"]
        att = event_select.attendees_fact(raw)
        if att:
            out["attendees"] = {
                "count": att["count"],
                "source_name": att["credit"]["name"],
                "source_url": att["credit"]["url"],
                "retrieved": att["credit"].get("retrieved"),
            }
        ids = [str(item) for item in (raw.get("talk_ids") or []) if item]
        if ids:
            out["talk_ids"] = ids
        if self.preview:
            out["status"] = raw.get("status")
        return out

    def talk_item(self, raw):
        tid = safe_id(raw.get("id"))
        if not tid:
            return None
        out = {key: raw.get(key) for key in TALK_FIELDS}
        out["id"] = tid
        out["speakers"] = raw.get("speakers") or []
        out["embed"] = bool(raw.get("embed"))
        out["html_url"] = self.abs(f"talks/#{tid}")
        out["api_url"] = self.abs(f"api/v1/talks/{tid}.json")
        return out

    def media(self, raw, kind):
        if not raw or not raw.get("file"):
            return None
        source_url = raw.get("source_url") or raw.get("source_page") or raw.get("page")
        return {
            "kind": kind,
            "file_url": self.abs(raw["file"]) if not str(raw["file"]).startswith("http") else raw["file"],
            "source_url": source_url,
            "author": raw.get("author"),
            "license": raw.get("license"),
            "license_url": raw.get("license_url"),
            "credit": raw.get("source") or raw.get("origin"),
        }

    def logo(self, rec):
        """News-outlet logo from source_logos.for_source(): the media fields plus raster_url.

        raster_url is a PNG or WebP (never SVG) so SwiftUI AsyncImage can draw it: the PNG rendering of an SVG
        (logos.json "raster"), or the WebP itself. Null when an SVG has no rendering yet. The original and the
        raster are copied into the site, so every URL here resolves."""
        out = self.media(rec, "logo")
        if not out:
            return None
        raster = rec.get("raster")
        out["raster_url"] = self.abs(raster) if raster else None
        if self.site:
            for f in (rec.get("file"), raster):
                if not f or str(f).startswith("http"):
                    continue
                src, dst = os.path.join(ROOT, f), os.path.join(self.site, f)
                if os.path.exists(src) and not os.path.exists(dst):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy(src, dst)
        return out

    def entity(self, raw):
        eid = safe_id(raw.get("id"))
        if not eid:
            return None
        profiles = []
        for p in raw.get("profiles") or []:
            if p.get("status") not in (None, "published") and not (self.preview and p.get("status") == "pending"):
                if p.get("status") != "published":
                    continue
            if not p.get("url"):
                continue
            profiles.append({
                "kind": p.get("kind"),
                "label": p.get("label"),
                "url": p.get("url"),
                "source_url": p.get("source_url"),
            })
        sources = []
        for s in raw.get("sources") or []:
            sources.append({"url": s.get("url"), "title": s.get("title"), "source_name": s.get("source_name"), "date": s.get("date")})
        out = {
            "id": eid,
            "api_url": self.abs(f"api/v1/orgchart/{eid}.json"),
            "html_url": self.abs(f"org-chart/#{eid}"),
            "name": raw.get("name"),
            "type": raw.get("type"),
            "sector": raw.get("sector"),
            "country": raw.get("country"),
            "description": raw.get("description"),
            "role": raw.get("role"),
            "org": raw.get("org"),
            "group": raw.get("group"),
            "profile_url": raw.get("profile_url"),
            "provenance": raw.get("origin"),
            "caveat": bool(raw.get("caveat")),
            "sources": sources,
            "logo": self.media(raw.get("logo"), "logo"),
            "image": self.media(raw.get("image"), "photo"),
            "profiles": profiles,
        }
        ids = [str(item) for item in (raw.get("talk_ids") or []) if item]
        if ids:
            out["talk_ids"] = ids
        events = [str(item) for item in (raw.get("event_ids") or []) if item]
        if events:
            out["event_ids"] = events
        talks = []
        for item in raw.get("talks") or []:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            brief = {"id": str(item.get("id")), "title": item.get("title") or ""}
            if item.get("video_url"):
                brief["video_url"] = item.get("video_url")
            if item.get("event_id"):
                brief["event_id"] = item.get("event_id")
            if item.get("date"):
                brief["date"] = item.get("date")
            talks.append(brief)
        if talks:
            out["talks"] = talks
        affiliations = []
        for item in raw.get("affiliations") or []:
            if not isinstance(item, dict):
                continue
            if not (item.get("organisation") and item.get("source_url") and item.get("retrieved_at")):
                continue
            aff = {
                "talk_id": item.get("talk_id"),
                "organisation": item.get("organisation"),
                "source_url": item.get("source_url"),
                "source_name": item.get("source_name"),
                "retrieved_at": item.get("retrieved_at"),
            }
            if item.get("role"):
                aff["role"] = item.get("role")
            if item.get("date"):
                aff["date"] = item.get("date")
            if item.get("event_id"):
                aff["event_id"] = item.get("event_id")
            affiliations.append(aff)
        if affiliations:
            out["affiliations"] = affiliations
        return out

    def relation(self, raw):
        rid = safe_id(raw.get("id")) or safe_id(f"{raw.get('from')}-{raw.get('to')}-{raw.get('type')}")
        return {
            "id": rid,
            "api_url": self.abs(f"api/v1/orgchart/relations/{rid}.json"),
            "from": raw.get("from"),
            "to": raw.get("to"),
            "type": raw.get("type"),
            "label": raw.get("label"),
            "sources": [{"url": s.get("url"), "title": s.get("title"), "source_name": s.get("source_name"), "date": s.get("date")} for s in (raw.get("sources") or [])],
        }


def public_news(preview):
    """Same inclusion rule as build.py, without rewriting data/news.json."""
    news = load(os.path.join(ROOT, "data", "news.json"), {"items": []}) or {"items": []}
    items = []
    for raw in news.get("items") or []:
        item = json.loads(json.dumps(raw))
        if not preview and item.get("summary_i18n_review", "approved") != "approved":
            item.pop("summary_i18n", None)
        if item.get("status") == "published" and (item.get("summary") or "").strip():
            items.append(item)
        elif preview and item.get("status") == "pending":
            items.append(item)
    items.sort(key=lambda i: i.get("published") or "", reverse=True)
    return items, news.get("updated")


def public_org(preview):
    org = load(os.path.join(ROOT, "data", "orgchart.json"), {"entities": [], "relations": []}) or {}
    ents = []
    for raw in org.get("entities") or []:
        if not raw.get("sources"):
            continue
        if raw.get("status") == "published" or (preview and raw.get("status") == "pending"):
            e = json.loads(json.dumps(raw))
            e["profiles"] = [p for p in (e.get("profiles") or []) if p.get("status") == "published" or (preview and p.get("status") == "pending")]
            if not preview:
                for k in ("logo", "image"):
                    im = e.get(k)
                    if im and im.get("review", "ok") != "ok":
                        e.pop(k, None)
            ents.append(e)
    ids = {e["id"] for e in ents}
    rels = []
    for raw in org.get("relations") or []:
        if not raw.get("sources") or raw.get("from") not in ids or raw.get("to") not in ids:
            continue
        if raw.get("status") == "published" or (preview and raw.get("status") == "pending"):
            rels.append(raw)
    return ents, rels, org.get("updated"), org.get("regulation") or [], org.get("caveats") or []


TALK_FIELDS = (
    "id", "video_url", "platform", "title", "speakers", "event_name", "event_url",
    "calendar_event_id", "event_id", "unlink_reason", "speaker_ids", "city", "country", "date", "published", "duration", "language",
    "channel", "description", "source_url", "retrieved_at", "added_at", "embed",
)

def public_talks():
    """Talks archive. Empty fields stay null. Newest talk date first."""
    raw = load(os.path.join(ROOT, "data", "talks.json"), {"talks": []}) or {"talks": []}
    rows = []
    for item in raw.get("talks") or []:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        row = {}
        for key in TALK_FIELDS:
            value = item.get(key)
            if key in ("speakers", "speaker_ids"):
                row[key] = [s for s in value if isinstance(s, str) and s] if isinstance(value, list) else []
            elif key == "embed":
                row[key] = bool(value)
            elif value in ("", None):
                row[key] = None if key != "title" else value
            else:
                row[key] = value
        if not row.get("title"):
            row["title"] = None
        rows.append(row)
    rows.sort(key=lambda r: (r.get("date") or r.get("published") or "", r.get("id") or ""), reverse=True)
    return rows

def public_events(preview, now=None):
    """Read-only mirror of build.events_for_site (does not rewrite the archive)."""
    import events as eventslib
    ev = load(os.path.join(ROOT, "data", "events.json"), {"events": []}) or {"events": []}
    ap_path = os.path.join(ROOT, "queue", "approved.json")
    approvals_present = os.path.exists(ap_path)
    ap = (load(ap_path, {}) or {}).get("events", {}) or {}
    now = now or dt.datetime.now(dt.timezone.utc).astimezone()
    # Compare with offset-aware datetimes. Source times carry an offset.
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    out = []
    for raw in ev.get("events") or []:
        e = dict(raw)
        status = event_block.publication_status(e, ap, preview, approvals_present, from_archive=False)
        if not status:
            continue
        e["status"] = status
        if not (e.get("place") or e.get("online")) or not e.get("organiser") or not e.get("start"):
            continue
        e["note"] = ap.get("notes", {}).get(e["id"]) or (e.get("note") if preview else None)
        if e["id"] in (ap.get("title_en") or {}):
            e["title_orig"] = e["title"]
            e["title"] = ap["title_en"][e["id"]]
        if e["id"] in ap.get("sponsored", []):
            e["sponsored"] = True
        if e["id"] in ap.get("sponsor", {}):
            e["sponsored"] = ap["sponsor"][e["id"]]
        e["sponsored"] = eventslib.clear_kaupr_sponsor(e.get("sponsored"))
        if e["id"] in ap.get("paid", {}):
            e["paid"] = ap["paid"][e["id"]]
        if e.get("status") == "published":
            e["note"] = ap.get("notes", {}).get(e["id"])
        e["note_i18n"] = (ap.get("notes_i18n") or {}).get(e["id"]) if e.get("note") else None
        site_url.brand_note(e)  # same correction as build.events_for_site; approved.json is local
        end = e.get("end") or e["start"]
        e["past"] = dt.datetime.fromisoformat(end) < now
        out.append(e)
    ark = load(os.path.join(ROOT, "archive", "events.json"), {"events": []}) or {"events": []}
    seen = {e["id"] for e in out}
    for raw in ark.get("events") or []:
        if raw.get("id") in seen:
            continue
        e = dict(raw)
        status = event_block.publication_status(e, ap, preview, approvals_present, from_archive=True)
        if not status:
            continue
        e["status"] = status
        e["note_i18n"] = e.get("note_i18n") or ((ap.get("notes_i18n") or {}).get(e["id"]) if e.get("note") else None)
        site_url.brand_note(e)
        end = e.get("end") or e.get("start")
        if not end:
            continue
        e["past"] = dt.datetime.fromisoformat(end) < now
        out.append(e)
    out.sort(key=lambda e: dt.datetime.fromisoformat(e["start"]))
    return out


def repo_context(preview=False):
    items, updated = public_news(preview)
    ents, rels, org_updated, regulation, caveats = public_org(preview)
    events = public_events(preview)
    return {
        "items": items,
        "events": (events, None),
        "ents": ents,
        "rels": rels,
        "org": {"updated": org_updated, "regulation": regulation, "caveats": caveats},
        "cfg": load(os.path.join(ROOT, "sources.json"), {"sources": []}) or {"sources": []},
        "news": {"updated": updated},
    }


def _academia_rows(preview):
    ac = load(os.path.join(ROOT, "data", "academia.json"), {}) or {}
    tr = load(os.path.join(ROOT, "data", "academia_i18n.json"), {}) or {}
    sections = {}
    for key in ("courses", "groups", "publications", "research"):
        rows = []
        for raw in ac.get(key) or []:
            if raw.get("status") != "approved" and not (preview and raw.get("status") in ("pending", "unverified")):
                continue
            if raw.get("status") != "approved" and not preview:
                continue
            row = {k: v for k, v in raw.items() if k not in BANNED_KEYS and not str(k).startswith("_")}
            row.pop("editor_note", None)
            row.pop("status", None)
            about_i18n = (tr.get(raw.get("url")) or {}) if raw.get("url") else {}
            row["about_i18n"] = {k: v for k, v in about_i18n.items() if k in LANGS and v and not str(k).startswith("_")}
            rows.append(row)
        sections[key] = rows
    return ac.get("updated"), [r for r in (ac.get("rules") or []) if isinstance(r, str)], sections


def _row_id(section, row, n, used):
    if section == "publications" and row.get("doi"):
        base = "doi-" + safe_id(str(row["doi"]).replace("/", "_"))
    elif section == "courses" and row.get("code"):
        base = safe_id(f"{row.get('country') or 'xx'}-{row['code']}")
    elif row.get("url"):
        tail = re.sub(r"^https?://", "", row["url"]).strip("/")
        base = safe_id(f"{section}-{tail}")
    else:
        base = safe_id(row.get("name") or row.get("title") or f"{section}-{n}")
    base = base or f"{section}-{n}"
    cand, i = base, 2
    while cand in used:
        cand = f"{base}-{i}"
        i += 1
    used.add(cand)
    return cand


def _changelog(preview):
    cl = load(os.path.join(ROOT, "changelog.json"), {"entries": []}) or {"entries": []}
    launch = cl.get("launch_date")
    rows = []
    for e in cl.get("entries") or []:
        if e.get("review") == "pending" and not preview:
            continue
        d = launch if e.get("date") == "launch" else e.get("date")
        i18n_map = {}
        for lang, block in (e.get("i18n") or {}).items():
            if lang in LANGS and isinstance(block, dict):
                i18n_map[lang] = {"title": block.get("title"), "description": block.get("description")}
        rows.append({"id": e.get("id"), "date": d, "title": e.get("title"), "description": e.get("description"), "i18n": i18n_map})
    rows.sort(key=lambda e: e.get("date") or "9999-99-99", reverse=True)
    return launch, rows


def _sources(cfg):
    outlets, search = [], []
    for s in cfg.get("sources") or []:
        row = {
            "id": s.get("id"),
            "name": s.get("name"),
            "country": s.get("country"),
            "kind": s.get("kind"),
            "url": s.get("url"),
            "type": s.get("type"),
            "paywall": bool(s.get("paywall")),
            "enabled": bool(s.get("enabled")),
            "status": s.get("status") or "",
            "verified": s.get("verified"),
            "language": s.get("language"),
            "coverage": s.get("coverage"),
            "region": s.get("region"),
            "method": s.get("method") or ("rss" if s.get("type") in ("rss", "rss-all") else "html" if s.get("type") == "html" else "sitemap" if s.get("type") == "sitemap" else "search" if s.get("type") == "bing" else "manual"),
            "icon_url": s.get("logo") if isinstance(s.get("logo"), str) and str(s.get("logo")).startswith("https://") else None,
            "logo_source": s.get("logo_source") if isinstance(s.get("logo_source"), str) and str(s.get("logo_source")).startswith("https://") else None,
        }
        feed = s.get("feed")
        if feed and "{q}" not in feed and s.get("type") != "bing":
            row["feed"] = feed
        else:
            row["feed"] = None
        if is_kaupr(s.get("id"), s.get("name")):
            row["source_note"] = "Kaupr is a news source only. Nordic Crypto does not treat Kaupr as a sponsor."
        else:
            row["source_note"] = None
        outlets.append(row)
        if s.get("type") == "bing":
            search.append({
                "id": s.get("id"),
                "country": s.get("country"),
                "allowed_tld": s.get("allowed_tld"),
                "queries": list(s.get("queries") or []),
            })
    events = []
    for s in cfg.get("event_sources") or []:
        if event_block.blocked_source(s):
            continue
        events.append({
            "id": s.get("id"),
            "name": s.get("name"),
            "url": s.get("url"),
            "country": s.get("country"),
            "city": s.get("city"),
            "organiser": s.get("organiser"),
            "enabled": bool(s.get("enabled", True)),
            "trusted": bool(s.get("trusted")),
            "status": s.get("status") or "",
            "method": s.get("method") or "",
            "intake": s.get("type"),
            "ics": s.get("ics"),
            "organizer_id": s.get("organizer_id"),
            "venue_id": s.get("venue_id"),
        })
    return outlets, search, events


SOURCE_LOGO_NOTE = ("logo / source_logo is the outlet's logo (file_url is the original, SVG or WebP). logo_url (sources) and "
                    "source_logo_url (news) are the same logo as a raster image, PNG or WebP, never SVG, for apps that cannot draw SVG. "
                    "Logos are the publishers' own trademarks, shown only to identify the source of a headline. "
                    "They are null until the editor has checked the logo.")


def _rules(preview, base):
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import rules_page
    R = load(os.path.join(ROOT, "rules.json"), None)
    if not R:
        return None
    if R.get("review") != "approved" and not preview:
        return {
            "available": False,
            "review": R.get("review") or "pending",
            "html_url": base + "rules/",
            "summary": "The rules page is awaiting editor review. The public site shows a short placeholder.",
        }
    en = rules_page.STR["en"]
    eu = json.loads(json.dumps(R.get("eu") or {}))
    for act in eu.get("acts") or []:
        act["note"] = en.get(act.get("note_key"), "")
    for agency in eu.get("agencies") or []:
        agency["note"] = en.get(agency.get("note_key"), "")
    copy = {lang: dict(rules_page.STR.get(lang) or {}) for lang in LANGS}
    return {
        "available": True,
        "review": R.get("review"),
        "checked": R.get("checked"),
        "html_url": base + "rules/",
        "not_legal_advice": True,
        "sources": R.get("sources") or {},
        "eu": eu,
        "eea": R.get("eea") or {},
        "countries": R.get("countries") or {},
        "copy": copy,
    }


def _newsletters(feed):
    pub = os.path.join(ROOT, "newsletter", "published")
    data = load(os.path.join(pub, "issues.json"), {}) or {}
    issues = sorted(data.get("issues") or [], key=lambda i: (i.get("date") or "", i.get("number") or 0), reverse=True)
    out = []
    for iss in issues:
        iid = safe_id(iss.get("id"))
        if not iid:
            continue
        per = iss.get("period") or []
        period = {"start": per[0], "end": per[1]} if len(per) == 2 else None
        v = iss.get("video") or {}
        video = None
        if v:
            poster = v.get("poster")
            subs = v.get("subs")
            video = {
                "language": "en",
                "duration_seconds": v.get("duration"),
                "width": v.get("width"),
                "height": v.get("height"),
                "bytes": v.get("bytes"),
                "sha256": v.get("sha256"),
                "download_url": v.get("url"),
                "file_url": feed.abs(f"newsletter/{iid}/{v.get('file') or 'video.mp4'}"),
                "poster_url": feed.abs(f"newsletter/{iid}/{poster}") if poster else None,
                "subtitles_url": feed.abs(f"newsletter/{iid}/{subs}") if subs else None,
                "subtitles_language": "en" if subs else None,
            }
        html_urls = {lang: feed.abs(("" if lang == "en" else lang + "/") + f"newsletter/{iid}/") for lang in LANGS}
        bodies, texts = {}, {}
        en_html = ""
        en_path = os.path.join(pub, iid, "issue.html")
        if os.path.exists(en_path):
            en_html = site_url.expand(open(en_path, encoding="utf-8").read())
        for lang in LANGS:
            if lang == "en":
                continue
            p = os.path.join(pub, iid, f"issue.{lang}.html")
            if os.path.exists(p):
                bodies[lang] = site_url.expand(open(p, encoding="utf-8").read())
                texts[lang] = html_to_text(bodies[lang])
        full = {
            "id": iid,
            "number": iss.get("number"),
            "date": iss.get("date"),
            "period": period,
            "lang": iss.get("lang") or "en",
            "title": iss.get("title"),
            "subtitle": iss.get("subtitle"),
            "title_i18n": {k: v for k, v in (iss.get("title_i18n") or {}).items() if k in LANGS and v},
            "subtitle_i18n": {k: v for k, v in (iss.get("subtitle_i18n") or {}).items() if k in LANGS and v},
            "stories": iss.get("stories"),
            "events": iss.get("events"),
            "sign_off": SIGN_OFF,
            "html_url": html_urls["en"],
            "html_urls": html_urls,
            "api_url": feed.abs(f"api/v1/newsletters/{iid}.json"),
            "video": video,
            "body_languages": ["en"] + sorted(bodies),
            "text": html_to_text(en_html),
            "html": en_html,
            "text_i18n": texts,
            "html_i18n": bodies,
        }
        out.append(full)
    return out


def _archive(feed):
    data = load(os.path.join(ROOT, "archive", "articles.json"), {}) or {}
    rows = []
    for a in data.get("articles") or []:
        aid = safe_id(a.get("id"))
        if not aid:
            continue
        rows.append({
            "id": aid,
            "api_url": feed.abs(f"api/v1/archive/articles/{aid}.json"),
            "site": a.get("site") or "nordic-crypto",
            "url": a.get("url"),
            "canonical_url": a.get("canonical_url"),
            "title": a.get("title"),
            "titles": a.get("titles") or {},
            "source": a.get("source"),
            "source_name": a.get("source_name"),
            "country": a.get("country"),
            "published_at": a.get("published_at"),
            "first_published_on_site": a.get("first_published_on_site"),
            "last_seen_on_site": a.get("last_seen_on_site"),
            "languages": a.get("languages") or [],
            "summaries": a.get("summaries") or {},
            "topics": a.get("topics") or [],
            "removed": bool(a.get("removed")),
            "removed_at": a.get("removed_at"),
        })
    return data.get("exported_at"), rows


def brand_social():
    """Nordic Crypto brand accounts for /api/v1/meta.json. English name, Nordic name_i18n, other languages use name."""
    def names(key):
        return {lang: i18n.t(lang, key) for lang in NORDIC_UI}
    return {
        "note": (
            "Nordic Crypto brand accounts for the site and the iOS app. "
            "label and name are English. name_i18n has nn, nb, sv, da, fi and is. "
            "Other site languages use name."
        ),
        "telegram": {
            "label": "Telegram",
            "name": i18n.t("en", "tg_follow"),
            "name_i18n": names("tg_follow"),
            "url": SITE_TELEGRAM_URL,
        },
        "x": {
            "label": "X",
            "name": i18n.t("en", "x_follow"),
            "name_i18n": names("x_follow"),
            "url": SITE_X_URL,
            "handle": "@xcryptonordic",
        },
    }


def _meta(feed):
    pages = [
        ("", "News"),
        ("calendar/", "Events calendar, upcoming and past"),
        ("events/previous/", "Previous events, newest first. Finished events are kept."),
        ("talks/", "Public talks on bitcoin, cryptocurrencies and blockchain in the Nordics, with video"),
        ("org-chart/", "Who's who: industry, regulators and the regulation overview"),
        ("rules/", "How EU crypto rules become law in the five countries"),
        ("regulation-videos/", "Country explainer videos: how crypto rules are decided in each Nordic country"),
        ("academia/", "Courses, student groups, publications and research"),
        ("sources/", "News and event sources"),
        ("newsletter/", "Newsletter issues"),
        ("about/", "About, privacy, corrections and removal"),
        ("media/", "Logo and media kit"),
        ("ethics/", "Editorial ethics (Vær Varsom-plakaten)"),
        ("changelog/", "Site changelog"),
        ("tip/", "Send a tip (not part of this data API)"),
        ("columnist/", "Apply as a columnist (not part of this data API)"),
        ("markets/", "Prices on Nordic exchanges (market data, not investment advice)"),
        ("screen/", "News screen, English"),
        ("api/", "This API, human documentation"),
    ]
    return feed.env(
        sign_off=SIGN_OFF,
        description="Bitcoin, blockchain and crypto news, events, a who's who, regulation and academia for Norway, Sweden, Denmark, Finland and Iceland.",
        license="MIT",
        operator="Jørgen S. Notland (jQrgen), Oslo",
        ios={
            "name": "Nordic Crypto",
            "distribution": "TestFlight",
            "label": "iOS app (TestFlight)",
            "url": "https://testflight.apple.com/join/nQ2fpjZn",
            "note": "Public TestFlight invite. This feed does not list an App Store page. The Nordic Crypto TestFlight version especially supports Apple TV.",
            "apple_tv": i18n.t("en", "ios_tv"),
            "apple_tv_i18n": {lang: i18n.t(lang, "ios_tv") for lang in i18n.ALL_LANGS},
        },
        languages=language_rows(feed),
        language_note=(
            "Site languages, with native_name, english_name and rtl, are listed in languages and in /api/v1/languages.json. "
            "Our own text is written in English first. summary_i18n, title_i18n, subtitle_i18n, note_i18n and about_i18n "
            "carry published translations, today nn, nb, sv, da, fi and is. Other site languages fall back to the English field "
            "until a translation is published. On a news item, title is the source headline, title_en is our English headline "
            "and title_i18n is our headline in nn, nb, sv, da, fi and is. The site shows the page-language headline first "
            "and the source headline underneath when they differ. Outlet headlines inside sources stay in that outlet's language. "
            "There is no query string for language: each JSON document already carries every published translation. "
            "The language switcher's country default is a guess; see /api/v1/geo-language.json. The nc_lang cookie wins."
        ),
        countries=[{"code": c, "name_en": i18n.t("en", "c_" + c)} for c in COUNTRIES],
        urls={
            "github_pages": feed.base,
            "custom_domain": feed.custom,
            "docs": feed.abs("api/"),
            "discovery": feed.abs("api/v1/index.json"),
            "openapi": feed.abs("api/v1/openapi.json"),
            "llms_txt": feed.abs("llms.txt"),
            "github": "https://github.com/jQrgen/nordic-crypto",
            "newsletter": feed.abs("newsletter/"),
            "rss": feed.abs("rss.xml"),
            "telegram": SITE_TELEGRAM_URL,
            "x": SITE_X_URL,
            "logo": feed.abs("assets/brand/crest.svg"),
            "logo_png": feed.abs("assets/media/nordic-crypto-crest.png"),
            "wordmark": feed.abs("assets/brand/wordmark.svg"),
            "icon": feed.abs("assets/brand/icon.svg"),
            "og_image": feed.abs("assets/brand/og-image.png"),
            "media": feed.abs("media/"),
            "stylesheet": feed.abs("assets/brand/nordic-crypto.css"),
        },
        social=brand_social(),
        url_note=(
            "Absolute urls in this API use the public site origin "
            f"({feed.base}). "
            "GitHub Pages serves that origin from the repository root. "
            "There is no /nordic-crypto/ path on this origin. "
            "GitHub Pages sends Access-Control-Allow-Origin: * on these files."
        ),
        editorial={
            "sign_off": SIGN_OFF,
            "kaupr": "Kaupr (kaupr.io) is a news source only. It is never a sponsor of Nordic Crypto.",
            "not_investment_advice": True,
        },
        site_pages=[{"path": "/" + p if p else "/", "url": feed.abs(p), "title": title} for p, title in pages],
        cors=cors_doc(),
        not_included=[
            "Editor queue, rejected stories and unpublished drafts",
            "Reader tips, tip-server keys and newsletter subscriber addresses",
            "Analytics token and private health or financial data",
            "Research notes that are not on the public site",
        ],
    )


def cors_doc():
    return {
        "access_control_allow_origin": "*",
        "credentials": False,
        "how": (
            "GitHub Pages sends Access-Control-Allow-Origin: * on static files, including this JSON. "
            "A browser on any origin can fetch() the URLs. GitHub Pages does not honour a _headers file, "
            "so this site does not ship one. The same header is present on the custom domain while GitHub Pages serves it."
        ),
    }


def _markets(feed, markets):
    """Write /api/v1/markets*.json. markets is the body from tools/markets.py, or None to fetch live."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import markets as markets_mod
    if markets is None:
        try:
            markets = markets_mod.fetch()
        except Exception as ex:
            print(f"markets: fetch failed: {ex}", file=sys.stderr)
            markets = markets_mod.empty_failure(str(ex).split("\n")[0][:300])
    doc = markets_mod.public_document(
        markets, generated_at=feed.generated, preview=feed.preview, base=feed.base, custom=feed.custom,
    )
    files = markets_mod.documents(doc)
    for rel, obj in files.items():
        feed.write_json(rel, obj)
    markets_mod.write_logos(feed.site)
    feed.add_endpoint(
        "markets",
        "api/v1/markets.json",
        "Nordic exchange prices. Market data, not investment advice. Each ticker names the exchange, fetched_at, the source URL and volume when the exchange published it. NOK, SEK, DKK and EUR only. aggregated is one row per pair.",
        "MarketCatalogue",
        example="api/v1/markets/firi.json" if "api/v1/markets/firi.json" in files else None,
    )
    feed.add_endpoint(
        "markets-aggregated",
        "api/v1/markets/aggregated.json",
        "One price per base-quote pair. BTC-NOK is separate from BTC-EUR. last is the mean of published last prices. mid is the mean of bid/ask midpoints and is not blended into last. Volume is summed only within the same field and the same pair. logo_url is a CC0 icon when cryptocurrency-icons includes the asset, otherwise null.",
        "MarketAggregated",
        example="api/v1/markets/aggregated.json" if "api/v1/markets/aggregated.json" in files else None,
    )
    feed.add_endpoint(
        "markets-exchange",
        "api/v1/markets/{exchange}.json",
        "Prices from one included exchange: firi (Norway), nbx (Norway) or coinmotion (Finland).",
        "MarketExchange",
        example="api/v1/markets/firi.json" if "api/v1/markets/firi.json" in files else None,
    )
    asset_example = None
    for rel in files:
        if rel.startswith("api/v1/markets/by-asset/") and rel.endswith(".json"):
            asset_example = rel
            if rel.endswith("/BTC.json"):
                break
    feed.add_endpoint(
        "markets-asset",
        "api/v1/markets/by-asset/{symbol}.json",
        "Prices for one asset (the base symbol, such as BTC) on every included Nordic exchange, plus aggregated pairs for each quote currency and logo_url when an icon is available.",
        "MarketAsset",
        example=asset_example,
    )
    return doc


def write(site, *, preview, base, items, events, entities, relations, org_updated, regulation, caveats, sources_cfg, news_updated, markets=None, now=None):
    feed = Feed(site, preview, base, now=now)
    os.makedirs(site, exist_ok=True)

    news = [feed.news_item(i) for i in items]
    news = [n for n in news if n.get("id")]
    # Public build: pending rows are already excluded by the caller. Drop empty-summary non-preview rows.
    if not preview:
        news = [n for n in news if (n.get("summary") or "").strip() or n.get("own_story")]
    seen = set()
    uniq = []
    for n in news:
        if n["id"] in seen:
            print(f"api: duplicate news id {n['id']}", file=sys.stderr)
            continue
        seen.add(n["id"])
        uniq.append(n)
    news = uniq

    raw_events = list(events or [])
    evs = [e for e in (feed.event_item(e) for e in raw_events) if e]
    upcoming = [e for e in evs if not e["past"]]
    past = [e for e in evs if e["past"]][::-1]
    ongoing = [e for e in evs if e.get("ongoing")]
    # Backfill is previous-archive only. It is not part of the calendar lists above.
    raw_past = [e for e in raw_events if e.get("past")]
    previous = [e for e in (feed.event_item(e) for e in event_backfill.merge_previous(raw_past, feed.now)) if e]
    known = {e["id"] for e in evs}
    backfill = [e for e in previous if e.get("backfill") and e["id"] not in known]

    ents = [e for e in (feed.entity(e) for e in entities) if e]
    rels = [feed.relation(r) for r in relations]
    profiles = [{"entity_id": e["id"], "name": e["name"], "type": e["type"], "country": e["country"], "api_url": feed.abs(f"api/v1/profiles/{e['id']}.json"), "links": e["profiles"]} for e in ents if e["profiles"]]
    images = []
    for e in ents:
        for key in ("logo", "image"):
            im = e.get(key)
            if im:
                images.append(dict(im, entity_id=e["id"], entity_name=e["name"]))

    updated_ac, rules_ac, sections = _academia_rows(preview)
    ac_ids = set()
    for key, rows in sections.items():
        for i, row in enumerate(rows):
            row["id"] = _row_id(key, row, i + 1, ac_ids)
            row["section"] = key
            row["api_url"] = feed.abs(f"api/v1/academia/{row['id']}.json")

    launch, changes = _changelog(preview)
    for e in changes:
        eid = safe_id(e.get("id")) or safe_id(e.get("title"))
        e["id"] = eid
        e["html_url"] = feed.abs(f"changelog/#{eid}") if eid else feed.abs("changelog/")
        e["api_url"] = feed.abs(f"api/v1/changelog/{eid}.json") if eid else None

    outlets, search, event_sources = _sources(sources_cfg or {})
    for row in outlets:
        row["logo"] = feed.logo(source_logos.for_source(row.get("id"), preview=preview))
        row["logo_url"] = (row["logo"] or {}).get("raster_url")
    rules = _rules(preview, feed.base)
    letters = _newsletters(feed)
    exported_at, articles = _archive(feed)

    def collection(rel, summary, schema, obj, example=None, item_template=None):
        feed.write_json(rel, obj)
        feed.add_endpoint(rel.replace("/", "-").replace(".json", ""), rel, summary, schema, example, item_template)

    lang_note = (
        "summary is English. summary_i18n holds nn, nb, sv, da, fi and is when that translation is published. "
        "Other site languages use the English summary until a translation exists. "
        "title is the source headline. title_en is our English headline when we wrote one. "
        "title_i18n holds nn, nb, sv, da, fi and is when that headline is not already the source headline. "
        "The site shows the page-language headline first and the source headline under it when they differ. "
        "Other site languages use title_en. "
        "source_logo is the outlet image when assets/img/logos/logos.json has a checked file for the source id "
        "(or its outlet, or a _source_alias). Null means show the source name as text. "
        "illustration is a picture we may show, with source, author, license and url. "
        "It is never a photograph copied or hotlinked from another newspaper. "
        "primary_source is that outlet. also_covered_by lists every other outlet on the same event "
        "(outlet, outlet_name, url, title, published, lang, country, source_type, paywall, logo). "
        "sources is the primary plus those outlets. coverage.count is how many outlets, "
        "coverage.by_country and coverage.by_source_type (national, regional, official, international) "
        "are the counts and shares for the bars, including zeros. "
        "html_url is our page for the story. url on the item is the primary outlet. "
        "The site language list is /api/v1/languages.json."
    )
    collection(
        "api/v1/news.json",
        "Published news and our own stories, newest first.",
        "NewsList",
        feed.env(updated=news_updated, language_note=lang_note, logo_note=SOURCE_LOGO_NOTE, count=len(news), items=news),
        example=f"api/v1/news/{news[0]['id']}.json" if news else None,
        item_template="api/v1/news/{id}.json",
    )
    for n in news:
        feed.write_json(f"api/v1/news/{n['id']}.json", feed.env(item=n))
    by_c = {}
    for c in COUNTRIES:
        rows = [n for n in news if n.get("country") == c]
        by_c[c] = len(rows)
        feed.write_json(f"api/v1/news/by-country/{c}.json", feed.env(country=c, count=len(rows), items=rows))
    feed.add_endpoint("news-by-country", "api/v1/news/by-country/{country}.json",
                      "Published news for one country code: NO, SE, DK, FI, IS, NORDIC or EU.",
                      "NewsList", example="api/v1/news/by-country/NO.json")
    topics = {}
    for n in news:
        for t in n.get("topics") or []:
            topics.setdefault(t, []).append(n)
    topic_index = []
    for t in sorted(topics):
        tid = safe_id(t) or "topic"
        feed.write_json(f"api/v1/news/by-topic/{tid}.json", feed.env(topic=t, count=len(topics[t]), items=topics[t]))
        topic_index.append({"id": t, "count": len(topics[t]), "url": feed.abs(f"api/v1/news/by-topic/{tid}.json")})
    collection("api/v1/news/topics.json", "Topic ids present in the published news, with counts.", "TopicIndex",
               feed.env(topics=topic_index), example="api/v1/news/by-topic/bitcoin.json" if any(t["id"] == "bitcoin" for t in topic_index) else None,
               item_template="api/v1/news/by-topic/{topic}.json")

    list_letters = []
    for full in letters:
        brief = {k: full[k] for k in ("id", "number", "date", "period", "lang", "title", "subtitle", "title_i18n", "subtitle_i18n", "stories", "events", "sign_off", "html_url", "html_urls", "api_url", "video", "body_languages")}
        list_letters.append(brief)
        feed.write_json(f"api/v1/newsletters/{full['id']}.json", feed.env(item=full))
    collection(
        "api/v1/newsletters.json",
        "Published newsletter issues, newest first. The list omits the HTML body; the issue URL includes text and html.",
        "NewsletterList",
        feed.env(sign_off=SIGN_OFF, count=len(list_letters), issues=list_letters),
        example=f"api/v1/newsletters/{letters[0]['id']}.json" if letters else None,
        item_template="api/v1/newsletters/{id}.json",
    )

    def ev_doc(rel, summary, rows, example=None):
        collection(rel, summary, "EventList", feed.env(count=len(rows), events=rows), example=example, item_template="api/v1/events/{id}.json" if rel == "api/v1/events.json" else None)
    ev_doc("api/v1/events.json", "Public events, soonest start first, including past events.", evs, example=f"api/v1/events/{evs[0]['id']}.json" if evs else None)
    collection("api/v1/events/upcoming.json", "Events that have not ended, soonest first. Judged in the event's own offset.", "EventList", feed.env(count=len(upcoming), events=upcoming, ongoing=ongoing))
    collection("api/v1/events/past.json", "Finished public events, newest first. Finished events stay in the archive.", "EventList", feed.env(count=len(past), events=past))
    collection("api/v1/events/previous.json", "Previous events, newest finish first. Finished calendar events plus backfilled public events (source backfill). Backfill is not on the calendar or in upcoming or past.", "EventList", feed.env(count=len(previous), events=previous))
    for e in evs:
        feed.write_json(f"api/v1/events/{e['id']}.json", feed.env(item=e))
    for e in backfill:
        feed.write_json(f"api/v1/events/{e['id']}.json", feed.env(item=e))
    for c in COUNTRIES:
        rows = [e for e in evs if e.get("country") == c]
        feed.write_json(f"api/v1/events/by-country/{c}.json", feed.env(country=c, count=len(rows), events=rows))
    feed.add_endpoint("events-by-country", "api/v1/events/by-country/{country}.json",
                      "Public events for one country code.", "EventList", example="api/v1/events/by-country/NO.json")

    talks = [t for t in (feed.talk_item(raw) for raw in public_talks()) if t]
    collection(
        "api/v1/talks.json",
        "Public talks on bitcoin, cryptocurrencies and blockchain in the Nordic countries, newest first. "
        "A player is embedded on the site only when embed is true (YouTube via youtube-nocookie.com, or the Vimeo player). "
        "Unknown fields are null. description is ours; title and the other details come from the platform.",
        "TalkList",
        feed.env(count=len(talks), talks=talks),
        example=f"api/v1/talks/{talks[0]['id']}.json" if talks else None,
        item_template="api/v1/talks/{id}.json",
    )
    for talk in talks:
        feed.write_json(f"api/v1/talks/{talk['id']}.json", feed.env(item=talk))
    for code in ("NO", "SE", "DK", "FI", "IS", "FO", "GL", "AX"):
        subset = [t for t in talks if t.get("country") == code]
        feed.write_json(f"api/v1/talks/by-country/{code}.json", feed.env(country=code, count=len(subset), talks=subset))
    feed.add_endpoint(
        "talks-by-country",
        "api/v1/talks/by-country/{country}.json",
        "Public talks for one country code: NO, SE, DK, FI, IS, FO (Faroe Islands), GL (Greenland) or AX (Åland).",
        "TalkList",
        example="api/v1/talks/by-country/NO.json",
    )

    collection("api/v1/sources.json", "News outlets, justice-system press pages, the public search terms, and event sources. coverage is national, regional, local or justice. region is the place. feed is null when no working RSS, sitemap or index page was verified. method is rss, html, sitemap, search or manual. Event sources name the intake method. Luma calendars use a public iCal subscribe URL. Eventbrite organizers and venues use the v3 API when the server has EVENTBRITE_TOKEN; the token is not in this feed. Without it, event pages are schema.org JSON-LD. icon_url is a public icon from the outlet when one was easy to find. logo_source is the URL the stored logo was fetched from. logo is the checked outlet image for that source id when one is on file, used only to identify the source. Kaupr is marked as a news source only and is never an event sponsor.", "SourceCatalogue",
               feed.env(
                   user_agent=site_url.expand((sources_cfg or {}).get("user_agent") or ""),
                   min_delay_seconds=(sources_cfg or {}).get("min_delay_seconds"),
                   keyword_note=i18n.t("en", "src_kw"),
                   kaupr="Kaupr (kaupr.io) is one of the news sources. It is never a sponsor.",
                   logo_note=SOURCE_LOGO_NOTE,
                   count=len(outlets),
                   sources=outlets,
                   search=search,
                   event_sources=event_sources,
               ))

    ac_counts = {k: len(v) for k, v in sections.items()}
    collection("api/v1/academia.json", "Editor-approved courses, student groups, publications and research.", "Academia",
               feed.env(updated=updated_ac, inclusion_rules=rules_ac, counts=ac_counts, **sections))
    for key in sections:
        collection(f"api/v1/academia/{key}.json", f"Academia section: {key}.", "AcademiaSection",
                   feed.env(section=key, count=len(sections[key]), items=sections[key]))
    for rows in sections.values():
        for row in rows:
            feed.write_json(f"api/v1/academia/{row['id']}.json", feed.env(item=row))
    feed.add_endpoint("academia-item", "api/v1/academia/{id}.json", "One academia row. The id is in academia.json.", "AcademiaItem",
                      example=f"api/v1/academia/{next(iter(ac_ids))}.json" if ac_ids else None)

    collection("api/v1/orgchart.json", "Published who's who: organisations, people, relations, regulation notes and caveats. A person named on a talk has talk_ids, event_ids and talks. affiliations lists the organisation the talk page stated for that talk, with the talk date when the page gave one, the source URL and the retrieval time. An affiliation the page did not state is omitted.", "OrgChart",
               feed.env(updated=org_updated, count=len(ents), entities=ents, relations=rels, regulation=regulation, caveats=caveats),
               example=f"api/v1/orgchart/{ents[0]['id']}.json" if ents else None,
               item_template="api/v1/orgchart/{id}.json")
    collection("api/v1/orgchart/relations.json", "Relations between published who's who entries.", "RelationList", feed.env(count=len(rels), relations=rels))
    collection("api/v1/orgchart/regulation.json", "Short regulation status for each Nordic country, as on the who's who page.", "RegulationList", feed.env(regulation=regulation, caveats=caveats))
    for e in ents:
        feed.write_json(f"api/v1/orgchart/{e['id']}.json", feed.env(item=e))
    for r in rels:
        feed.write_json(f"api/v1/orgchart/relations/{r['id']}.json", feed.env(item=r))
    feed.add_endpoint("orgchart-relation", "api/v1/orgchart/relations/{id}.json", "One relation from the who's who.", "Relation")

    collection("api/v1/profiles.json", "Public profile links (Wikipedia, X, Wikidata and similar) for people and organisations.", "ProfileList",
               feed.env(count=len(profiles), profiles=profiles),
               example=f"api/v1/profiles/{profiles[0]['entity_id']}.json" if profiles else None,
               item_template="api/v1/profiles/{id}.json")
    for p in profiles:
        feed.write_json(f"api/v1/profiles/{p['entity_id']}.json", feed.env(item=p))

    collection("api/v1/images.json", "Logos and photos used on the public who's who, with licence and credit. These are not newspaper photographs.", "ImageList",
               feed.env(count=len(images), images=images))
    story_pictures = illustrations.catalogue(feed.abs)
    collection("api/v1/illustrations.json",
               "Pictures used on story cards and story pages. Each record has source, author, license and url. "
               "No photograph from another newspaper is included. Outlet logos are in images.json and on each news item as source_logo.",
               "IllustrationList",
               feed.env(count=len(story_pictures), images=story_pictures,
                        policy="Nordic Crypto does not copy, store, proxy or hotlink news photographs. See docs/image-policy.md."))

    collection("api/v1/changelog.json", "Site changelog (product changes, not the news), newest first.", "ChangelogList",
               feed.env(launch_date=launch, count=len(changes), entries=changes),
               example=f"api/v1/changelog/{changes[0]['id']}.json" if changes else None,
               item_template="api/v1/changelog/{id}.json")
    for e in changes:
        if e.get("id"):
            feed.write_json(f"api/v1/changelog/{e['id']}.json", feed.env(item=e))

    collection("api/v1/rules.json", "How EU crypto rules become law in the five countries. Simplified, not legal advice. Omitted while the page is still a placeholder.", "Rules",
               feed.env(**(rules or {"available": False})))

    collection("api/v1/archive/articles.json", "Append-only archive of stories that have been on the public site. removed is  true when a story later left the site; the row stays.", "ArticleArchive",
               feed.env(exported_at=exported_at, count=len(articles), articles=articles),
               example=f"api/v1/archive/articles/{articles[0]['id']}.json" if articles else None,
               item_template="api/v1/archive/articles/{id}.json")
    for a in articles:
        feed.write_json(f"api/v1/archive/articles/{a['id']}.json", feed.env(item=a))

    market_doc = _markets(feed, markets)
    market_counts = {}
    for ex in market_doc.get("exchanges") or []:
        market_counts[ex.get("id")] = ex.get("ticker_count") or 0
    market_bases = []
    for row in market_doc.get("tickers") or []:
        if row.get("base") not in market_bases:
            market_bases.append(row["base"])
    example_asset = "BTC" if "BTC" in market_bases else (market_bases[0] if market_bases else None)

    collection(
        "api/v1/languages.json",
        "Site UI languages: code, native name, English name, rtl, html lang and home URL.",
        "LanguageList",
        _languages(feed),
    )
    collection(
        "api/v1/geo-language.json",
        "Country to default site language. An IP guess only; the nc_lang cookie from the language switcher wins.",
        "GeoLanguage",
        _geo_language(feed),
    )

    meta = _meta(feed)
    collection("api/v1/meta.json", "Site name, languages, countries, page list, CORS, editorial notes and brand social accounts (social.telegram, social.x).", "SiteMeta", meta)

    # Discovery, OpenAPI, llms.txt and the human page. Registered after the datasets exist.
    index = feed.env(
        title="Nordic Crypto data API",
        sign_off=SIGN_OFF,
        docs_url=feed.abs("api/"),
        docs_url_custom_domain=feed.custom_abs("api/"),
        openapi_url=feed.abs("api/v1/openapi.json"),
        openapi_yaml_url=feed.abs("api/v1/openapi.yaml"),
        llms_txt_url=feed.abs("llms.txt"),
        api_catalog_url=feed.abs(".well-known/api-catalog"),
        stability="Version 1 field names stay. New fields may be added. Removing or renaming a field means a new version path.",
        auth="none",
        cors=cors_doc(),
        bases={"github_pages": feed.base, "custom_domain": feed.custom},
        language_note=meta["language_note"],
        editorial=meta["editorial"],
        counts={
            "news": len(news),
            "news_by_country": by_c,
            "newsletters": len(letters),
            "events": len(evs),
            "events_upcoming": len(upcoming),
            "events_ongoing": len(ongoing),
            "events_past": len(past),
            "events_previous": len(previous),
            "talks": len(talks),
            "sources": len(outlets),
            "academia": ac_counts,
            "org_entities": len(ents),
            "org_relations": len(rels),
            "profiles": len(profiles),
            "images": len(images),
            "illustrations": len(story_pictures),
            "changelog": len(changes),
            "archive_articles": len(articles),
            "markets": market_doc.get("count") or 0,
            "markets_aggregated": market_doc.get("aggregated_count") or 0,
            "markets_by_exchange": market_counts,
        },
        endpoints=list(feed.endpoints),
        start_here=[
            {"description": "Nordic exchange prices (market data, not investment advice)", "url": feed.abs("api/v1/markets.json")},
            {"description": "Aggregated price per pair, one quote currency at a time", "url": feed.abs("api/v1/markets/aggregated.json")},
            {"description": "Prices from one exchange", "url": feed.abs("api/v1/markets/firi.json")},
            *([{"description": "Prices for one asset, on every included exchange", "url": feed.abs(f"api/v1/markets/by-asset/{example_asset}.json")}] if example_asset else []),
            {"description": "All published news", "url": feed.abs("api/v1/news.json")},
            {"description": "One news item", "url": news[0]["api_url"] if news else None},
            {"description": "Newsletter issues", "url": feed.abs("api/v1/newsletters.json")},
            {"description": "One newsletter issue, with text", "url": letters[0]["api_url"] if letters else None},
        ],
    )
    # The index lists every other endpoint. Add itself first.
    index["endpoints"] = [{
        "id": "index",
        "method": "GET",
        "path": "/api/v1/index.json",
        "url": feed.abs("api/v1/index.json"),
        "url_custom_domain": feed.custom_abs("api/v1/index.json"),
        "summary": "Discovery document: every endpoint, with example URLs.",
        "schema": "Discovery",
    }] + index["endpoints"]
    feed.write_json("api/v1/index.json", index)
    feed.write_json("api/index.json", feed.env(
        current="v1",
        index_url=feed.abs("api/v1/index.json"),
        docs_url=feed.abs("api/"),
        openapi_url=feed.abs("api/v1/openapi.json"),
        llms_txt_url=feed.abs("llms.txt"),
    ))

    spec = openapi(feed, index)
    feed.write_json("api/v1/openapi.json", spec)
    yaml_path = os.path.join(site, "api", "v1", "openapi.yaml")
    os.makedirs(os.path.dirname(yaml_path), exist_ok=True)
    with open(yaml_path, "w", encoding="utf-8") as fh:
        fh.write(yaml_dump(spec) + "\n")

    llms = llms_txt(feed, index)
    llms_path = os.path.join(site, "llms.txt")
    with open(llms_path, "w", encoding="utf-8") as fh:
        fh.write(llms)
    linkset = api_catalog(feed)
    well = os.path.join(site, ".well-known")
    os.makedirs(well, exist_ok=True)
    raw = json.dumps(linkset, ensure_ascii=False, indent=1) + "\n"
    for name in ("api-catalog", "api-catalog.json"):
        with open(os.path.join(well, name), "w", encoding="utf-8") as fh:
            fh.write(raw)

    fragment = docs_fragment(index)
    doc = standalone_docs(fragment, feed.base)
    docs_path = os.path.join(site, "api", "index.html")
    os.makedirs(os.path.dirname(docs_path), exist_ok=True)
    with open(docs_path, "w", encoding="utf-8") as fh:
        fh.write(doc)

    print(f"api v1: {len(news)} news, {len(letters)} newsletters, {len(evs)} events, {len(ents)} org rows, {market_doc.get('count') or 0} market rows, {len(feed.endpoints) + 1} endpoints -> {site}")
    return index


def openapi(feed, index):
    def ok(ref, summary):
        return {"200": {"description": summary, "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{ref}"}}}}}
    paths = {}
    def add_path(path, operation, summary, schema):
        params = []
        for name in re.findall(r"\{([^}]+)\}", path):
            if name == "country" and "/talks/" in path:
                enum = ["NO", "SE", "DK", "FI", "IS", "FO", "GL", "AX"]
            elif name == "country":
                enum = COUNTRIES
            else:
                enum = None
            params.append({"name": name, "in": "path", "required": True, "schema": {"type": "string", **({"enum": enum} if enum else {})}})
        paths[path] = {"get": {
            "operationId": operation,
            "summary": summary,
            "responses": ok(schema or "Document", summary),
            **({"parameters": params} if params else {}),
        }}
    for ep in index["endpoints"]:
        add_path(ep["path"], re.sub(r"[^A-Za-z0-9]+", "_", ep["id"]).strip("_"), ep["summary"], ep.get("schema"))
        if ep.get("item_path") and ep["item_path"] not in paths:
            add_path(ep["item_path"], re.sub(r"[^A-Za-z0-9]+", "_", ep["id"]).strip("_") + "_item",
                     "One item from " + ep["path"], "Document")
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Nordic Crypto data API",
            "version": API,
            "description": (
                f"Public read-only JSON for Nordic Crypto ({feed.base}). "
                "No authentication. News, newsletters, events, sources, academia, the who's who, profiles, images, "
                "the rules map, the changelog, the article archive, public talk videos and Nordic exchange prices (market data, not investment advice). "
                "Kaupr is a news source only, never a sponsor. The sign-off is The Nordic Crypto team. "
                "GitHub Pages sends Access-Control-Allow-Origin: * so browsers can fetch these files. "
                "English text is the default; published translations are inside each object under *_i18n. "
                "Site languages: /api/v1/languages.json. IP-country language guess: /api/v1/geo-language.json "
                "(the nc_lang cookie wins). "
                f"Discovery: {feed.abs('api/v1/index.json')}. Human docs: {feed.abs('api/')}."
            ),
            "license": {"name": "MIT", "url": "https://github.com/jQrgen/nordic-crypto/blob/main/LICENSE"},
            "contact": {"name": SITE_NAME, "url": feed.abs("about/")},
        },
        "servers": [
            {"url": feed.base.rstrip("/"), "description": "Public site"},
        ],
        "paths": paths,
        "components": {"schemas": schemas()},
    }


def schemas():
    i18n_obj = {"type": "object", "additionalProperties": {"type": "string"}, "description": "Keys are site language codes: nn, nb, sv, da, fi, is. English lives in the sibling field."}
    logo_url_desc = ("Absolute URL of the news source's logo as a raster image (PNG or WebP, never SVG, so SwiftUI AsyncImage can draw it) on the GitHub Pages base. Null until the editor has checked "
                     "the logo (review ok); a preview build also lists pending logos. The publisher's trademark, shown only to identify the source.")
    source_logo = {
        "type": "object", "nullable": True,
        "description": "Outlet logo for this source id (via outlet / _source_alias in assets/img/logos/logos.json). Null when no checked image is on file; show the name only. Same fields as a who's who logo in images.json, plus raster_url.",
        "properties": {
            "kind": {"type": "string", "enum": ["logo"]},
            "file_url": {"type": "string", "description": "The original file as fetched: SVG, or WebP for raster logos."},
            "raster_url": {"type": "string", "nullable": True, "description": "PNG rendering of an SVG (256 px on the long side, transparent), or the WebP itself. Same value as logo_url."},
            "source_url": {"type": "string", "nullable": True, "description": "Wikimedia Commons file page, or the image URL on the publisher's site."},
            "author": {"type": "string", "nullable": True},
            "license": {"type": "string", "nullable": True, "description": "Commons licence, or \"Publisher's own logo, used only to identify the source of a headline\"."},
            "license_url": {"type": "string", "nullable": True},
            "credit": {"type": "string", "nullable": True, "description": "Wikimedia Commons or Official website."},
        },
    }
    source_row = {
        "type": "object",
        "required": ["id", "name", "country"],
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "country": {"type": "string"},
            "kind": {"type": "string", "nullable": True},
            "url": {"type": "string", "nullable": True},
            "type": {"type": "string"},
            "paywall": {"type": "boolean"},
            "enabled": {"type": "boolean"},
            "status": {"type": "string"},
            "verified": {"type": "string", "nullable": True},
            "language": {"type": "string", "nullable": True},
            "feed": {"type": "string", "nullable": True},
            "source_note": {"type": "string", "nullable": True},
            "logo_url": {"type": "string", "nullable": True, "description": logo_url_desc},
            "logo": source_logo,
        },
    }
    news_item = {
        "type": "object",
        "required": ["id", "title", "published", "api_url"],
        "properties": {
            "id": {"type": "string"},
            "url": {"type": "string", "description": "Story the reader follows. Absolute."},
            "html_url": {"type": "string", "nullable": True, "description": "Our story page: summary, licensed picture and the outlets. For our own articles this is the article. For other outlets this is the coverage page; url is the primary outlet."},
            "api_url": {"type": "string"},
            "title": {"type": "string", "description": "Source headline."},
            "title_en": {"type": "string", "nullable": True, "description": "Our English headline, when the source headline is not English."},
            "title_i18n": {"type": "object", "additionalProperties": {"type": "string"}, "description": "Our headline in nn, nb, sv, da, fi and is, when that language is not already the source headline. English is title_en."},
            "source": {"type": "string", "description": "Source id from sources.json."},
            "source_name": {"type": "string"},
            "source_logo": source_logo,
            "source_note": {"type": "string", "nullable": True},
            "country": {"type": "string"},
            "language": {"type": "string"},
            "language_code": {"type": "string", "nullable": True},
            "published": {"type": "string", "description": "ISO 8601 date-time with offset."},
            "topics": {"type": "array", "items": {"type": "string"}},
            "summary": {"type": "string", "nullable": True, "description": "Our English summary."},
            "summary_i18n": i18n_obj,
            "paywall": {"type": "boolean"},
            "links": {"type": "array", "items": {"type": "object"}},
            "own_story": {"type": "boolean"},
            "illustration": {
                "type": "object",
                "nullable": True,
                "description": "Picture for the card and the story page. source, author, license and url are the credit. file_url is our copy. Never a newspaper photograph.",
                "properties": {
                    "id": {"type": "string"},
                    "kind": {"type": "string", "enum": ["original", "commons", "official-press"]},
                    "file_url": {"type": "string"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"},
                    "alt": {"type": "string"},
                    "source": {"type": "string"},
                    "author": {"type": "string"},
                    "license": {"type": "string"},
                    "license_url": {"type": "string", "nullable": True},
                    "url": {"type": "string"},
                    "credit": {"type": "string"},
                    "modifications": {"type": "string", "nullable": True},
                    "terms": {"type": "string", "nullable": True},
                },
            },
            "source_logo_url": {"type": "string", "nullable": True, "description": logo_url_desc + " Same as source_logo.raster_url."},
            "primary_source": {"$ref": "#/components/schemas/NewsOutlet"},
            "also_covered_by": {"type": "array", "items": {"$ref": "#/components/schemas/NewsOutlet"}, "description": "Other outlets on the same event. Empty when only the primary covered it."},
            "sources": {"type": "array", "items": {"$ref": "#/components/schemas/NewsOutlet"}, "description": "Primary first, then also_covered_by."},
            "coverage": {"$ref": "#/components/schemas/NewsCoverage"},
        },
    }
    news_outlet = {
        "type": "object",
        "required": ["url", "primary"],
        "properties": {
            "outlet": {"type": "string", "description": "Source id from sources.json."},
            "outlet_name": {"type": "string"},
            "url": {"type": "string"},
            "title": {"type": "string", "description": "That outlet's headline."},
            "published": {"type": "string", "description": "ISO 8601 date-time with offset."},
            "lang": {"type": "string", "description": "Language name, same vocabulary as language on the story."},
            "language_code": {"type": "string", "nullable": True},
            "country": {"type": "string"},
            "source_type": {"type": "string", "enum": ["national", "regional", "official", "international"], "description": "national, regional (regional and local), official (justice and official), or international."},
            "paywall": {"type": "boolean"},
            "primary": {"type": "boolean"},
            "logo": source_logo,
            "source_note": {"type": "string", "nullable": True, "description": "Set when the outlet is Kaupr: a news source only, never a sponsor."},
        },
    }
    news_coverage = {
        "type": "object",
        "required": ["count", "by_country", "by_source_type"],
        "properties": {
            "count": {"type": "integer"},
            "by_country": {"type": "array", "items": {"type": "object", "properties": {"country": {"type": "string"}, "count": {"type": "integer"}, "share": {"type": "number"}}}},
            "by_source_type": {"type": "array", "description": "Always national, regional, official and international, in that order. count 0 is included.", "items": {"type": "object", "properties": {"type": {"type": "string"}, "count": {"type": "integer"}, "share": {"type": "number"}}}},
        },
    }
    event_item = {
        "type": "object",
        "required": ["id", "title", "start"],
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "title_original": {"type": "string", "nullable": True},
            "start": {"type": "string", "description": "ISO 8601 date-time with offset."},
            "end": {"type": "string", "nullable": True},
            "place": {"type": "string", "nullable": True},
            "city": {"type": "string", "nullable": True},
            "country": {"type": "string"},
            "online": {"type": "boolean"},
            "organiser": {"type": "string"},
            "url": {"type": "string"},
            "source": {"type": "string"},
            "paid": {"nullable": True},
            "sponsored": {"nullable": True, "description": "false, true, or the sponsor's name. Never Kaupr."},
            "note": {"type": "string", "nullable": True},
            "note_i18n": i18n_obj,
            "past": {"type": "boolean"},
            "ongoing": {"type": "boolean", "description": "True while start <= now <= end. Additive. Events with no end are never ongoing."},
            "place_source": {"type": "object", "nullable": True, "description": "Credit for the venue or online flag: name, url, retrieved. Omitted when the place cannot be credited."},
            "attendees": {"type": "object", "nullable": True, "description": "Registered participant count with source_name, source_url and retrieved. Omitted when the source did not state a count. Capacity is not a count."},
            "html_url": {"type": "string", "description": "This event's page on the site, /calendar/<id>/."},
            "html_urls": {"type": "object", "description": "The same page in every site language. English is at the root. Other codes are /<code>/calendar/<id>/."},
            "api_url": {"type": "string"},
            "backfill": {"type": "boolean", "description": "True when the row comes from the previous-events backfill. Absent on calendar events. Those rows are only in previous.json."},
            "event_type": {"type": "string", "nullable": True, "enum": ["conference", "meetup", "hackathon", "seminar"], "description": "Set on backfilled events when a source supports the type."},
            "language": {"type": "string", "nullable": True, "description": "Language code when a source states it. Omitted when unknown."},
            "speakers_count": {"type": "integer", "nullable": True, "description": "Exact speaker count when a source states one. Omitted otherwise. A session count is not a speaker count."},
            "videos_url": {"type": "string", "nullable": True, "description": "Link to talk videos when a source gives one."},
            "talk_ids": {"type": "array", "items": {"type": "string"}, "description": "Ids of talks in /api/v1/talks.json recorded at this event. Omitted when none are linked."},
            "credits": {"type": "object", "nullable": True, "description": "Per-field source_name, source_url and retrieved_at on backfilled events."},
        },
    }
    talk_item = {
        "type": "object",
        "required": ["id", "video_url", "platform", "title", "source_url", "retrieved_at", "added_at"],
        "description": "A public talk. Unknown fields are null. description is written by Nordic Crypto. The other details come from the platform named in source_url.",
        "properties": {
            "id": {"type": "string"},
            "video_url": {"type": "string"},
            "platform": {"type": "string", "enum": ["youtube", "vimeo", "university", "other"]},
            "title": {"type": "string"},
            "speakers": {"type": "array", "items": {"type": "string"}, "description": "Names the platform page states. Empty when none are stated."},
            "event_name": {"type": "string", "nullable": True},
            "event_url": {"type": "string", "nullable": True},
            "calendar_event_id": {"type": "string", "nullable": True, "description": "Same value as event_id. The event page is /calendar/<id>/ and the document is /api/v1/events/<id>.json. Previous events are also listed in /api/v1/events/previous.json."},
            "event_id": {"type": "string", "nullable": True, "description": "Id of the event this talk belongs to. Null when the talk could not be dated or placed."},
            "unlink_reason": {"type": "string", "nullable": True, "description": "Why the talk is not linked to an event. Null when event_id is set."},
            "city": {"type": "string", "nullable": True},
            "country": {"type": "string", "nullable": True, "description": "NO, SE, DK, FI, IS, FO, GL or AX."},
            "date": {"type": "string", "nullable": True, "description": "Calendar date of the talk, YYYY-MM-DD, when the source states it."},
            "published": {"type": "string", "nullable": True, "description": "Date the video was published, YYYY-MM-DD."},
            "duration": {"type": "string", "nullable": True, "description": "ISO 8601 duration when the platform states a length."},
            "language": {"type": "string", "nullable": True, "description": "Language of the talk when the source states it."},
            "channel": {"type": "string", "nullable": True},
            "description": {"type": "string", "description": "Short neutral summary in our own words."},
            "source_url": {"type": "string", "description": "Page the metadata was retrieved from."},
            "retrieved_at": {"type": "string", "description": "ISO 8601 timestamp."},
            "added_at": {"type": "string", "description": "ISO 8601 timestamp."},
            "embed": {"type": "boolean", "description": "True when the platform's oEmbed response includes an official player."},
            "speaker_ids": {"type": "array", "items": {"type": "string"}, "description": "Who's who ids for speakers, in the same order as speakers. Empty when the page named nobody."},
            "html_url": {"type": "string"},
            "api_url": {"type": "string"},
        },
    }
    issue = {
        "type": "object",
        "required": ["id", "date", "title"],
        "properties": {
            "id": {"type": "string"},
            "number": {"type": "integer"},
            "date": {"type": "string", "description": "ISO date YYYY-MM-DD."},
            "period": {"type": "object", "properties": {"start": {"type": "string"}, "end": {"type": "string"}}},
            "title": {"type": "string"},
            "subtitle": {"type": "string"},
            "title_i18n": i18n_obj,
            "subtitle_i18n": i18n_obj,
            "sign_off": {"type": "string"},
            "text": {"type": "string", "description": "Plain text of the English issue. Present on the issue URL, not the list."},
            "html": {"type": "string"},
            "text_i18n": {"type": "object"},
            "html_i18n": {"type": "object"},
            "video": {"type": "object", "nullable": True},
            "api_url": {"type": "string"},
            "html_url": {"type": "string"},
        },
    }
    env = {"api_version": {"type": "string"}, "name": {"type": "string"}, "generated_at": {"type": "string"}, "preview": {"type": "boolean"}}
    def wrap(name, extra):
        props = dict(env)
        props.update(extra)
        return {"type": "object", "properties": props, "description": name}
    return {
        "Document": {"type": "object", "additionalProperties": True},
        "Discovery": wrap("Discovery", {"endpoints": {"type": "array"}, "counts": {"type": "object"}, "cors": {"type": "object"}}),
        "NewsOutlet": news_outlet,
        "NewsCoverage": news_coverage,
        "NewsItem": news_item,
        "NewsList": wrap("NewsList", {"count": {"type": "integer"}, "items": {"type": "array", "items": news_item}, "updated": {"type": "string", "nullable": True}, "logo_note": {"type": "string"}}),
        "TopicIndex": wrap("TopicIndex", {"topics": {"type": "array"}}),
        "Event": event_item,
        "EventList": wrap("EventList", {"count": {"type": "integer"}, "events": {"type": "array", "items": event_item}}),
        "Talk": talk_item,
        "TalkList": wrap("TalkList", {"count": {"type": "integer"}, "talks": {"type": "array", "items": talk_item}}),
        "NewsletterIssue": issue,
        "NewsletterList": wrap("NewsletterList", {"count": {"type": "integer"}, "issues": {"type": "array", "items": issue}}),
        "Source": source_row,
        "SourceCatalogue": wrap("SourceCatalogue", {"logo_note": {"type": "string"}, "sources": {"type": "array", "items": source_row}, "search": {"type": "array"}, "event_sources": {"type": "array"}}),
        "Academia": wrap("Academia", {"courses": {"type": "array"}, "groups": {"type": "array"}, "publications": {"type": "array"}, "research": {"type": "array"}}),
        "AcademiaSection": wrap("AcademiaSection", {"section": {"type": "string"}, "items": {"type": "array"}}),
        "AcademiaItem": wrap("AcademiaItem", {"item": {"type": "object"}}),
        "OrgEntity": {
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "type": {"type": "string"},
                "talk_ids": {"type": "array", "items": {"type": "string"}, "description": "Talks in /api/v1/talks.json that name this person. Omitted when none are linked."},
                "event_ids": {"type": "array", "items": {"type": "string"}, "description": "Events those talks belong to. Omitted when none are linked."},
                "talks": {"type": "array", "description": "id, title, video_url, and event_id and date when the talk has them."},
                "affiliations": {"type": "array", "description": "One organisation per talk, only when the talk page stated it. Each item has organisation, talk_id, source_url, source_name and retrieved_at. role and date are present when the page stated them. An affiliation without a source is omitted."},
            },
        },
        "OrgChart": wrap("OrgChart", {"entities": {"type": "array", "items": {"$ref": "#/components/schemas/OrgEntity"}}, "relations": {"type": "array"}, "regulation": {"type": "array"}}),
        "Relation": {"type": "object"},
        "RelationList": wrap("RelationList", {"relations": {"type": "array"}}),
        "RegulationList": wrap("RegulationList", {"regulation": {"type": "array"}}),
        "ProfileList": wrap("ProfileList", {"profiles": {"type": "array"}}),
        "ImageList": wrap("ImageList", {"images": {"type": "array"}}),
        "IllustrationList": wrap("IllustrationList", {"images": {"type": "array"}, "policy": {"type": "string"}}),
        "ChangelogList": wrap("ChangelogList", {"entries": {"type": "array"}}),
        "Rules": wrap("Rules", {"available": {"type": "boolean"}, "checked": {"type": "string"}}),
        "ArticleArchive": wrap("ArticleArchive", {"articles": {"type": "array"}}),
        "SiteMeta": wrap("SiteMeta", {
            "languages": {"type": "array"},
            "countries": {"type": "array"},
            "cors": {"type": "object"},
            "ios": {
                "type": "object",
                "description": "Public TestFlight invite for the Nordic Crypto iOS app. Not an App Store listing. apple_tv is English. apple_tv_i18n has every site language, including en.",
                "properties": {
                    "name": {"type": "string", "example": "Nordic Crypto"},
                    "distribution": {"type": "string"},
                    "label": {"type": "string"},
                    "url": {"type": "string"},
                    "note": {"type": "string"},
                    "apple_tv": {"type": "string"},
                    "apple_tv_i18n": {"type": "object"},
                },
            },
            "social": {
                "type": "object",
                "description": "Nordic Crypto brand accounts. telegram is https://t.me/nordiccryptochat. x is https://x.com/xcryptonordic. label and name are English. name_i18n has nn, nb, sv, da, fi and is. Other languages use name.",
                "properties": {
                    "note": {"type": "string"},
                    "telegram": {"type": "object", "properties": {
                        "label": {"type": "string", "example": "Telegram"},
                        "name": {"type": "string", "example": "Nordic Crypto on Telegram"},
                        "name_i18n": {"type": "object"},
                        "url": {"type": "string", "example": "https://t.me/nordiccryptochat"},
                    }},
                    "x": {"type": "object", "properties": {
                        "label": {"type": "string", "example": "X"},
                        "name": {"type": "string", "example": "Follow Nordic Crypto on X"},
                        "name_i18n": {"type": "object"},
                        "url": {"type": "string", "example": "https://x.com/xcryptonordic"},
                        "handle": {"type": "string", "example": "@xcryptonordic"},
                    }},
                },
            },
            "urls": {"type": "object", "description": "github, newsletter, rss, telegram and x, plus the API bases. newsletter is the signup page on this site. rss is the English story feed."},
        }),
        "LanguageList": wrap("LanguageList", {
            "count": {"type": "integer"},
            "languages": {"type": "array", "items": {"type": "object"}},
        }),
        "GeoLanguage": wrap("GeoLanguage", {
            "note": {"type": "string"},
            "default": {"type": "string"},
            "by_country": {"type": "object", "additionalProperties": {"type": "string"}},
            "order": {"type": "array", "items": {"type": "string"}},
        }),
        "MarketTicker": {
            "type": "object",
            "required": ["symbol", "base", "quote", "exchange", "fetched_at", "source_url"],
            "properties": {
                "id": {"type": "string"},
                "symbol": {"type": "string", "description": "BASE-QUOTE, for example BTC-NOK.", "example": "BTC-NOK"},
                "exchange_symbol": {"type": "string", "description": "The pair id used by the exchange."},
                "base": {"type": "string"},
                "quote": {"type": "string", "enum": ["NOK", "SEK", "DKK", "EUR"]},
                "last": {"type": "string", "nullable": True, "description": "Last price as published, decimal string. Null when the exchange does not publish a last trade."},
                "bid": {"type": "string", "nullable": True, "description": "Best bid as published, decimal string."},
                "ask": {"type": "string", "nullable": True, "description": "Best ask as published, decimal string."},
                "exchange": {"type": "object", "required": ["id", "name", "country"], "properties": {
                    "id": {"type": "string"}, "name": {"type": "string"}, "country": {"type": "string"},
                }},
                "fetched_at": {"type": "string", "description": "When Nordic Crypto fetched this row, ISO 8601 UTC."},
                "source_url": {"type": "string", "description": "Exchange URL the figure was read from."},
                "volume_base": {"type": "string", "nullable": True, "description": "Base-asset volume as published. Null when the exchange omits it. Firi's volume is stored here; that payload does not name a 24-hour window. Not treated as zero when missing."},
                "volume_quote": {"type": "string", "nullable": True, "description": "Quote-currency volume as published, window not named. Null when omitted."},
                "volume_base_24h": {"type": "string", "nullable": True, "description": "Base-asset volume over the last 24 hours. Set only when the exchange names that window (NBX). Not added to volume_base."},
                "volume_quote_24h": {"type": "string", "nullable": True, "description": "Quote-currency volume over the last 24 hours (NBX). The unit is this pair's quote (NOK, SEK, DKK or EUR)."},
                "high": {"type": "string", "nullable": True},
                "low": {"type": "string", "nullable": True},
                "change_pct": {"type": "string", "nullable": True},
                "exchange_time": {"type": "string", "nullable": True, "description": "Timestamp from the exchange payload, when it sends one."},
            },
        },
        "MarketLogo": {
            "type": "object",
            "nullable": True,
            "description": "Present when cryptocurrency-icons (CC0-1.0) includes this asset. Null fields on the parent when it does not. Nordic Crypto does not draw substitutes.",
            "properties": {
                "format": {"type": "string", "example": "svg"},
                "source": {"type": "string"},
                "source_url": {"type": "string"},
                "version": {"type": "string"},
                "license": {"type": "string", "example": "CC0-1.0"},
                "license_name": {"type": "string"},
                "license_url": {"type": "string"},
                "authors": {"type": "string"},
                "attribution": {"type": "string"},
            },
        },
        "MarketVolume": {
            "type": "object",
            "description": "Sums of like volume fields inside one pair. Fields are not mixed. A null sum means nobody published that field.",
            "properties": {
                "volume_base": {"type": "string", "nullable": True, "description": "Sum of volume_base. Unit: base asset. Window not named."},
                "volume_base_exchanges": {"type": "integer"},
                "volume_quote": {"type": "string", "nullable": True, "description": "Sum of volume_quote. Unit: quote currency. Window not named."},
                "volume_quote_exchanges": {"type": "integer"},
                "volume_base_24h": {"type": "string", "nullable": True, "description": "Sum of volume_base_24h. Unit: base asset over the last 24 hours."},
                "volume_base_24h_exchanges": {"type": "integer"},
                "volume_quote_24h": {"type": "string", "nullable": True, "description": "Sum of volume_quote_24h. Unit: quote currency over the last 24 hours."},
                "volume_quote_24h_exchanges": {"type": "integer"},
                "units": {"type": "object"},
            },
        },
        "MarketAggregate": {
            "type": "object",
            "required": ["symbol", "base", "quote", "currency", "exchange_count", "updated_at", "method", "price", "last", "mid", "min", "max", "contributors", "volume"],
            "properties": {
                "symbol": {"type": "string", "example": "BTC-NOK", "description": "BASE-QUOTE. One bucket per quote currency."},
                "base": {"type": "string"},
                "name": {"type": "string", "nullable": True},
                "quote": {"type": "string", "enum": ["NOK", "SEK", "DKK", "EUR"]},
                "currency": {"type": "string", "description": "Same as quote. NOK is never combined with EUR, SEK or DKK."},
                "updated_at": {"type": "string", "nullable": True, "description": "Newest fetched_at among the contributors, ISO 8601 UTC."},
                "oldest_fetched_at": {"type": "string", "nullable": True},
                "exchange_count": {"type": "integer", "description": "How many exchanges quoted this pair."},
                "method": {"type": "string", "nullable": True, "enum": ["mean_last", "mean_bid_ask_mid"], "description": "mean_last when any last exists, otherwise mean_bid_ask_mid. Null when no price can be formed."},
                "method_note": {"type": "string"},
                "price": {"type": "string", "nullable": True, "description": "Equals last, or mid when no last exists."},
                "min": {"type": "string", "nullable": True, "description": "Lowest value in the same series as price."},
                "max": {"type": "string", "nullable": True, "description": "Highest value in the same series as price."},
                "last": {"type": "string", "nullable": True, "description": "Arithmetic mean of published last prices. Null if none."},
                "last_count": {"type": "integer"},
                "last_min": {"type": "string", "nullable": True},
                "last_max": {"type": "string", "nullable": True},
                "mid": {"type": "string", "nullable": True, "description": "Arithmetic mean of (bid+ask)/2 where both were published. Not blended into last."},
                "mid_count": {"type": "integer"},
                "mid_min": {"type": "string", "nullable": True},
                "mid_max": {"type": "string", "nullable": True},
                "vwap": {"type": "string", "nullable": True, "description": "Always null. Volume windows are not comparable, so there is no VWAP."},
                "volume_used_for_price": {"type": "boolean"},
                "volume": {"$ref": "#/components/schemas/MarketVolume"},
                "contributors": {"type": "array", "items": {"type": "object"}},
                "logo_url": {"type": "string", "nullable": True, "description": "Absolute GitHub Pages URL of the SVG, or null."},
                "logo_url_custom_domain": {"type": "string", "nullable": True},
                "logo_path": {"type": "string", "nullable": True, "description": "Site-relative path, for example api/v1/markets/logos/btc.svg."},
                "logo": {"$ref": "#/components/schemas/MarketLogo"},
            },
        },
        "MarketCatalogue": wrap("MarketCatalogue", {
            "disclaimer": {"type": "string"},
            "count": {"type": "integer"},
            "aggregated_count": {"type": "integer"},
            "aggregation": {"type": "object", "description": "How last, mid, volume and logos are derived."},
            "exchanges": {"type": "array"},
            "skipped": {"type": "array", "description": "Venues checked and left out because they have no public ticker."},
            "tickers": {"type": "array", "items": {"$ref": "#/components/schemas/MarketTicker"}},
            "aggregated": {"type": "array", "items": {"$ref": "#/components/schemas/MarketAggregate"}},
            "urls": {"type": "object"},
            "refresh": {"type": "object"},
        }),
        "MarketExchange": wrap("MarketExchange", {"exchange": {"type": "object"}, "count": {"type": "integer"}, "tickers": {"type": "array", "items": {"$ref": "#/components/schemas/MarketTicker"}}}),
        "MarketAsset": wrap("MarketAsset", {
            "symbol": {"type": "string"},
            "name": {"type": "string", "nullable": True},
            "count": {"type": "integer"},
            "tickers": {"type": "array", "items": {"$ref": "#/components/schemas/MarketTicker"}},
            "aggregated": {"type": "array", "items": {"$ref": "#/components/schemas/MarketAggregate"}, "description": "One object per quote currency for this asset."},
            "aggregation": {"type": "object"},
            "logo_url": {"type": "string", "nullable": True},
            "logo_url_custom_domain": {"type": "string", "nullable": True},
            "logo_path": {"type": "string", "nullable": True},
            "logo": {"$ref": "#/components/schemas/MarketLogo"},
        }),
        "MarketAggregated": wrap("MarketAggregated", {
            "kind": {"type": "string", "example": "markets-aggregated"},
            "count": {"type": "integer"},
            "aggregation": {"type": "object"},
            "pairs": {"type": "array", "items": {"$ref": "#/components/schemas/MarketAggregate"}},
            "urls": {"type": "object"},
        }),
    }


def llms_txt(feed, index):
    news = feed.abs("api/v1/news.json")
    letters = feed.abs("api/v1/newsletters.json")
    one = None
    for ep in index["endpoints"]:
        if ep["id"] == "api-v1-newsletters":
            one = ep.get("example_url")
    lines = [
        f"# {SITE_NAME}",
        "",
        "> Public JSON feed of Nordic crypto news, newsletters, events, talks, sources, academia and the who's who. No account. No API key.",
        "",
        f"{SITE_NAME} covers Norway, Sweden, Denmark, Finland and Iceland. "
        "The sign-off is The Nordic Crypto team. Kaupr (kaupr.io) is a news source only and is never a sponsor. "
        "Summaries are ours, in English, with translations in summary_i18n (nn, nb, sv, da, fi, is) when published. "
        "Other site languages fall back to English until a translation is published. "
        "title on a news item is the source headline. title_en and title_i18n are our headlines. "
        "The pages show the page-language headline first and the source headline underneath when they differ.",
        "",
        "GitHub Pages sends Access-Control-Allow-Origin: * on every JSON file, so a browser can fetch them from any site. "
        "Use the file name (index.json). A directory URL does not serve the JSON.",
        "",
        f"Public site: {feed.base}",
        "Absolute URLs in this file use that origin, at the domain root.",
        "",
        "## Start here",
        "",
        f"- [Discovery]({feed.abs('api/v1/index.json')}): every endpoint, counts, and example URLs.",
        f"- [Human docs]({feed.abs('api/')}): the same catalogue as a web page.",
        f"- [OpenAPI JSON]({feed.abs('api/v1/openapi.json')}): OpenAPI 3.0.",
        f"- [OpenAPI YAML]({feed.abs('api/v1/openapi.yaml')}): the same document.",
        f"- [API catalog]({feed.abs('.well-known/api-catalog')}): RFC 9727 linkset. A .json copy is at {feed.abs('.well-known/api-catalog.json')}.",
        f"- [Site meta]({feed.abs('api/v1/meta.json')}): languages, countries, page list, CORS, and brand social accounts.",
        f"- Telegram: {SITE_TELEGRAM_URL} (`social.telegram`). X: {SITE_X_URL} (`social.x`, also `urls.x`). `name` is English. `name_i18n` has nn, nb, sv, da, fi and is. Other languages use `name`.",
        "- iOS app: public TestFlight invite in `ios`. `apple_tv` is English. `apple_tv_i18n` has every site language. The Nordic Crypto TestFlight version especially supports Apple TV. No App Store listing.",
        f"- [Languages]({feed.abs('api/v1/languages.json')}): site UI languages (code, native name, English name, rtl, home).",
        f"- [Geo language]({feed.abs('api/v1/geo-language.json')}): country to default language. An IP guess; the nc_lang cookie wins.",
        "- Browser notifications: opt-in Web Push. The Worker `GET /api/push/feed.json` repeats each publish as one batch (title, summary, URL). APNs is not implemented. Subscriptions are not in this API.",
        "",
        "## Market prices",
        "",
        "Prices from Nordic exchanges with a public ticker (Firi and Norwegian Block Exchange in Norway, Coinmotion in Finland). "
        "Market data, not investment advice. Each ticker has symbol, base, quote, last, bid and ask when the exchange publishes them, "
        "plus exchange id, name and country, fetched_at and source_url. "
        "volume_base is the base asset with no named window (Firi). volume_base_24h and volume_quote_24h are the last 24 hours (NBX), in the base asset and in the quote currency. "
        "A missing volume is null, not zero. Quotes are NOK, SEK, DKK or EUR. "
        "A failed exchange is an error with a timestamp and no price. "
        "The file is fetched again when the site is built, and a GitHub Actions job rewrites it on gh-pages about hourly. "
        "Durable URL: https://raw.githubusercontent.com/jQrgen/nordic-crypto/gh-pages/api/v1/markets.json",
        "",
        "Aggregated prices are one row per pair: /api/v1/markets/aggregated.json. "
        "BTC-NOK is not averaged with BTC-EUR. last is the arithmetic mean of published last prices. "
        "mid is the mean of (bid+ask)/2 and is not mixed into last. "
        "min and max follow the same series as price. There is no VWAP, because the volume windows do not match. "
        "Volume sums add only the same field inside the same pair. "
        "logo_url points at api/v1/markets/logos/{symbol}.svg when cryptocurrency-icons (CC0-1.0) includes that asset, and is null otherwise. "
        "The same pairs, with the logo, are on /api/v1/markets/by-asset/{symbol}.json.",
        "",
        "```",
        f"curl -fsS {feed.abs('api/v1/markets.json')}",
        f"curl -fsS {feed.abs('api/v1/markets/aggregated.json')}",
        "curl -fsS https://raw.githubusercontent.com/jQrgen/nordic-crypto/gh-pages/api/v1/markets.json",
        "```",
        "",
        "## Events",
        "",
        "Luma calendars use the public iCal subscribe URL (the Subscribe link). "
        "City pages, category pages and the Luma discover API are not used: the terms only allow publicly supported interfaces, "
        "and the official API needs Luma Plus and only covers calendars you administer. "
        "An individual Luma event page is schema.org JSON-LD. "
        "Eventbrite organizers and venues use the v3 API when EVENTBRITE_TOKEN is set on the server. "
        "The token is not in this feed. Without it, the event page JSON-LD is used. "
        "The same title, date and venue is listed once. Finished events are kept. "
        "Kaupr is a news source only and is never an event sponsor.",
        "",
        "## Fetch news and newsletters",
        "",
        "```",
        f"curl -fsS {news}",
        f"curl -fsS {letters}",
    ]
    if one:
        lines.append(f"curl -fsS {one}")
    lines += [
        "```",
        "",
        "A single news item is api/v1/news/{id}.json (the id is on each item). "
        "primary_source is the outlet we lead with. also_covered_by is every other outlet on the same event. "
        "sources lists them with the primary first. coverage.by_country and coverage.by_source_type "
        "(national, regional, official, international) are the counts and shares, and empty types are included as zero. "
        "html_url is our coverage page. url is the primary outlet. ",
        "A single newsletter issue is api/v1/newsletters/{id}.json and includes plain text and HTML. "
        "Country slices: api/v1/news/by-country/NO.json (also SE, DK, FI, IS).",
        "",
        "## Source logos",
        "",
        f"Each outlet in {feed.abs('api/v1/sources.json')} has logo_url (absolute PNG or WebP URL, never SVG, or null) and logo "
        "(kind, file_url (the original, SVG or WebP), raster_url (same as logo_url), source_url, author, license, license_url, credit, or null). "
        "Each news item has source_logo_url, the logo of the outlet that published the headline. "
        "Logos come from Wikimedia Commons (with licence and author) or the publisher's own site. "
        "They are the publishers' trademarks, shown only to identify the source of a headline. "
        "A logo is null until the editor has checked it.",
        "",
        "## Talks",
        "",
        "Public talks on bitcoin, cryptocurrencies and blockchain in the Nordic countries, newest first. "
        "description is ours. title, dates, duration, channel and speakers come from the platform at source_url. "
        "A missing detail is null. embed is true only when that platform's oEmbed response includes a player. "
        "Country files use NO, SE, DK, FI, IS, FO (Faroe Islands), GL (Greenland) and AX (Åland).",
        "",
        "```",
        f"curl -fsS {feed.abs('api/v1/talks.json')}",
        "```",
        "",
        "## Endpoints",
        "",
    ]
    for ep in index["endpoints"]:
        lines.append(f"- [{ep['path']}]({ep['url']}): {ep['summary']}")
    lines += [
        "",
        "## Not in this feed",
        "",
        "Drafts, the editor queue, rejected stories, reader tips, newsletter subscriber addresses, analytics tokens, and private personal data are not published.",
        "",
        f"## {SIGN_OFF}",
        "",
    ]
    return "\n".join(lines)


def api_catalog(feed):
    return {
        "linkset": [{
            "anchor": feed.base,
            "service-desc": [
                {"href": feed.abs("api/v1/openapi.json"), "type": "application/openapi+json"},
                {"href": feed.abs("api/v1/openapi.yaml"), "type": "application/yaml"},
            ],
            "service-doc": [
                {"href": feed.abs("api/"), "type": "text/html"},
                {"href": feed.abs("llms.txt"), "type": "text/plain"},
            ],
            "status": [
                {"href": feed.abs("api/v1/index.json"), "type": "application/json"},
            ],
        }]
    }


def head_links(base):
    b = base if base.endswith("/") else base + "/"
    return (
        f'<link rel="describedby" href="{b}api/v1/index.json" type="application/json">'
        f'<link rel="service-desc" href="{b}api/v1/openapi.json" type="application/openapi+json">'
        f'<link rel="describedby" href="{b}llms.txt" type="text/plain">'
    )


def docs_fragment(index):
    b = index["bases"]["github_pages"]
    def row(ep):
        return (
            f"<tr><td>GET</td><td><a href=\"{html.escape(ep['url'])}\"><code>{html.escape(ep['path'])}</code></a></td>"
            f"<td>{html.escape(ep['summary'])}</td></tr>"
        )
    rows = "\n".join(row(ep) for ep in index["endpoints"])
    news = html.escape(b + "api/v1/news.json")
    letters = html.escape(b + "api/v1/newsletters.json")
    one = ""
    for ep in index["endpoints"]:
        if ep.get("example_url") and ep["id"] == "api-v1-newsletters":
            one = ep["example_url"]
    one_line = f"\ncurl -fsS {one}" if one else ""
    counts = index.get("counts") or {}
    return f"""<style>
.api-docs pre{{overflow:auto;padding:10px 12px;background:#f6f7f8;border:1px solid #e5e7eb;font-size:13px}}
.api-docs code{{font-size:.92em}}
.api-docs td:first-child{{white-space:nowrap}}
.api-docs, .api-docs p, .api-docs li, .api-docs td, .api-docs th{{text-align:left}}
</style>
<div class="api-docs">
<h1>Nordic Crypto data API</h1>
<p class="lead">A public JSON feed of the site, for apps and for other tools. No account and no API key. It is regenerated whenever the site is built.</p>
<p>Version 1. {html.escape(str(counts.get('news', 0)))} news items, {html.escape(str(counts.get('newsletters', 0)))} newsletter issues, {html.escape(str(counts.get('events', 0)))} events and {html.escape(str(counts.get('talks', 0)))} talks in this build. Generated {html.escape(index.get('generated_at') or '')}.</p>
<h2>Start here</h2>
<ul>
<li><a href="{html.escape(b)}api/v1/index.json">Discovery</a> — every endpoint and example URL.</li>
<li><a href="{html.escape(b)}api/v1/openapi.json">OpenAPI</a> (also <a href="{html.escape(b)}api/v1/openapi.yaml">YAML</a>).</li>
<li><a href="{html.escape(b)}llms.txt">llms.txt</a> — plain-language instructions.</li>
<li><a href="{html.escape(b)}.well-known/api-catalog">API catalog</a> (RFC 9727 linkset; <a href="{html.escape(b)}.well-known/api-catalog.json">.json copy</a>).</li>
</ul>
<h2>Fetch news and a newsletter</h2>
<pre>curl -fsS {news}
curl -fsS {letters}{html.escape(one_line)}</pre>
<p>Absolute URLs use the public site, at the domain root: <code>{html.escape(b)}api/v1/news.json</code>.</p>
<h2>Market prices</h2>
<p>Nordic exchange prices are market data, not investment advice. <a href="{html.escape(b)}api/v1/markets.json"><code>/api/v1/markets.json</code></a> lists each pair with symbol, base, quote, last, bid and ask when the exchange publishes them, the exchange id, name and country, <code>fetched_at</code>, the source URL, and volume when the exchange published it. <code>volume_base</code> is the base asset with no named window (Firi). <code>volume_base_24h</code> and <code>volume_quote_24h</code> are the last 24 hours (NBX). A missing volume is null, not zero. Quotes are NOK, SEK, DKK and EUR. One exchange is <a href="{html.escape(b)}api/v1/markets/firi.json"><code>/api/v1/markets/{{exchange}}.json</code></a> (<code>firi</code>, <code>nbx</code>, <code>coinmotion</code>). One asset is <a href="{html.escape(b)}api/v1/markets/by-asset/BTC.json"><code>/api/v1/markets/by-asset/{{symbol}}.json</code></a>. Venues without a public ticker are listed under <code>skipped</code> and are not given a made-up price.</p>
<p><a href="{html.escape(b)}api/v1/markets/aggregated.json"><code>/api/v1/markets/aggregated.json</code></a> is one row per pair. BTC-NOK is not averaged with BTC-EUR. <code>last</code> is the arithmetic mean of published last prices. <code>mid</code> is the mean of (bid+ask)/2 and is not mixed into <code>last</code>. <code>price</code> equals <code>last</code> when any last exists, otherwise <code>mid</code>. <code>min</code> and <code>max</code> use that same series. There is no VWAP. Volume is summed only inside the same field and the same pair. <code>logo_url</code> is an SVG from <a href="https://github.com/spothq/cryptocurrency-icons" rel="noopener">cryptocurrency-icons</a> (CC0 1.0) when that set includes the asset, served at <code>/api/v1/markets/logos/{{symbol}}.svg</code>, and null otherwise. The per-asset file repeats <code>aggregated</code> and the logo.</p>
<p>The build fetches the exchanges. <code>.github/workflows/markets-refresh.yml</code> rewrites the JSON on gh-pages about once an hour, including the aggregated file and the icons. The markets page reloads this file, and refreshes Firi and Coinmotion in the browser because those APIs send <code>Access-Control-Allow-Origin: *</code>. NBX does not, so those rows follow the file. The same document on the gh-pages branch: <a href="https://raw.githubusercontent.com/jQrgen/nordic-crypto/gh-pages/api/v1/markets.json">raw.githubusercontent.com/jQrgen/nordic-crypto/gh-pages/api/v1/markets.json</a>.</p>
<pre>curl -fsS {html.escape(b)}api/v1/markets.json
curl -fsS {html.escape(b)}api/v1/markets/aggregated.json</pre>
<h2>Talks</h2>
<p>Public talks on bitcoin, cryptocurrencies and blockchain held in Norway, Sweden, Denmark, Finland, Iceland, the Faroe Islands, Greenland and Åland are at <a href="{html.escape(b)}api/v1/talks.json"><code>/api/v1/talks.json</code></a>, newest first. One talk is <code>/api/v1/talks/{{id}}.json</code>. One country is <a href="{html.escape(b)}api/v1/talks/by-country/NO.json"><code>/api/v1/talks/by-country/{{country}}.json</code></a> (<code>NO</code>, <code>SE</code>, <code>DK</code>, <code>FI</code>, <code>IS</code>, <code>FO</code>, <code>GL</code>, <code>AX</code>). <code>description</code> is ours. <code>title</code>, dates, duration, channel and speakers come from the platform at <code>source_url</code>. A field the platform did not state is null. <code>embed</code> is true only when that platform's oEmbed response includes a player. The HTML page loads the player after a click: YouTube via youtube-nocookie.com, Vimeo via player.vimeo.com. <code>event_id</code> and <code>calendar_event_id</code> are the same event id when the talk is linked. That event is <code>/api/v1/events/{{id}}.json</code> (and <code>/api/v1/events/previous.json</code> when it is a past event) and the page is <code>/calendar/{{id}}/</code>. <code>talk_ids</code> on the event lists those talks. <code>unlink_reason</code> is set when the video page did not state a day or a place, and <code>event_id</code> is then null. <code>speaker_ids</code> are who's who ids in the same order as <code>speakers</code>. The person, at <code>/api/v1/orgchart/{{id}}.json</code>, lists those talks and any affiliation the talk page stated.</p>
<h2>Several outlets, one story</h2>
<p>A story keeps one primary outlet. Other outlets that covered the same event are in <code>also_covered_by</code>. <code>sources</code> lists the primary first, then the others. Each outlet has <code>outlet</code>, <code>outlet_name</code>, <code>url</code>, <code>title</code> (that outlet's headline), <code>published</code>, <code>lang</code>, <code>country</code>, <code>source_type</code> and <code>logo</code>. <code>source_type</code> is <code>national</code>, <code>regional</code> (regional and local), <code>official</code> (justice and official: police, prosecutors, courts, regulators) or <code>international</code>. <code>coverage.count</code> is the number of outlets. <code>coverage.by_country</code> and <code>coverage.by_source_type</code> are the counts and shares for the bars. Every source type is present, including a count of zero. <code>html_url</code> is our page for that story. <code>url</code> is the primary outlet. Kaupr stays a news source only.</p>
<h2>Events</h2>
<p>Upcoming and past events are in <a href="{html.escape(b)}api/v1/events.json"><code>/api/v1/events.json</code></a>. Luma calendars are taken from the public Subscribe iCal URL on each event source (<code>ics</code>). Luma city pages, category pages and the discover API are not used. An individual Luma event page is schema.org JSON-LD. Eventbrite organizers and venues are read with the v3 API when the server has <code>EVENTBRITE_TOKEN</code>. That token is not in this feed and is not committed. Without it, the event page JSON-LD is used. The same title, date and venue is one event. Finished events stay in the feed. Kaupr is never a sponsor.</p>
<h2>Languages</h2>
<p>English is the default field (<code>summary</code>, <code>title</code>, <code>text</code>). Translations that we have published sit in <code>summary_i18n</code>, <code>title_i18n</code>, <code>subtitle_i18n</code>, <code>note_i18n</code>, <code>text_i18n</code> and <code>about_i18n</code>, keyed by <code>nn</code>, <code>nb</code>, <code>sv</code>, <code>da</code>, <code>fi</code> and <code>is</code>. Other site languages use the English field until a translation is published. On a news item, <code>title</code> stays the source headline, <code>title_en</code> is our English headline and <code>title_i18n</code> is our headline in the Nordic site languages. The pages show the page-language headline first and the source headline underneath when they differ. Each outlet's own headline, inside <code>sources</code>, stays in that outlet's language. Dates are ISO 8601.</p>
<p><a href="{html.escape(b)}api/v1/languages.json"><code>/api/v1/languages.json</code></a> lists every site language with <code>code</code>, <code>native_name</code>, <code>english_name</code>, <code>rtl</code>, <code>html_lang</code> and <code>home</code>. <a href="{html.escape(b)}api/v1/geo-language.json"><code>/api/v1/geo-language.json</code></a> is the country-to-language guess used on a first visit. The IP country comes from the tipworker <code>GET /api/geo</code> (Cloudflare <code>request.cf.country</code>). Nothing is stored. The <code>nc_lang</code> cookie, set by the language switcher, always wins.</p>
<h2>Source logos</h2>
<p>Each outlet in <a href="{html.escape(b)}api/v1/sources.json"><code>/api/v1/sources.json</code></a> has <code>logo_url</code> (absolute PNG or WebP URL, never SVG, or <code>null</code>) and <code>logo</code> (<code>kind</code>, <code>file_url</code> (the original, SVG or WebP), <code>raster_url</code> (same as <code>logo_url</code>), <code>source_url</code>, <code>author</code>, <code>license</code>, <code>license_url</code>, <code>credit</code>, or <code>null</code>). Each news item has <code>source_logo_url</code>, so an app can show the outlet's logo next to the headline. Logos come from Wikimedia Commons (with the licence) or the publisher's own site. They are the publishers' trademarks, shown only to identify the source of a headline. A logo stays <code>null</code> until the editor has checked it.</p>
<h2>CORS</h2>
<p>GitHub Pages sends <code>Access-Control-Allow-Origin: *</code> on these files, so a page on another site can <code>fetch()</code> them. GitHub Pages does not apply a custom headers file. Use the <code>.json</code> file name; opening a directory does not return the JSON.</p>
<h2>Editorial</h2>
<p>The sign-off is The Nordic Crypto team. Kaupr (kaupr.io) is a news source only and is never a sponsor. Nothing here is investment advice.</p>
<h2>Brand accounts</h2>
<p><code>ios</code> in <a href="{html.escape(b)}api/v1/meta.json"><code>/api/v1/meta.json</code></a> is the public TestFlight invite for the Nordic Crypto iOS app. There is no App Store listing. <code>apple_tv</code> says the TestFlight version especially supports Apple TV. <code>apple_tv_i18n</code> has that short sentence in every site language. The brand name stays Nordic Crypto.</p>
<p><a href="{html.escape(b)}api/v1/meta.json"><code>/api/v1/meta.json</code></a> includes <code>social</code> for the iOS app. <code>social.telegram</code> is the Nordic Crypto chat at <a href="{SITE_TELEGRAM_URL}">{html.escape(SITE_TELEGRAM_URL)}</a>. <code>social.x</code> is the brand account at <a href="{SITE_X_URL}">{html.escape(SITE_X_URL)}</a> (<code>@xcryptonordic</code>), also listed as <code>urls.x</code>. <code>urls.telegram</code> repeats the chat URL. <code>urls.rss</code> is the English story feed at <a href="{html.escape(b)}rss.xml"><code>/rss.xml</code></a>. Each language home has its own <code>rss.xml</code>. <code>urls.newsletter</code> is the signup page on this site. <code>label</code> is the short name (<code>Telegram</code>, <code>X</code>). <code>name</code> is the English link text. <code>name_i18n</code> has <code>nn</code>, <code>nb</code>, <code>sv</code>, <code>da</code>, <code>fi</code> and <code>is</code>. Other site languages use <code>name</code>.</p>
<h2>Browser notifications</h2>
<p>When <code>workers/push/public.json</code> has a Worker URL, a button at the bottom of each page is Web Push. Until then the page says the service is not switched on and does not call a Worker. Subscriptions live on a Cloudflare Worker, not in this static feed. After a publish, <code>GET /api/push/feed.json</code> on that Worker lists the same batches (title, short summary, URL, country, and translations when we have them). One publish is one batch. The document says <code>"apns": "not implemented"</code>: Apple Push Notification service is out of scope. An iOS app can poll the feed. The Worker URL is set when <code>workers/push/</code> is deployed; it is not a path on this site. Subscriptions are not in the feed. This API's <a href="{html.escape(b)}api/v1/news.json"><code>/api/v1/news.json</code></a> remains the full published list.</p>
<h2>Endpoints</h2>
<div class="tablewrap"><table class="list"><thead><tr><th>Method</th><th>Path</th><th>Returns</th></tr></thead><tbody>
{rows}
</tbody></table></div>
<h2>Not included</h2>
<p>Drafts, the editor queue, rejected stories, reader tips, newsletter subscriber addresses, the analytics token, and private personal data are not in this feed. An unknown id is a normal site 404, not a JSON error.</p>
<p class="meta">Field names in version 1 stay. New fields may appear. A breaking change would use a new path.</p>
</div>"""


def standalone_docs(fragment, base):
    b = base if base.endswith("/") else base + "/"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Data API – {SITE_NAME}</title>
<meta name="description" content="{html.escape(DOCS_DESC)}">
<link rel="canonical" href="{b}api/">
{head_links(b)}
</head><body>
{fragment}
</body></html>
"""


def main():
    preview = "--preview" in sys.argv
    ctx = repo_context(preview)
    site = os.environ.get("NC_SITE_DIR") or os.path.join(ROOT, "site")
    ev = ctx["events"]
    events = ev[0] if isinstance(ev, tuple) else ev
    write(
        site,
        preview=preview,
        base=site_url.BASE,
        items=ctx["items"],
        events=events,
        entities=ctx["ents"],
        relations=ctx["rels"],
        org_updated=(ctx.get("org") or {}).get("updated"),
        regulation=(ctx.get("org") or {}).get("regulation") or [],
        caveats=(ctx.get("org") or {}).get("caveats") or [],
        sources_cfg=ctx["cfg"],
        news_updated=(ctx.get("news") or {}).get("updated"),
    )

if __name__ == "__main__":
    main()
