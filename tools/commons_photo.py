#!/usr/bin/env python3
"""Laster ned et fritt lisensiert portrett fra Wikimedia Commons og skriver bildeinfo inn i data/images.json (leses av import_industrikart.py ved hver bygging).
  .venv/bin/python tools/commons_photo.py <entity-id> "<Commons-filnavn>"
Godtar bare CC0, Public domain, CC BY og CC BY-SA. Lagrer en 240 px versjon lokalt (ingen hotlinking)."""
import json, os, re, sys, requests
from bs4 import BeautifulSoup
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "CryptoNordic/0.1 (https://jqrgen.github.io/nordic-crypto/; github.com/jQrgen/nordic-crypto)"
OK = re.compile(r"^(CC0|Public domain|PD|CC BY(-SA)? \d\.\d( \w+)?|CC BY(-SA)?)", re.I)
def txt(h): return BeautifulSoup(h or "", "lxml").get_text(" ", strip=True)
def fetch(eid, fname):
    r = requests.get("https://commons.wikimedia.org/w/api.php", headers={"User-Agent": UA}, timeout=20, params={
        "action": "query", "titles": "File:" + fname, "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 240, "format": "json"}).json()
    page = next(iter(r["query"]["pages"].values())); ii = page["imageinfo"][0]; md = ii["extmetadata"]
    lic = md.get("LicenseShortName", {}).get("value", ""); 
    if not OK.match(lic): raise SystemExit(f"lisens ikke godkjent: {lic!r}")
    img = requests.get(ii["thumburl"], headers={"User-Agent": UA}, timeout=30); img.raise_for_status()
    rel = f"assets/img/people/{eid}.jpg"; open(os.path.join(ROOT, rel), "wb").write(img.content)
    return {"file": rel, "source_page": ii["descriptionurl"], "author": txt(md.get("Artist", {}).get("value")) or "ukjent",
            "license": lic, "license_url": md.get("LicenseUrl", {}).get("value") or ii["descriptionurl"], "origin": "Wikimedia Commons"}
if __name__ == "__main__":
    eid, fname = sys.argv[1], sys.argv[2]
    p = os.path.join(ROOT, "data", "images.json")
    imgs = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    imgs[eid] = fetch(eid, fname); json.dump(imgs, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(eid, imgs[eid]["license"], imgs[eid]["author"])
