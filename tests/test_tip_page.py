#!/usr/bin/env python3
"""The /tip/ page stays closed until the private inbox is switched on. No network."""
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["NC_SITE_DIR"] = tempfile.mkdtemp(prefix="nc-tip-")
os.environ.pop("TIP_INTAKE", None)
os.environ.pop("TIP_INTAKE_ENDPOINT", None)
os.environ.pop("TIP_TURNSTILE_SITEKEY", None)
os.environ.pop("TIP_ONION", None)
import build

fails = []


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def page(lang):
    build.LANG = lang
    build.build_tip()
    path = os.path.join(build.SITE, "" if lang == "en" else lang, "tip", "index.html")
    return open(path, encoding="utf-8").read()


def main():
    enabled, ep, key, onion = build.tip_intake_config()
    check(enabled is False, "intake flag defaults off")
    check(ep == "https://tips.nordiccrypto.no", "endpoint is tips.nordiccrypto.no")
    check(key == "", "turnstile site key is empty until configured")
    check(onion == "", "no onion address until one exists")

    html = page("en")
    check("Opening soon" in html, "english opening-soon notice")
    check("Nordic Crypto" in html and "Nordic <span>Crypto</span>" in html, "brand is Nordic Crypto")
    check("<form" not in html, "closed page has no form")
    check("issues/new" not in html and "template=tip.yml" not in html, "closed page does not open a GitHub issue")
    check("tips.nordiccrypto.no" not in html, "closed page does not post to the worker")
    check("text-align:left" in html, "tip copy is left-aligned")
    check("artificial intelligence" in html and "is not a human" in html, "editor is not called a human")
    check("not published yet" in html and "onion-location" not in html, "tor is named without an address")

    da = page("da")
    check("Åbner snart" in da and "kunstig intelligens" in da, "danish opening notice")
    check("<form" not in da and "issues/new" not in da, "danish page has no form and no GitHub issue")

    nb = page("nb")
    check("kunstig intelligens" in nb and " AI " not in nb and " KI " not in nb, "bokmål says kunstig intelligens")

    os.environ["TIP_INTAKE"] = "1"
    os.environ["TIP_TURNSTILE_SITEKEY"] = "1x00000000000000000000AA"
    on, ep_on, key_on, _onion = build.tip_intake_config()
    check(on is True and key_on.startswith("1x") and ep_on == "https://tips.nordiccrypto.no", "flag can be forced on")
    opened = page("en")
    check('<form id="tipform"' in opened, "open page has the tip form")
    check('action="https://tips.nordiccrypto.no/api/tip"' in opened, "form posts to the Nordic Crypto tip host")
    check("issues/new" not in opened and "template=tip.yml" not in opened, "open page does not open a GitHub issue")
    check("cf-turnstile" in opened, "open page includes Turnstile")
    check("Opening soon" not in opened, "open page does not say opening soon")

    os.environ["TIP_ONION"] = "http://" + ("a" * 56) + ".onion"
    with_onion = page("en")
    check('http-equiv="onion-location"' in with_onion, "onion-location meta when an address exists")
    check("http://" + ("a" * 56) + ".onion/en/" in with_onion, "tip page links the onion address")
    check("issues/new" not in with_onion, "onion link does not open a GitHub issue")

    os.environ["TIP_INTAKE"] = "0"
    os.environ.pop("TIP_ONION", None)
    closed_again = page("da")
    check("<form" not in closed_again and "Åbner snart" in closed_again, "TIP_INTAKE=0 closes the form again")

    shutil.rmtree(build.SITE, ignore_errors=True)
    if fails:
        print(f"\n{len(fails)} failed")
        sys.exit(1)
    print("tip page checks passed")


if __name__ == "__main__":
    main()
