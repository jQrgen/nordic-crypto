#!/usr/bin/env python3
"""Nominative-use logo rules. No network. python3 tests/test_logo_policy.py"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import logo_policy

def main():
    fails = []
    def check(cond, msg):
        if not cond:
            fails.append(msg)

    check(logo_policy.terms_forbid_logo("You may not use our logo without written permission"), "blanket ban")
    check(logo_policy.terms_forbid_logo("Logoen må ikke brukes uten samtykke"), "norwegian ban")
    check(logo_policy.terms_forbid_logo("All rights reserved. © 2026") is None, "copyright is not a logo ban")
    check(logo_policy.terms_forbid_logo("You may not use the logo in a way that implies endorsement") is None, "endorsement clause is not a blanket ban")
    check(logo_policy.bad_image_url("https://commons.wikimedia.org/wiki/File:Bergens_Tidende_30._januar_1871_-_topp.jpg"), "old scan")
    check(not logo_policy.bad_image_url("https://www.aftenposten.no/favicon.ico"), "favicon ok")
    own = {"file": "assets/img/logos/aftenposten.svg", "source": "Wikimedia Commons",
           "source_url": "https://commons.wikimedia.org/wiki/File:Aftenposten_logo.svg"}
    check(logo_policy.own_mark(own, "https://www.aftenposten.no"), "aftenposten commons logo")
    scan = {"file": "assets/img/logos/bt.webp", "source": "Wikimedia Commons",
            "source_url": "https://commons.wikimedia.org/wiki/File:Bergens_Tidende_30._januar_1871_-_topp.jpg"}
    check(not logo_policy.own_mark(scan, "https://www.bt.no"), "1871 scan is not the current mark")
    touch = {"file": "assets/img/logos/e24.webp", "source": "Official website", "kind": "touch",
             "source_url": "https://e24.no/vgc/gfx/icon-180x180-1.0.png", "page": "https://e24.no"}
    check(logo_policy.own_mark(touch, "https://e24.no", "E24"), "e24 touch icon")
    sister = {"file": "assets/img/logos/version2.svg", "source": "Official website", "kind": "img",
              "source_url": "https://www.version2.dk/themes/mi/mu/images/subsite-logos/ingenioren.svg",
              "page": "https://www.version2.dk"}
    check(not logo_policy.own_mark(sister, "https://www.version2.dk", "Version2"), "sister-site wordmark is not this outlet")
    own_ing = {"file": "assets/img/logos/ingenioren.svg", "source": "Official website", "kind": "img",
               "source_url": "https://ing.dk/themes/mi/mu/images/subsite-logos/ingenioren.svg",
               "page": "https://ing.dk"}
    check(logo_policy.own_mark(own_ing, "https://ing.dk", "Ingeniøren"), "ingenioren own wordmark")
    abc = {"file": "assets/img/logos/abcnyheter.svg", "source": "Official website", "kind": "img",
           "source_url": "https://www.abcnyheter.no/view-resources/abcnyheter/public/abcnyheter/abclogo.svg",
           "page": "https://www.abcnyheter.no"}
    check(logo_policy.own_mark(abc, "https://www.abcnyheter.no", "ABC Nyheter"), "abc logo file")
    if fails:
        print("FAIL")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("logo policy ok")

if __name__ == "__main__":
    main()
