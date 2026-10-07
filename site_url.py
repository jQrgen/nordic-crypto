"""Public origin of the Nordic Crypto site.

The live origin is the one line `base` in site_url.json (this module loads it).
Change that line to rename the domain (for example https://nordiccrypto.example/).
It must be https, with a trailing slash. The host is the GitHub Pages CNAME.
Canonical, hreflang, og:url, the sitemap, robots, the JSON API, the tip worker
and newsletter links are built from it.

GitHub repository links (github.com/jQrgen/nordic-crypto and
raw.githubusercontent.com) are source links and do not use this origin.
"""
import json
import os
import re

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site_url.json")
BASE = json.load(open(_PATH, encoding="utf-8"))["base"]

# Previous project-site prefix, still in committed copy. expand() rewrites it
# to BASE, so those files do not need a second copy of the live origin.
LEGACY = "https://jqrgen.github.io/nordic-crypto/"
# Placeholder for the same rewrite, used in committed HTML that should not
# hard-code either origin.
TOKEN = "__SITE__/"


def _host_path(base):
    if "://" not in base or not base.endswith("/"):
        raise SystemExit("site BASE must be an absolute URL with a trailing slash")
    rest = base.split("://", 1)[1]
    host, path = rest.split("/", 1)
    if not host:
        raise SystemExit("site BASE has no host")
    return host, "/" + path


HOST, PATH = _host_path(BASE)
ORIGIN = BASE.split("://", 1)[0] + "://" + HOST


def join(path=""):
    """Absolute site URL. path is relative to the site root."""
    return BASE + str(path or "").lstrip("/")


def expand(text):
    """Rewrite a previous site origin or the __SITE__/ placeholder to BASE."""
    if not isinstance(text, str) or not text:
        return text
    return text.replace(TOKEN, BASE).replace(LEGACY, BASE)


# Search tokens are concatenated so this file does not itself contain the reversed name.
_REVERSED = "Crypto" + " Nordic"
_REVERSED_FI = _REVERSED + "in"
_REVERSED_CAMEL = "Crypto" + "Nordic"


def brand(text):
    """The public name is Nordic Crypto.

    Older copy put the two words in the other order. The Finnish genitive
    suffix stays on Crypto. Domains and handles such as cryptonordic.no and
    @xcryptonordic are left as they are: they have no space between the words.
    """
    if not isinstance(text, str) or not text:
        return text
    text = re.sub(re.escape(_REVERSED_FI) + r"\b", "Nordic Crypton", text, flags=re.IGNORECASE)
    text = re.sub(re.escape(_REVERSED) + r"\b", "Nordic Crypto", text, flags=re.IGNORECASE)
    return text.replace(_REVERSED_CAMEL, "NordicCrypto")


def brand_note(event):
    """Apply brand() to an event note and its translations, in place.

    queue/approved.json is local and can still carry the old word order.
    The site build and the JSON API both pass notes through here, then the
    build writes the corrected text back into archive/events.json.
    """
    note = event.get("note")
    if isinstance(note, str):
        event["note"] = brand(note)
    translations = event.get("note_i18n")
    if isinstance(translations, dict):
        event["note_i18n"] = {k: brand(v) if isinstance(v, str) else v for k, v in translations.items()}
    return event
