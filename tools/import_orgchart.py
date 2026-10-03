#!/usr/bin/env python3
"""Builds data/orgchart.json for Nordic Crypto (run by build.py on every build):
  1) Norway: the editor-approved Kryptonytt export (queue/approved.json -> industrikart.export) parsed by
     tools/import_industrikart_no.py, then translated with data/no_en.json. Rows without an English entry are LEFT OUT.
  2) Sweden, Denmark, Finland, Iceland, Nordic: data/orgchart_nordic.json (curated, English, sourced).
Status: every row is "pending" until the editor approves it in queue/approved.json:
  "org": {"approve": [ids], "approve_countries": ["NO", ...], "reject": [ids]}
Rows without at least one source are dropped."""
import json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P = lambda *a: os.path.join(ROOT, *a)
def load(p, d=None):
    try: return json.load(open(p, encoding="utf-8"))
    except FileNotFoundError: return d
SEC = {"offentlig": "public", "privat": "private"}
def main():
    subprocess.run([sys.executable, P("tools", "import_industrikart_no.py")], check=True)
    raw = load(P("data", "orgchart_no_raw.json"), {"entities": [], "relations": []}); en = load(P("data", "no_en.json"))
    nordic = load(P("data", "orgchart_nordic.json")); ap = (load(P("queue", "approved.json"), {}) or {}).get("org", {})
    ok_ids, ok_c, rej = set(ap.get("approve", [])), set(ap.get("approve_countries", [])), set(ap.get("reject", []))
    out, skipped = [], []
    for e in raw["entities"]:
        t = en["e"].get(e["id"])
        if t is None: skipped.append(e["id"]); continue
        x = {"id": e["id"], "name": t.get("name", e["name"]), "type": "person" if e["type"] == "person" else "organisation",
             "sector": SEC[e["sector"]], "country": t.get("country", "NO"), "description": t["description"] if "description" in t else e.get("description"),
             "sources": [dict(s, title=en["source_titles"].get(s.get("title"), s.get("title")), source_name=en["source_titles"].get(s.get("source_name"), s.get("source_name"))) for s in e.get("sources", [])],
             "image": e.get("image"), "caveat": e.get("caveat", False), "origin": "Kryptonytt industry map (approved for Norway)"}
        if e["type"] == "person": x.update(org=e.get("org"), role=t.get("role", e.get("role")), profile_url=e.get("profile_url"))
        else: x["group"] = en["group_override"].get(e["id"]) or en["groups"].get(e.get("group"), e.get("group"))
        if x["description"] and any(w in x["description"] for w in (" ifølge ", " ikke ", " eller ", " blir ")): skipped.append(e["id"] + " (untranslated text)"); continue
        out.append(x)
    ids = {x["id"] for x in out}
    for e in nordic["entities"]:
        if e["id"] in ids: print(f"orgchart: duplicate id {e['id']}", file=sys.stderr); continue
        out.append(dict(e, origin="Nordic Crypto research")); ids.add(e["id"])
    out = [e for e in out if e.get("sources")]
    for e in out:
        e["status"] = "rejected" if e["id"] in rej else ("published" if (e["id"] in ok_ids or e["country"] in ok_c) else "pending")
    rels = []
    for r in raw.get("relations", []) + nordic.get("relations", []):
        if r["from"] in ids and r["to"] in ids and r.get("sources"):
            rels.append(dict(r, status="rejected" if r["id"] in rej else ("published" if r["id"] in ok_ids or {next(e["country"] for e in out if e["id"] == r["from"]), next(e["country"] for e in out if e["id"] == r["to"])} <= ok_c else "pending")))
    res = {"updated": nordic.get("checked"), "no_export_date": raw.get("updated"), "entities": out, "relations": rels,
           "regulation": nordic.get("regulation", []), "caveats": en.get("caveats", []) + nordic.get("caveats", [])}
    json.dump(res, open(P("data", "orgchart.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    by = {}
    for e in out: by[e["country"]] = by.get(e["country"], 0) + 1
    print(f"orgchart: {len(out)} rows {by}, {sum(e['type']=='person' for e in out)} people, {len(rels)} relations, "
          f"{sum(e['status']=='published' for e in out)} approved / {sum(e['status']=='pending' for e in out)} pending" + (f"; left out: {skipped}" if skipped else ""))
if __name__ == "__main__": main()
