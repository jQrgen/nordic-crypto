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
