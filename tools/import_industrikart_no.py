#!/usr/bin/env python3
"""Crypto Nordic copy of Kryptonytt's importer (unchanged parsing; output goes to data/orgchart_no_raw.json, Norwegian text,
which tools/import_orgchart.py translates via data/no_en.json).
Bygger data/orgchart.json på nytt ved hver bygging fra:
  1) researcherens redaktørgodkjente eksport (queue/approved.json -> industrikart.export), alle «ifølge …»-forbehold beholdes ordrett
  2) data/orgchart_extra.json – aktører og koblinger fra redaktørgodkjente nyhetssaker (kuratert)
  3) data/images.json – fritt lisensierte bilder (Wikimedia Commons) per person-id
Rader som ikke kan tolkes trygt, hoppes over og rapporteres."""
import json, os, re, sys, unicodedata, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P = lambda *a: os.path.join(ROOT, *a)
def load(p, d=None):
    try: return json.load(open(p, encoding="utf-8"))
    except FileNotFoundError: return d
def slug(s):
    s = s.replace("ø", "o").replace("Ø", "O").replace("æ", "ae").replace("Æ", "AE").replace("å", "a").replace("Å", "A")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
DOM = {"stortinget.no": "Stortinget", "regjeringen.no": "Regjeringen", "finanstilsynet.no": "Finanstilsynet", "norges-bank.no": "Norges Bank",
 "nrk.no": "NRK", "kaupr.io": "Kaupr", "shifter.no": "Shifter", "bankshift.no": "BankShift", "lovdata.no": "Lovdata", "nkom.no": "Nkom",
 "esma.europa.eu": "ESMA", "eba.europa.eu": "EBA", "globenewswire.com": "GlobeNewswire", "bpinorge.no": "Bitcoinpolitisk institutt", "finansnorge.no": "Finans Norge",
 "seetee.io": "Seetee", "barebitcoin.no": "Bare Bitcoin", "firi.com": "Firi", "nbx.com": "NBX", "storage.mfn.se": "K33 børsmelding (MFN)", "mfn.se": "MFN",
 "okonomi24.com": "Økonomi24", "img8.custompublish.com": "Økokrim årsrapport 2025 (PDF)", "okokrim.custompublish.com": "Økokrim", "inyheter.no": "iNyheter",
 "finanswatch.no": "Finanswatch", "sparebank1.no": "SpareBank 1", "kommunikasjon.ntb.no": "NTB Kommunikasjon", "no.linkedin.com": "LinkedIn (Norges Bank)",
 "api3.oslo.oslobors.no": "Oslo Børs NewsWeb (vedlegg)", "newsweb.oslobors.no": "Oslo Børs NewsWeb", "data.stortinget.no": "Stortinget"}
def src(u, date):
    d = urllib.parse.urlparse(u).netloc.lower().removeprefix("www.")
    name = DOM.get(d) or next((v for k, v in DOM.items() if d.endswith("." + k)), d)
    return {"url": u, "title": name, "source_name": name, "date": date}
# kanoniske organisasjoner: institusjonsnavn (eller prefiks før « – ») -> (id, visningsnavn, sektor, gruppe)
CANON = [
 (r"^Stortinget – finanskomiteen", "stortinget-finanskomiteen", "Stortinget – finanskomiteen", "Storting og regjering"),
 (r"^(Finansdepartementet – Finansmarkedsavdelingen|FMA)\b", "fma", "Finansdepartementet – Finansmarkedsavdelingen (FMA)", "Storting og regjering"),
 (r"^Finansdepartementet", "finansdepartementet", "Finansdepartementet", "Storting og regjering"),
 (r"^Digitaliserings- og forvaltningsdepartementet", "dfd", "Digitaliserings- og forvaltningsdepartementet", "Storting og regjering"),
 (r"^Energidepartementet", "energidepartementet", "Energidepartementet", "Storting og regjering"),
 (r"^Finanstilsynet", "finanstilsynet", "Finanstilsynet", "Tilsyn og etater"),
 (r"^Norges Banks tokeniseringsnettverk", "norges-bank-tokenisering", "Norges Banks tokeniseringsnettverk", None),
 (r"^Norges Bank", "norges-bank", "Norges Bank", "Tilsyn og etater"),
 (r"^Skatteetaten", "skatteetaten", "Skatteetaten", "Tilsyn og etater"),
 (r"^Økokrim", "okokrim", "Økokrim (inkl. Enheten for finansiell etterretning/FIU)", "Tilsyn og etater"),
 (r"^Nkom-registeret", "nkom-kryptoutvinnere", "Kryptoutvinnere i Nkom-registeret", None),
 (r"^Nkom", "nkom", "Nkom (Nasjonal kommunikasjonsmyndighet)", "Tilsyn og etater"),
 (r"^NVE", "nve", "NVE", "Tilsyn og etater"), (r"^Statnett", "statnett", "Statnett", None),
 (r"^ESMA", "esma", "ESMA (EU)", "EU"), (r"^EBA", "eba", "EBA (EU)", "EU"),
 (r"^EØS: MiCA", "kryptoeiendelsloven", "Kryptoeiendelsloven (MiCA i norsk rett)", "Regelverk"),
 (r"^Firi", "firi", "Firi", None), (r"^(Norwegian Block Exchange|NBX)", "nbx", "NBX (Norwegian Block Exchange)", None),
 (r"^K33", "k33", "K33", None), (r"^Bare Bitcoin", "bare-bitcoin", "Bare Bitcoin", None), (r"^Týr", "tyr-markets", "Týr Markets", None),
 (r"^DNB", "dnb", "DNB", None), (r"^Seetee", "seetee", "Seetee", None), (r"^Schibsted Ventures", "schibsted-ventures", "Schibsted Ventures", None),
 (r"^Tydal", "tydal-data-center", "Tydal Data Center (Bitdeer)", None), (r"^Bitcoinpolitisk", "bpi", "Bitcoinpolitisk institutt Norge", None),
 (r"^Finans Norge", "finans-norge", "Finans Norge", None), (r"^Shifter", "shifter", "Shifter / BankShift (Shifter Media)", None), (r"^Kaupr", "kaupr", "Kaupr", None),
]
PUBLIC_SEG = ("Regulering og myndigheter",)
PARTY = r"(Ap|H|FrP|Sp|SV|R|V|KrF|MDG|alle Ap)"
def canon(inst):
    for rx, i, name, grp in CANON:
        if re.search(rx, inst): return i, name, grp
    base = re.sub(r"\s*\(.*?\)\s*$", "", inst).replace(" AS", "").strip()
    return slug(base), base, None
def split_names(navn, rolle):
    """-> liste av (navn, rolle, notat) eller None hvis raden ikke er personer"""
    if not navn or navn.strip() in ("–", "-") or "ikke bekreftet" in navn: return None
    if "," in navn: return None  # lister (selskaper/flere personer) beskrives i organisasjonens tekst
    names = [n.strip() for n in navn.split(" / ")]; roles = [r.strip() for r in rolle.split(" / ")]
    if len(roles) != len(names): roles = [rolle] * len(names)
    out = []
    for n, r in zip(names, roles):
        note = None; m = re.match(r"^(.*?)\s*\((.*)\)\s*$", n)
        if m:
            n, par = m.group(1).strip(), m.group(2).strip()
            if re.fullmatch(PARTY, par): r = f"{r} ({par})"
            elif re.match(r"^fra ", par): r = f"{r} ({par})"
            else: note = par[0].upper() + par[1:] + "."
        out.append((n, r[0].upper() + r[1:], note))
    return out

def main():
    ap = load(P("queue", "approved.json"), {}); cfg = ap.get("industrikart", {})
    exp = load(cfg.get("export", ""), None)
    imgs = load(P("data", "images.json"), {}); extra = {"entities": [], "relations": []}  # Crypto Nordic: no Norwegian news extras
    E, R, skipped = {}, [], []
    excl = set(cfg.get("exclude_institutions", []))
    for row in (exp or {}).get("rader", []):
        if row.get("status") not in ("godkjent", "godkjent med forbehold") or row["institusjon"] in excl: skipped.append(row["institusjon"]); continue
        if row.get("rolle", "").startswith("Øvrige medlemmer"): skipped.append(row["institusjon"] + " (øvrige medlemmer)"); continue
        oid, oname, grp = canon(row["institusjon"]); pub = row["segment"] in PUBLIC_SEG
        srcs = [src(u, row.get("sjekket")) for u in row.get("kilder", [])]
        if not srcs: skipped.append(row["institusjon"] + " (mangler kilde)"); continue
        o = E.setdefault(oid, {"id": oid, "name": oname, "type": "organisasjon", "sector": "offentlig" if pub else "privat",
                               "group": grp or ("Tilsyn og etater" if pub else row["segment"]), "description": "", "sources": [], "image": None, "caveat": row["status"] == "godkjent med forbehold"})
        for s in srcs:
            if s["url"] not in {x["url"] for x in o["sources"]}: o["sources"].append(s)
        people = split_names(row.get("navn", ""), row.get("rolle", ""))
        sub = row["institusjon"].split(" – ", 1)[1].replace("styret", "Finanstilsynets styre") if " – " in row["institusjon"] and oid not in ("stortinget-finanskomiteen", "nkom-kryptoutvinnere") else None
        if people:
            for n, r, note in people:
                pid = slug(n)
                role = f"{r}, {sub}" if sub and sub.lower() not in r.lower() else r
                desc = " ".join(x for x in [note, row.get("paavirkning") if row["status"] == "godkjent med forbehold" else None] if x)
                E[pid] = {"id": pid, "name": n, "type": "person", "sector": o["sector"], "org": oid, "role": role, "description": desc or None,
                          "profile_url": srcs[0]["url"], "sources": srcs, "image": imgs.get(pid), "caveat": row["status"] == "godkjent med forbehold"}
            if not o["description"] and row.get("paavirkning") and row["paavirkning"] != "Som over" and not sub:
                o["description"] = row["paavirkning"]
        else:
            lead = "" if not row.get("navn") or row["navn"].strip() in ("–", "-") else (f"{row['rolle']}: {row['navn']}. " if row.get("rolle", "–") not in ("–", "-") else f"{row['navn']}. ")
            txt = (lead + (row.get("paavirkning") or "")).strip()
            o["description"] = (o["description"] + " " + txt).strip() if o["description"] else txt
    # kuraterte tillegg fra nyhetssaker
    for e in extra.get("entities", []):
        if e["id"] in E:  # utvid eksisterende med nyhetskilder
            for s in e.get("sources", []):
                if s["url"] not in {x["url"] for x in E[e["id"]]["sources"]}: E[e["id"]]["sources"].append(s)
            if e.get("add_description"): E[e["id"]]["description"] = (E[e["id"]].get("description") or "") + " " + e["add_description"]
            continue
        e = dict(e); e.setdefault("image", imgs.get(e["id"])); E[e["id"]] = e
    for r in extra.get("relations", []):
        if r["from"] in E and r["to"] in E: R.append(dict(r, status="published"))
        else: skipped.append(f"relasjon {r['id']} (mangler entitet)")
    for e in E.values():
        e.setdefault("status", "published")
        if e.get("type") == "person" and not e.get("image"): e["image"] = imgs.get(e["id"])
    out = {"updated": (exp or {}).get("per_dato"), "summary": (exp or {}).get("oppsummering") if cfg.get("publish_summary") else None,
           "caveats": (exp or {}).get("forbehold", []), "entities": list(E.values()), "relations": R}
    json.dump(out, open(P("data", "orgchart_no_raw.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"industrikart: {len(E)} entiteter ({sum(e['type']=='person' for e in E.values())} personer), {len(R)} relasjoner fra {cfg.get('export')}"
          + (f"; hoppet over: {skipped}" if skipped else ""))
if __name__ == "__main__": main()
