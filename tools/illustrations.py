#!/usr/bin/env python3
"""Licensed pictures for story cards and story pages.

The catalogue is data/illustrations.json. A story does not store the picture.
assign() picks one record from the story's topics and country, unless the
story has illustration_id set to a catalogue id (an extra field; existing
rows stay valid without it).

Allowed kinds:
  original       drawn for Nordic Crypto, no real person, no copied logo
  commons        Wikimedia Commons under CC0, CC BY or CC BY-SA
  official-press a public body that released the file for free use; terms recorded

Newspaper photographs are refused by tools/press_images.py and cannot be
added to this catalogue.
"""
import html as html_mod
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "illustrations.json")

_ALLOWED_LICENCE = re.compile(r"^(CC0|Public domain|CC BY-SA(?: |$)|CC BY(?: |$))", re.I)
_KINDS = {"original", "commons", "official-press"}
_cache = None


def load(path=None):
    global _cache
    path = path or PATH
    if path == PATH and _cache is not None:
        return _cache
    import json
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if path == PATH:
        _cache = data
    return data


def reset():
    global _cache
    _cache = None


def _by_id(data):
    return {im["id"]: im for im in data.get("images") or []}


def _press():
    try:
        import press_images
        return press_images
    except ImportError:
        from tools import press_images
        return press_images


def validate(data=None):
    """Raise ValueError if a record is missing a credit field or is a press photo."""
    press_images = _press()
    data = data or load()
    ids = _by_id(data)
    if len(ids) != len(data.get("images") or []):
        raise ValueError("duplicate illustration id")
    if data.get("fallback") not in ids:
        raise ValueError("fallback illustration missing")
    for code, iid in (data.get("country") or {}).items():
        if iid not in ids:
            raise ValueError(f"country {code} points at unknown {iid}")
    for im in data["images"]:
        for key in ("id", "kind", "file", "alt", "source", "author", "license", "url", "width", "height"):
            if not im.get(key) and im.get(key) != 0:
                raise ValueError(f"{im.get('id')}: missing {key}")
        if im["kind"] not in _KINDS:
            raise ValueError(f"{im['id']}: kind {im['kind']}")
        rel = im["file"]
        if rel.startswith("http") or ".." in rel.split("/"):
            raise ValueError(f"{im['id']}: file must be a path in the repo")
        if not rel.startswith("assets/img/illustrations/") or not rel.endswith(".webp"):
            raise ValueError(f"{im['id']}: file must be a webp under assets/img/illustrations/")
        full = os.path.join(ROOT, rel)
        if not os.path.isfile(full):
            raise ValueError(f"{im['id']}: file missing")
        if press_images.is_press_image_url(im.get("url") or "") or press_images.is_press_image_url(im.get("license_url") or ""):
            raise ValueError(f"{im['id']}: url is a newspaper picture")
        if im["kind"] == "official-press":
            if not (im.get("terms") and im.get("license_url")):
                raise ValueError(f"{im['id']}: official press image needs terms and license_url")
        elif not _ALLOWED_LICENCE.match(im["license"]):
            raise ValueError(f"{im['id']}: licence {im['license']!r} is not CC0, CC BY, CC BY-SA or public domain")
        try:
            from PIL import Image
            with Image.open(full) as pic:
                if list(pic.size) != [im["width"], im["height"]]:
                    raise ValueError(f"{im['id']}: dimensions {pic.size} != {[im['width'], im['height']]}")
        except ImportError:
            pass
    for rule in data.get("assign") or []:
        iid = rule.get("id")
        if iid not in ids and iid != "country":
            raise ValueError(f"assign rule points at {iid}")
    return data


def assign(item, data=None):
    """The picture for one story. None only when the catalogue is empty."""
    data = data or load()
    ids = _by_id(data)
    override = (item or {}).get("illustration_id")
    if isinstance(override, str) and override in ids and "://" not in override:
        return dict(ids[override])
    topics = [str(t).lower() for t in ((item or {}).get("topics") or [])]
    country = (item or {}).get("country") or ""
    chosen = None
    for rule in data.get("assign") or []:
        want = [str(t).lower() for t in (rule.get("topics") or [])]
        if want and not any(t in want for t in topics):
            continue
        countries = rule.get("countries")
        if countries and country not in countries:
            continue
        iid = rule.get("id")
        if iid == "country":
            iid = (data.get("country") or {}).get(country) or data.get("fallback")
        if iid in ids:
            chosen = ids[iid]
            break
    if chosen is None:
        chosen = ids.get(data.get("fallback"))
    return dict(chosen) if chosen else None


def attach(items, data=None):
    for item in items:
        item["illustration"] = assign(item, data)
    return items


def credit_text(rec):
    if not rec:
        return ""
    kind = "Illustration" if rec.get("kind") == "original" else "Photo"
    extra = " Cropped." if rec.get("modifications") else ""
    return f"{kind}: {rec.get('author')}. Licence: {rec.get('license')}. Source: {rec.get('source')}.{extra}"


def api_record(rec, abs_url):
    """Fields the API shows for one picture: source, author, license, url, plus the file."""
    if not rec:
        return None
    return {
        "id": rec.get("id"),
        "kind": rec.get("kind"),
        "file_url": abs_url(rec["file"]) if rec.get("file") else None,
        "width": rec.get("width"),
        "height": rec.get("height"),
        "alt": rec.get("alt"),
        "source": rec.get("source"),
        "author": rec.get("author"),
        "license": rec.get("license"),
        "license_url": rec.get("license_url") or None,
        "url": rec.get("url"),
        "credit": credit_text(rec),
        "modifications": rec.get("modifications") or None,
        "terms": rec.get("terms") or None,
    }


def catalogue(abs_url, data=None):
    data = data or load()
    return [api_record(im, abs_url) for im in data.get("images") or []]


def figure_html(rec, prefix, labels, href=None, esc=None):
    """Left-aligned figure. Credit sits under the picture. href wraps the img on a card."""
    if not rec or not rec.get("file"):
        return ""
    esc = esc or (lambda s: html_mod.escape(s or "", quote=True))
    src = f"{prefix}{rec['file']}"
    img = (
        f'<img src="{esc(src)}" alt="{esc(rec.get("alt") or "")}" '
        f'width="{int(rec["width"])}" height="{int(rec["height"])}" loading="lazy" decoding="async">'
    )
    if href:
        img = f'<a href="{esc(href)}">{img}</a>'
    word = labels.get("ill_drawing") if rec.get("kind") == "original" else labels.get("ill_photo")
    author = esc(rec.get("author") or "")
    lic = rec.get("license") or ""
    lic_html = esc(lic)
    if rec.get("license_url"):
        lic_html = f'<a href="{esc(rec["license_url"])}" rel="license noopener">{esc(lic)}</a>'
    source = esc(rec.get("source") or "")
    if rec.get("url"):
        source = f'<a href="{esc(rec["url"])}" rel="noopener">{source}</a>'
    cap = f'{esc(word or "")}: {author}. {esc(labels.get("ill_licence") or "")}: {lic_html}. {esc(labels.get("ill_source") or "")}: {source}.'
    if rec.get("modifications"):
        cap += " " + esc(labels.get("ill_cropped") or "")
    return f'<figure class="ill">{img}<figcaption class="credit">{cap}</figcaption></figure>'
