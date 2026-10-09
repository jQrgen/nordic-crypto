#!/usr/bin/env python3
"""Open-source developers (data/developers.json), used by the /developers/ page in build.py and by /api/v1/developers.json.

A row is a technical person in Nordic crypto (developer, CTO, protocol engineer, researcher who writes code) with
public crypto-related code: at least one public, non-fork crypto repo of their own, or merged commits or pull
requests in a public crypto project (Bitcoin, Nexa, Ethereum and other chains, wallets, Lightning, nodes, explorers,
smart contracts, DeFi, cryptographic protocols used in crypto, crypto libraries and tooling). Unrelated open source
(web apps, dotfiles, game mods, non-crypto libraries) does not count on its own.

Every row names where its Nordic link is shown (nordic_source) and the date it was checked. Only public professional
information: name as shown on the profile, role, organisation, country, profile links and the crypto repos or
projects. No emails, addresses or other private details.

Approval: the same model as the who's who people and profile links. A row is "pending" until the editor sets
status "published" in data/developers.json (review "ready_for_owner": jQrgen decides, never the editor alone).
rows(preview=False) returns only published rows; the --preview build also shows pending rows, marked.
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "developers.json")
COUNTRY_ORDER = ["NO", "SE", "DK", "FI", "IS", "FO", "GL", "AX"]
STATUSES = ("pending", "published", "rejected")
REVIEWS = ("editor", "ready_for_owner")
PROFILE_KINDS = ("github", "gitlab", "codeberg", "sourcehut")
PROFILE_HOSTS = {"github": "https://github.com/", "gitlab": "https://gitlab.com/", "codeberg": "https://codeberg.org/", "sourcehut": "https://sr.ht/"}
REQUIRED = ("id", "name", "role", "country", "profiles", "notable", "nordic_source", "checked", "status")
FIELDS = ("id", "name", "role", "org", "org_id", "whoswho_id", "country", "profiles", "website", "notable",
          "nordic_source", "checked", "status", "review", "note")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def raw():
    with open(PATH, encoding="utf-8") as fh:
        return json.load(fh)


def updated():
    return raw().get("updated")


def _sort_key(r):
    order = {c: i for i, c in enumerate(COUNTRY_ORDER)}
    return (order.get(r["country"], 99), r["name"].lower())


def all_rows():
    """Every row with every field (None when unknown), by country, then name. Rejected rows are left out."""
    out = []
    for r in raw().get("people") or []:
        if r.get("status") == "rejected":
            continue
        row = {k: r.get(k) for k in FIELDS}
        row["profiles"] = list(row["profiles"] or [])
        row["notable"] = list(row["notable"] or [])
        out.append(row)
    return sorted(out, key=_sort_key)


def rows(preview=False):
    """What a build may show: published rows, plus pending rows in a --preview build."""
    return [r for r in all_rows() if r["status"] == "published" or (preview and r["status"] == "pending")]


def counts():
    rs = all_rows()
    return {"published": sum(r["status"] == "published" for r in rs), "pending": sum(r["status"] == "pending" for r in rs),
            "ready_for_owner": sum(r["status"] == "pending" and r.get("review") == "ready_for_owner" for r in rs)}


def notable_label(n):
    """Short English text for one notable item, used by the API (the page builds its own, translated)."""
    if n.get("kind") == "repo":
        return n["name"]
    bits = []
    if n.get("merged_prs"):
        bits.append(f'{n["merged_prs"]} merged pull requests')
    if n.get("commits"):
        bits.append(f'{n["commits"]} commits')
    return f'{n["project"]} ({", ".join(bits)})' if bits else n["project"]


def problems():
    """Data checks for the test and the build log. Empty list means the file is fine."""
    bad, seen = [], set()
    data = raw()
    if EMAIL.search(json.dumps(data, ensure_ascii=False)):
        bad.append("an email address is in the data")
    for r in data.get("people") or []:
        rid = r.get("id") or "?"
        for k in REQUIRED:
            if r.get(k) in (None, "", [], {}):
                bad.append(f"{rid}: missing {k}")
        if rid in seen:
            bad.append(f"{rid}: duplicate id")
        seen.add(rid)
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", rid):
            bad.append(f"{rid}: id must be lower-case words joined by -")
        if r.get("country") not in COUNTRY_ORDER:
            bad.append(f"{rid}: country {r.get('country')}")
        if r.get("status") not in STATUSES:
            bad.append(f"{rid}: status {r.get('status')}")
        if r.get("review", "editor") not in REVIEWS:
            bad.append(f"{rid}: review {r.get('review')}")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(r.get("checked") or "")):
            bad.append(f"{rid}: checked must be YYYY-MM-DD")
        for p in r.get("profiles") or []:
            host = PROFILE_HOSTS.get(p.get("kind"))
            if not host or not str(p.get("url") or "").startswith(host):
                bad.append(f"{rid}: profile {p.get('kind')} {p.get('url')}")
        src = r.get("nordic_source") or {}
        if not str(src.get("url") or "").startswith("https://") or not src.get("note"):
            bad.append(f"{rid}: nordic_source needs an https url and a note")
        notable = r.get("notable") or []
        if len(notable) > 3:
            bad.append(f"{rid}: more than 3 notable items")
        for n in notable:
            if n.get("kind") == "repo":
                if not n.get("name") or not str(n.get("url") or "").startswith("https://"):
                    bad.append(f"{rid}: repo needs name and https url")
            elif n.get("kind") == "contrib":
                if not n.get("project") or not str(n.get("url") or "").startswith("https://"):
                    bad.append(f"{rid}: contrib needs project and https url")
                if not (n.get("commits") or n.get("merged_prs")):
                    bad.append(f"{rid}: contrib {n.get('project')} has no commits or merged pull requests")
            else:
                bad.append(f"{rid}: notable kind {n.get('kind')}")
        if r.get("website") and not str(r["website"]).startswith("https://"):
            bad.append(f"{rid}: website must be https")
    return bad


if __name__ == "__main__":
    for msg in problems():
        print(msg)
    print(counts())
