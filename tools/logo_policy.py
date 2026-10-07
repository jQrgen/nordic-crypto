#!/usr/bin/env python3
"""When an outlet logo may be shown.

Nominative use only: the outlet's own official mark (logo, favicon or
apple-touch-icon, or a press-kit file of that mark), unaltered apart from
scaling a raster image to about 64px, shown small beside the source name and
linked to the outlet. It does not imply endorsement.

A logo is skipped when the outlet's own terms explicitly forbid using the logo.
A general copyright line, or a clause that only forbids implying endorsement,
does not forbid identification.
"""
import re
import urllib.parse

# Blanket bans. A nearby endorsement/sponsorship clause is not a blanket ban.
_FORBID = re.compile(
    r"(?:"
    r"(?:may|must|shall) not use (?:our |the |any )?(?:logo|logotype|wordmark|trademark)"
    r"|do not use (?:our |the )?logo"
    r"|(?:any )?use of (?:our |the )?(?:logo|logotype) is (?:prohibited|forbidden|not permitted|not allowed)"
    r"|logo(?:type|s)? (?:may|must|shall) not be used"
    r"|ikke (?:tillatt|lov) å bruke [^\n.]{0,40}logo"
    r"|forbudt å bruke [^\n.]{0,40}logo"
    r"|logoen (?:må|kan) ikke brukes"
    r"|får inte använda [^\n.]{0,40}logotyp"
    r"|logotypen får inte användas"
    r"|användning av (?:vår |var )?(?:logotyp|logo) [^\n.]{0,40}(?:förbjuden|inte tillåten|ej tillåten)"
    r"|må ikke bruge [^\n.]{0,40}logo"
    r"|det er ikke tilladt at bruge [^\n.]{0,40}logo"
    r"|logoet må ikke (?:bruges|anvendes)"
    r"|logon käyttö [^\n.]{0,40}(?:kielletty|kielletään)"
    r"|ei saa käyttää [^\n.]{0,30}logo"
    r"|óheimilt (?:er )?að nota [^\n.]{0,40}(?:merki|logo)"
    r")",
    re.I,
)
_ENDORSE = re.compile(
    r"endors|sponsor|godkjen|markedsf|marknadsf|hyväks|viðurken|partnership",
    re.I,
)
# Not the outlet's own mark, or not a logo at all.
_BAD_URL = re.compile(
    r"imageId=|/width=\d{3,}|podme\.com|zeno\.fm|youtube\.com|youtu\.be|"
    r"spotify\.com|facebook\.com|fbcdn|twimg\.com|instagram\.com|"
    r"1871|masthead|newspaper-scan",
    re.I,
)
_LOGOISH = re.compile(r"logo|wordmark|apple-touch|favicon|icon", re.I)
_PLATFORM = ("podme.com", "zeno.fm", "youtube.com", "spotify.com", "facebook.com", "instagram.com", "twitter.com", "x.com")


def terms_forbid_logo(text):
    """Return a short quote when the text bans logo use, else None."""
    if not text:
        return None
    for m in _FORBID.finditer(text):
        window = text[m.end():m.end() + 90]
        if _ENDORSE.search(window):
            continue
        quote = re.sub(r"\s+", " ", m.group(0)).strip()
        return quote[:180]
    return None


def bad_image_url(url):
    """True when the URL is a photo, a platform icon, or a historical scan."""
    return bool(url and _BAD_URL.search(url))


def _host(url):
    return (urllib.parse.urlparse(url or "").hostname or "").lower().removeprefix("www.")


def _label(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _fold(text):
    """Lower-case and fold Nordic letters so a file name can match the outlet name."""
    table = str.maketrans({
        "ø": "o", "ö": "o", "å": "a", "ä": "a", "æ": "ae",
        "é": "e", "á": "a", "í": "i", "ó": "o", "ú": "u", "ý": "y",
        "ð": "d", "þ": "th",
    })
    return _label((text or "").lower().translate(table))


def own_mark(rec, homepage, name=""):
    """True when this manifest record is the outlet's own official mark.

    Official-website images linked from the outlet's homepage qualify, including
    a publisher CDN, as long as the URL is not a photo or another company's icon.
    A Wikimedia file qualifies when it is the outlet's logo (the file name says
    so) and it is not a scan of an old page.
    """
    if not isinstance(rec, dict) or not rec.get("file"):
        return False
    url = rec.get("source_url") or ""
    if bad_image_url(url):
        return False
    src = rec.get("source") or ""
    if src == "Official website":
        # Fetched from the outlet's homepage (page is that response, including a redirect).
        if not rec.get("page") or not homepage:
            return False
        if any(p in _host(url) for p in _PLATFORM):
            return False
        kind = rec.get("kind") or ""
        if kind in ("touch", "svgicon", "icon"):
            return True
        if kind != "img" and not _LOGOISH.search(url):
            return False
        filename = urllib.parse.urlparse(url).path.rsplit("/", 1)[-1].lower()
        label = _fold(_host(homepage).split(".")[0])
        title = _fold(name)
        fn = _fold(filename)
        if label and len(label) >= 4 and label in fn:
            return True
        if title and len(title) >= 4 and title[:12] in fn:
            return True
        generic = {"logo", "logos", "white", "black", "negativ", "negative", "primary", "header",
                   "footer", "square", "icon", "touch", "apple", "brand", "dark", "light", "main",
                   "site", "news", "media", "favicon", "wordmark", "horizontal", "vertical",
                   "blue", "vector", "color", "colour"}
        words = []
        for w in re.findall(r"[a-z]{5,}", filename):
            for suffix in ("wordmark", "favicon", "logo", "icon"):
                if w.endswith(suffix) and len(w) > len(suffix):
                    w = w[: -len(suffix)]
                    break
            if len(w) < 5 or w in generic:
                continue
            words.append(w)
        own = [t for t in (label, title) if t]
        if any(not any(t in w or w in t for t in own) for w in words):
            return False
        return "logo" in fn or "favicon" in fn or "wordmark" in fn or "icon" in fn
    if src == "Wikimedia Commons":
        if not _LOGOISH.search(url):
            return False
        if rec.get("file", "").endswith(".svg") or "logo" in url.lower():
            return "1871" not in url and "topp" not in url.lower()
    return False
