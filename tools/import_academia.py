#!/usr/bin/env python3
"""Builds data/academia.json from:
  1) the researcher's editor list (academia.md Status column) when present;
  2) research/academia/works.json — curated Nordic theses/papers (master/phd/paper/conference);
  3) optional local seed state/academia_seed_own.json (DOI-checked papers; gitignored).

On a clean clone, academia.md may be missing (box-only researcher path). In that case courses /
groups / research are preserved from the existing data/academia.json, and publications are rebuilt
from research/academia/works.json (+ any local seed).

Only rows whose status is APPROVED are shown on /academia/; pending/unverified/OUT stay in JSON.
"""
import json, os, re, sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD = sys.argv[1] if len(sys.argv) > 1 else "/workspace/nordic-crypto-research/academia.md"
WORKS = os.path.join(ROOT, "research", "academia", "works.json")
SEED = os.path.join(ROOT, "state", "academia_seed_own.json")
OUT = os.path.join(ROOT, "data", "academia.json")
CHECKED = date.today().isoformat()
INST_C = {"NTNU": "NO", "University of Oslo": "NO", "NHH": "NO", "KTH": "SE", "Uppsala University": "SE",
          "Aalto University (FITech)": "FI", "Tampere University": "FI", "University of Eastern Finland": "FI",
          "University of Vaasa": "FI", "Reykjavík University": "IS"}

def status(s):
    s = s.strip(); u = s.upper()
    if u.startswith("APPROVED"): return "approved", s
    if u.startswith("OUT"): return "out", s
    if u.startswith("UNVERIFIED"): return "unverified", s
    return "pending", s

def tables(md):
    sec, out = None, {}
    for line in md.splitlines():
        if line.startswith("## "): sec = line[3:].strip().lower(); continue
        if line.startswith("|") and not re.match(r"^\|[-| ]+\|$", line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            out.setdefault(sec, []).append(cells)
    return {k: [dict(zip(v[0], r)) for r in v[1:]] for k, v in out.items()}

def load_json(path, default=None):
    if not os.path.exists(path): return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)

prev = load_json(OUT, {}) or {}
courses, groups, research = [], [], []
source_list = None

if os.path.exists(MD):
    source_list = MD
    T = tables(open(MD, encoding="utf-8").read())
    def sec(prefix): return next((v for k, v in T.items() if k.startswith(prefix)), [])
    for r in sec("courses"):
        st, note = status(r["Status"]); code, _, name = r["Course"].partition(" ")
        courses.append({"country": r["Country"], "institution": r["Institution"], "code": code, "name": name,
                        "level": r["Level / credits"], "term": r["Term"], "about": r["Why included (course page)"],
                        "url": r["Source"], "source": r["Source"], "checked": r["Checked"], "status": st, "editor_note": note})
    for r in sec("borderline"):
        st, note = status(r["Reason"]); code, _, name = r["Course"].partition(" ")
        if not r["Source"].startswith("http"): continue
        row = {"country": INST_C.get(r["Institution"], "?"), "institution": r["Institution"], "code": code, "name": name,
               "level": "", "term": "", "about": "", "url": r["Source"], "source": r["Source"], "checked": "2026-10-03",
               "status": st, "editor_note": note}
        if r["Course"].startswith("CS-AJ0100"):
            row.update(level="Basic, 1 ECTS, online, English", term="Past run: 1 Aug 2025 – 16 Jul 2026 (ended)",
                       about="Introductory, non-coding course on blockchain and its business uses: NFTs, ICOs, security tokens, smart contracts and private DLT systems.")
        courses.append(row)
    for r in sec("research"):
        st, note = status(r["Status"])
        research.append({"country": r["Country"], "name": r["Group"], "institution": r["Institution"],
                         "about": r["Focus (own page)"], "url": r["Source"], "source": r["Source"],
                         "checked": r["Checked"], "status": st, "editor_note": note})
    for r in sec("student"):
        st, note = status(r["Status"])
        groups.append({"country": r["Country"], "name": r["Association"], "institution": r["Institution"], "about": "",
                       "activity": r["Last dated activity found"], "active": st == "approved", "url": r["Source"],
                       "source": r["Source"], "checked": r["Checked"], "status": st, "editor_note": note})
else:
    # Clean clone / CI: keep previously committed courses/groups/research.
    courses = list(prev.get("courses") or [])
    groups = list(prev.get("groups") or [])
    research = list(prev.get("research") or [])
    source_list = "research/academia/works.json (+ preserved data/academia.json courses/groups/research)"

def pub_key(p):
    doi = (p.get("doi") or "").strip().lower()
    if doi: return ("doi", doi)
    return ("url", (p.get("url") or "").strip().lower())

pubs_map = {}

# 1) Curated catalogue (tracked)
works = load_json(WORKS, []) or []
for w in works:
    url = w.get("url") or (f"https://doi.org/{w['doi']}" if w.get("doi") else None)
    if not url or not w.get("title"): continue
    typ = w.get("type") or "paper"
    if typ not in ("master", "phd", "paper", "conference"): typ = "paper"
    row = {
        "country": w.get("country"),
        "title": w["title"],
        "authors": w.get("authors") or [],
        "institution": w.get("institution") or "",
        "year": w.get("year"),
        "type": typ,
        "venue": w.get("venue") or {"master": "Master's thesis", "phd": "PhD dissertation",
                                    "paper": "Journal article", "conference": "Conference paper"}.get(typ, ""),
        "doi": w.get("doi") or None,
        "url": url,
        "db": url,
        "db_name": w.get("source_db") or "open catalogue",
        "source": url,
        "about": w.get("relevance") or "",
        "keywords": w.get("keywords") or [],
        "checked": CHECKED,
        "status": "pending",
        "editor_note": "awaiting editor (sourced catalogue research/academia/works.json)",
        "origin": "research/academia/works.json",
    }
    pubs_map[pub_key(row)] = row

# 2) Optional local DOI seed (gitignored) — fills gaps / refreshes OpenAlex metadata
own = load_json(SEED, {}) or {}
for p in own.get("publications") or []:
    doi = p.get("doi")
    url = p.get("url") or (f"https://doi.org/{doi}" if doi else None)
    if not url: continue
    row = dict(p)
    row.setdefault("type", "paper")
    row.setdefault("url", url)
    row.setdefault("source", url)
    row["status"] = "pending"
    row["editor_note"] = "awaiting editor (DOI seed checked " + str(p.get("checked") or CHECKED) + ")"
    row["origin"] = row.get("origin") or "state/academia_seed_own.json"
    k = pub_key(row)
    # Prefer seed metadata when DOI already present (richer OpenAlex fields), else add
    if k not in pubs_map or (doi and not pubs_map[k].get("doi")):
        pubs_map[k] = row
    elif doi:
        # merge authors/venue from seed if catalogue row is thinner
        cur = pubs_map[k]
        if (not cur.get("authors")) and row.get("authors"): cur["authors"] = row["authors"]
        if (not cur.get("venue")) and row.get("venue"): cur["venue"] = row["venue"]
        if row.get("db"): cur["db"] = row["db"]; cur["db_name"] = row.get("db_name") or cur.get("db_name")

pubs = sorted(pubs_map.values(), key=lambda r: (-(r.get("year") or 0), r.get("country") or "", r.get("title") or ""))

out = {
    "updated": CHECKED,
    "source_list": source_list,
    "works_catalogue": "research/academia/works.json",
    "rules": [
        "A course is listed only when blockchain or crypto is a substantial part of the syllabus on its own course page.",
        "Every DOI or research-database link is sourced before it is listed; no fabricated citations.",
        "A student group is marked active only with dated activity in the last 12 months; otherwise inactive.",
        "Every row carries a source, a check date and a status. Only editor-approved rows are shown.",
        "Publication types: master | phd | paper | conference (from research/academia/works.json).",
    ],
    "courses": courses,
    "groups": groups,
    "publications": pubs,
    "research": research,
}
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for k in ("courses", "groups", "publications", "research"):
    print(k, {s: sum(r.get("status") == s for r in out[k]) for s in ("approved", "pending", "unverified", "out")}, "n=", len(out[k]))
from collections import Counter
print("pub types", Counter(p.get("type") for p in pubs))
print("pub countries", Counter(p.get("country") for p in pubs))
