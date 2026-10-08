#!/usr/bin/env python3
"""Nordic crypto books (data/books.json), used by the /books/ page in build.py and by /api/v1/books.json.

A row is a published book about bitcoin, crypto or blockchain, written by a Nordic author or about the
Nordic countries. Every row names the catalogue or publisher page where the title, authors, year and
publisher were checked (source). Titles stay in the original language. about is our own one-line
description in English. No cover images: covers are the publisher's copyright, and the page stays compact.

Not listed: self-published spam, books that are not about crypto, and unpublished manuscripts.
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "books.json")
COUNTRY_ORDER = ["NO", "SE", "DK", "FI", "IS", "FO", "GL", "AX"]
LANGUAGES = ("nn", "nb", "sv", "da", "fi", "is", "fo", "kl", "en")
REQUIRED = ("id", "title", "authors", "year", "publisher", "language", "country", "about", "source", "source_name")
FIELDS = ("id", "title", "subtitle", "original_title", "authors", "author_role", "year", "publisher",
          "language", "country", "isbn", "about", "source", "source_name", "more_sources")


def raw():
    with open(PATH, encoding="utf-8") as fh:
        return json.load(fh)


def rows():
    """Every book, all fields present (None when unknown), by country, then newest year first, then title."""
    order = {c: i for i, c in enumerate(COUNTRY_ORDER)}
    out = []
    for r in raw().get("books") or []:
        row = {k: r.get(k) for k in FIELDS}
        row["authors"] = list(row["authors"] or [])
        row["more_sources"] = list(row["more_sources"] or [])
        out.append(row)
    return sorted(out, key=lambda r: (order.get(r["country"], 99), -(r["year"] or 0), (r["title"] or "").lower()))


def updated():
    return raw().get("updated")


def problems():
    """Data checks for the test and the build log. Empty list means the file is fine."""
    bad, seen = [], set()
    for r in raw().get("books") or []:
        rid = r.get("id") or "?"
        for k in REQUIRED:
            if r.get(k) in (None, "", []):
                bad.append(f"{rid}: missing {k}")
        if rid in seen:
            bad.append(f"{rid}: duplicate id")
        seen.add(rid)
        if r.get("language") not in LANGUAGES:
            bad.append(f"{rid}: language {r.get('language')}")
        if r.get("country") not in COUNTRY_ORDER:
            bad.append(f"{rid}: country {r.get('country')}")
        for u in [r.get("source")] + list(r.get("more_sources") or []):
            if not str(u or "").startswith("https://"):
                bad.append(f"{rid}: source must be https")
        isbn = r.get("isbn")
        if isbn:
            ok = len(isbn) == 13 and isbn.isdigit() and (10 - sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(isbn[:12])) % 10) % 10 == int(isbn[12])
            if not ok:
                bad.append(f"{rid}: ISBN-13 check digit")
        if not isinstance(r.get("year"), int):
            bad.append(f"{rid}: year must be a number")
    return bad
