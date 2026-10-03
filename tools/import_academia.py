#!/usr/bin/env python3
"""Builds data/academia.json from the researcher's list /workspace/nordic-crypto-research/academia.md (editor rulings
applied in its Status column) plus our own DOI-checked publication candidates (state/academia_seed_own.json).
Only rows whose status is APPROVED are shown on /academia/ (preview and public alike); pending, unverified and OUT rows
stay in the JSON for the editor but never reach the page."""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD = sys.argv[1] if len(sys.argv) > 1 else "/workspace/nordic-crypto-research/academia.md"
INST_C = {"NTNU": "NO", "University of Oslo": "NO", "NHH": "NO", "KTH": "SE", "Uppsala University": "SE", "Aalto University (FITech)": "FI",
          "Tampere University": "FI", "University of Eastern Finland": "FI", "University of Vaasa": "FI", "Reykjavík University": "IS"}
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
T = tables(open(MD, encoding="utf-8").read())
def sec(prefix): return next((v for k, v in T.items() if k.startswith(prefix)), [])
courses = []
for r in sec("courses"):
    st, note = status(r["Status"]); code, _, name = r["Course"].partition(" ")
    courses.append({"country": r["Country"], "institution": r["Institution"], "code": code, "name": name, "level": r["Level / credits"],
                    "term": r["Term"], "about": r["Why included (course page)"], "url": r["Source"], "source": r["Source"], "checked": r["Checked"],
                    "status": st, "editor_note": note})
for r in sec("borderline"):
    st, note = status(r["Reason"]); code, _, name = r["Course"].partition(" ")
    if not r["Source"].startswith("http"): continue
    row = {"country": INST_C.get(r["Institution"], "?"), "institution": r["Institution"], "code": code, "name": name, "level": "", "term": "",
           "about": "", "url": r["Source"], "source": r["Source"], "checked": "2026-10-03", "status": st, "editor_note": note}
    if r["Course"].startswith("CS-AJ0100"):   # editor: include, 1 ECTS, labelled as a past run
        row.update(level="Basic, 1 ECTS, online, English", term="Past run: 1 Aug 2025 – 16 Jul 2026 (ended)",
                   about="Introductory, non-coding course on blockchain and its business uses: NFTs, ICOs, security tokens, smart contracts and private DLT systems.")
    courses.append(row)
research = []
for r in sec("research"):
    st, note = status(r["Status"])
    research.append({"country": r["Country"], "name": r["Group"], "institution": r["Institution"], "about": r["Focus (own page)"], "url": r["Source"],
                     "source": r["Source"], "checked": r["Checked"], "status": st, "editor_note": note})
groups = []
for r in sec("student"):
    st, note = status(r["Status"])
    groups.append({"country": r["Country"], "name": r["Association"], "institution": r["Institution"], "activity": r["Last dated activity found"],
                   "active": False, "url": r["Source"], "source": r["Source"], "checked": r["Checked"], "status": st, "editor_note": note})
own = json.load(open(os.path.join(ROOT, "state", "academia_seed_own.json"), encoding="utf-8"))
pubs = [dict(p, status="pending", editor_note="awaiting editor (DOI checked at doi.org on " + p["checked"] + ")") for p in own.get("publications", [])]
out = {"updated": "2026-10-03", "source_list": MD,
       "rules": ["A course is listed only when blockchain or crypto is a substantial part of the syllabus on its own course page.",
                 "Every DOI or research-database link is checked before it is listed.",
                 "A student group is marked active only with dated activity in the last 12 months; otherwise inactive.",
                 "Every row carries a source, a check date and a status. Only editor-approved rows are shown."],
       "courses": courses, "groups": groups, "publications": pubs, "research": research}
json.dump(out, open(os.path.join(ROOT, "data", "academia.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for k in ("courses", "groups", "publications", "research"):
    print(k, {s: sum(r["status"] == s for r in out[k]) for s in ("approved", "pending", "unverified", "out")})
