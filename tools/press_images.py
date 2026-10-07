#!/usr/bin/env python3
"""Newspaper photographs stay at the newspaper.

Norwegian copyright law (åndsverkloven § 23) protects photographic pictures,
including pictures a newspaper made or bought for a story. Linking to the
article is not a licence to copy, store, proxy or hotlink the picture.

This module is the import rule. fetch.py calls it for every RSS item and
every page it reads. The site build and the API call it again. An outlet
logo that only identifies the source is not an article image and is left
alone (see tools/source_logos.py).
"""
import re

# Fields an importer might use for an article picture. None of these are
# published. "illustration" and "source_logo" are ours and are not in this set.
PRESS_IMAGE_KEYS = (
    "image", "image_url", "images", "og_image", "ogImage", "thumbnail", "thumb",
    "thumbnail_url", "hero", "hero_image", "hero_url", "hero_blur", "blur",
    "enclosure", "enclosures", "media_content", "media_thumbnail", "media_url",
    "picture", "photo", "photo_url", "lead_image", "main_image",
)

_IMAGE_EXT = re.compile(r"\.(?:jpe?g|png|gif|webp|avif|bmp|tiff?)(?:$|[?#])", re.I)

# Hosts of newspapers and broadcasters we link to. A picture URL on one of
# these hosts is someone else's news photo, even if a future field name is new.
PRESS_HOSTS = (
    "aftenposten.no", "vg.no", "dagbladet.no", "nrk.no", "e24.no", "dn.no",
    "finansavisen.no", "nettavisen.no", "tv2.no", "adressa.no", "bt.no", "ba.no",
    "dagsavisen.no", "klassekampen.no", "morgenbladet.no", "shifter.no",
    "digi.no", "tek.no", "kode24.no", "e24.no", "dn.no",
    "sydsvenskan.se", "svd.se", "di.se", "realtid.se", "breakit.se",
    "dn.se", "svt.se", "expressen.se", "aftonbladet.se", "dagensindustri.se",
    "kauppalehti.fi", "hs.fi", "yle.fi", "iltalehti.fi", "is.fi", "talouselama.fi",
    "politiken.dk", "berlingske.dk", "dr.dk", "borsen.dk", "ekstrabladet.dk",
    "jyllands-posten.dk", "tv2.dk", "finans.dk", "version2.dk",
    "mbl.is", "visir.is", "ruv.is", "heimildin.is",
    "reuters.com", "bloomberg.com", "wsj.com", "ft.com", "nytimes.com",
    "theguardian.com", "bbc.co.uk", "bbc.com",
)

_ignored = 0


def reset_ignored():
    global _ignored
    _ignored = 0


def ignored_count():
    return _ignored


def note_ignored(n=1):
    """Count a picture we saw and refused to store. The URL is not kept."""
    global _ignored
    _ignored += n


def _host(url):
    m = re.match(r"https?://([^/?#]+)", str(url or ""), re.I)
    if not m:
        return ""
    host = m.group(1).lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def is_press_image_url(url):
    """True when a URL looks like a picture on a newspaper or broadcaster host."""
    host = _host(url)
    if not host or not _IMAGE_EXT.search(str(url)):
        return False
    return any(host == h or host.endswith("." + h) for h in PRESS_HOSTS)


def entry_carries_article_image(entry):
    """RSS media:content, media:thumbnail or an image enclosure. Do not read the URL out."""
    if entry is None:
        return False
    found = False
    for key in ("media_content", "media_thumbnail"):
        if entry.get(key):
            found = True
    for enc in entry.get("enclosures") or []:
        href = enc.get("href") or enc.get("url") or ""
        typ = (enc.get("type") or "").lower()
        if typ.startswith("image/") or _IMAGE_EXT.search(href):
            found = True
    if found:
        note_ignored()
    return found


def note_og_image(url):
    """page_meta sees og:image and drops it. The URL is not returned or stored."""
    if url:
        note_ignored()
    return None


def strip_press_images(item):
    """Remove article-image fields from a news row. Status, summary and url stay.

    Returns the list of keys removed. Does not write the file.
    """
    if not isinstance(item, dict):
        return []
    removed = [k for k in PRESS_IMAGE_KEYS if k in item]
    for k in removed:
        item.pop(k, None)
    # An override must be one of our catalogue ids, never a remote picture URL.
    override = item.get("illustration_id")
    if isinstance(override, str) and ("://" in override or override.startswith("//")):
        item.pop("illustration_id", None)
        removed.append("illustration_id")
    return removed


def walk_press_urls(obj, where=""):
    """Yield (path, url) for picture URLs on a newspaper host, anywhere in obj."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_press_urls(v, f"{where}.{k}" if where else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_press_urls(v, f"{where}[{i}]")
    elif isinstance(obj, str) and is_press_image_url(obj):
        yield where, obj
