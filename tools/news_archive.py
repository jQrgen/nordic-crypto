#!/usr/bin/env python3
"""Historical news archive, plus the scientific works already on the academia page.

News articles live in data/archive/news/<year>.json (see schema.json). One file per
publication year, back to 2009. Researchers add rows. This module does not fetch them.

Master's theses, project theses and papers are not copied into those files. They are
read from data/academia.json, the same publication rows the /academia/ page shows
(status "approved" only). work_type stays master, project, paper or conference.
A conference row is a paper. PhD dissertations stay on the academia page.

The public JSON is /api/v1/archive/news/page-N.json, newest first.
"""
import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import i18n  # noqa: E402
NEWS_DIR = os.path.join(ROOT, "data", "archive", "news")
ACADEMIA = os.path.join(ROOT, "data", "academia.json")
PAGE_SIZE = 20
# Same translation codes as a news item: every site language except English.
# English lives in title_en and summary.
I18N_LANGS = tuple(l for l in i18n.ALL_LANGS if l != "en")
COUNTRIES = ("NO", "SE", "DK", "FI", "IS", "FO", "GL", "AX", "NORDIC", "EU")
# conference is included: those rows are papers. phd stays on /academia/ only.
ACADEMIC_TYPES = ("master", "project", "paper", "conference")
YEAR_FILE = re.compile(r"^(\d{4})\.json$")
REQUIRED = ("id", "title", "source", "url", "published", "country", "language", "summary")


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default


def _i18n(raw):
    out = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in I18N_LANGS and isinstance(value, str) and value.strip():
                out[key] = value.strip()
    return out


def _published(value):
    """ISO timestamp, or None when it cannot be read."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(dt.timezone.utc).isoformat()


def news_rows(directory=None):
    """Articles from data/archive/news/<year>.json. Newest last; public_items() sorts."""
    directory = directory or NEWS_DIR
    rows = []
    if not os.path.isdir(directory):
        return rows
    for name in sorted(os.listdir(directory)):
        match = YEAR_FILE.match(name)
        if not match:
            continue
        data = load(os.path.join(directory, name), {}) or {}
        for raw in data.get("articles") or []:
            if not isinstance(raw, dict):
                continue
            published = _published(raw.get("published"))
            year = int(published[:4]) if published else None
            title_en = (raw.get("title_en") or "").strip() or None
            rows.append({
                "type": "news",
                "id": str(raw.get("id") or "").strip(),
                "title": (raw.get("title") or "").strip(),
                "title_en": title_en,
                "title_i18n": _i18n(raw.get("title_i18n")),
                "source": (raw.get("source") or "").strip(),
                "source_name": (raw.get("source_name") or raw.get("source") or "").strip(),
                "url": (raw.get("url") or "").strip(),
                "archive_url": (raw.get("archive_url") or "").strip() or None,
                "published": published or "",
                "published_precision": "datetime",
                "country": raw.get("country") or "",
                "language": (raw.get("language") or "").strip(),
                "summary": (raw.get("summary") or "").strip(),
                "summary_i18n": _i18n(raw.get("summary_i18n")),
                "work_type": None,
                "authors": [],
                "year": year,
            })
    return rows


def academic_rows(path=None):
    """Approved master's theses, project theses and papers from the academia file.

    A conference paper is included (it is a paper). PhD dissertations are not.
    published is 1 January of the catalogue year, UTC, because the catalogue records a year.
    """
    data = load(path or ACADEMIA, {}) or {}
    rows = []
    for raw in data.get("publications") or []:
        if not isinstance(raw, dict):
            continue
        if raw.get("status") != "approved":
            continue
        kind = raw.get("type") or ""
        if kind not in ACADEMIC_TYPES:
            continue
        year = raw.get("year")
        if not isinstance(year, int):
            continue
        url = (raw.get("url") or "").strip()
        if not url.startswith("https://"):
            continue
        title = (raw.get("title") or "").strip()
        if not title:
            continue
        title_en = (raw.get("title_en") or "").strip() or None
        ident = academic_id(raw)
        rows.append({
            "type": "academic",
            "id": ident,
            "title": title,
            "title_en": title_en,
            "title_i18n": _i18n(raw.get("title_i18n")),
            "source": (raw.get("institution") or "").strip() or (raw.get("db_name") or "").strip(),
            "source_name": (raw.get("institution") or "").strip() or (raw.get("db_name") or "").strip(),
            "url": url,
            "archive_url": None,
            "published": f"{year:04d}-01-01T00:00:00+00:00",
            "published_precision": "year",
            "country": raw.get("country") or "",
            "language": (raw.get("language") or "").strip(),
            "summary": (raw.get("about") or "").strip(),
            "summary_i18n": _i18n(raw.get("summary_i18n")),
            "work_type": kind,
            "authors": [a for a in (raw.get("authors") or []) if isinstance(a, str) and a.strip()],
            "year": year,
        })
    return rows


def academic_id(raw):
    """Stable id from the handle or DOI, so a rebuild does not rename the row."""
    url = raw.get("url") or ""
    handle = re.search(r"11250/(\d+)", url)
    if handle:
        return "ac-" + handle.group(1)
    doi = (raw.get("doi") or "").strip().lower()
    if doi:
        return "ac-" + re.sub(r"[^a-z0-9]+", "-", doi).strip("-")[:80]
    tail = re.sub(r"^https?://", "", url).strip("/")
    return "ac-" + re.sub(r"[^A-Za-z0-9]+", "-", tail).strip("-")[:80]


def public_items(news_dir=None, academia_path=None):
    """News and academic rows together, newest published first."""
    rows = news_rows(news_dir) + academic_rows(academia_path)
    rows.sort(key=lambda r: (r.get("published") or "", r.get("id") or ""), reverse=True)
    return rows


def paginate(items, page_size=None):
    """Pages of items. An empty archive is one empty page, so page-1.json exists."""
    size = page_size or PAGE_SIZE
    if size < 1:
        size = PAGE_SIZE
    if not items:
        return [[]]
    return [items[i:i + size] for i in range(0, len(items), size)]


def problems(directory=None):
    """Data checks for the year files. An empty directory is fine. Academic rows are checked apart."""
    directory = directory or NEWS_DIR
    bad, seen = [], set()
    if not os.path.isdir(directory):
        return bad
    for name in sorted(os.listdir(directory)):
        if name == "schema.json":
            continue
        match = YEAR_FILE.match(name)
        if not match:
            bad.append(f"{name}: file name must be <year>.json")
            continue
        file_year = int(match.group(1))
        data = load(os.path.join(directory, name), {}) or {}
        if data.get("year") not in (None, file_year):
            bad.append(f"{name}: year {data.get('year')} does not match the file name")
        for raw in data.get("articles") or []:
            if not isinstance(raw, dict):
                bad.append(f"{name}: article is not an object")
                continue
            rid = raw.get("id") or "?"
            for key in REQUIRED:
                if raw.get(key) in (None, ""):
                    bad.append(f"{rid}: missing {key}")
            if rid in seen:
                bad.append(f"{rid}: duplicate id")
            seen.add(rid)
            if raw.get("country") not in COUNTRIES:
                bad.append(f"{rid}: country {raw.get('country')}")
            if not str(raw.get("url") or "").startswith("https://"):
                bad.append(f"{rid}: url must be https")
            archive = raw.get("archive_url")
            if archive not in (None, "") and not str(archive).startswith("https://"):
                bad.append(f"{rid}: archive_url must be https or null")
            published = _published(raw.get("published"))
            if not published:
                bad.append(f"{rid}: published must be ISO 8601 with a timezone")
            elif int(published[:4]) != file_year:
                bad.append(f"{rid}: published year is not {file_year}")
            for field in ("title_i18n", "summary_i18n"):
                extra = raw.get(field) or {}
                if not isinstance(extra, dict):
                    bad.append(f"{rid}: {field} must be an object")
                    continue
                for code in extra:
                    if code not in I18N_LANGS:
                        bad.append(f"{rid}: {field} key {code} is not a translation language")
    return bad


def academic_problems(path=None):
    """Approved academic rows that would be dropped, so a verified thesis cannot vanish quietly."""
    data = load(path or ACADEMIA, {}) or {}
    bad = []
    for raw in data.get("publications") or []:
        if not isinstance(raw, dict) or raw.get("status") != "approved":
            continue
        if raw.get("type") not in ACADEMIC_TYPES:
            continue
        rid = raw.get("title") or "?"
        if not str(raw.get("url") or "").startswith("https://"):
            bad.append(f"{rid}: academic url must be https")
        if not isinstance(raw.get("year"), int):
            bad.append(f"{rid}: academic year must be a number")
        if raw.get("country") not in COUNTRIES:
            bad.append(f"{rid}: academic country {raw.get('country')}")
    return bad
