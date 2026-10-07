"""Predatory or fake conference listings. Never imported and never shown.

The event pipeline (events.py) refuses a match on the event URL, the source URL,
the source name or the organiser. The calendar and the public API use the same
check, so a row that is already stored is not listed either.

Domains are the listing sites flagged as predatory (International Conference
Alerts, Conference Alerts, All Conference Alert, Conference Next, WASET and
Conference Index) and the sites of the named organisers. A host matches when
one of its labels is a listing brand, or when it is the organiser's domain.
"www" is ignored. notwaset.org does not match waset.org.
"""
import re
import urllib.parse

# Listing brands. Matched as a whole hostname label, so a subdomain is included
# and a longer label such as notwaset is not.
LISTING_LABELS = {
    "internationalconferencealerts",
    "conferencealerts",
    "conferencealert",
    "allconferencealert",
    "allconferencealerts",
    "worldconferencealerts",
    "conferencenext",  # same listings as International Conference Alerts and All Conference Alert
    "conferenceindex",
    "waset",
}

# Organiser sites. Matched as the host or a subdomain of that host.
ORGANISER_DOMAINS = {
    "iraj.in", "iraj.org", "iraj.com",
    "theiier.org", "iier.org", "iier.in",
    "iierd.org", "iierd.com",
    "iser.co.in", "iser.org.in", "iser.in",
    "academicsworld.org", "academicsworld.com", "academicsworld.net", "academicsworld.in",
    "worldacademics.org", "worldacademics.com", "worldacademics.net",
}

# Organiser and source names. Short acronyms are whole tokens, so "research" is not ISER.
_NAME = re.compile(
    r"\bWASET\b"
    r"|world academy of science,? engineering and technology"
    r"|\bIRAJ\b"
    r"|institute (?:of|for) research and journals"
    r"|\bIIERD?\b"
    r"|international institute of engineers and (?:researchers|doctors)"
    r"|\bISSER\b"
    r"|institute for scientific and engineering research"
    r"|\bISER\b"
    r"|international society for engineers and researchers"
    r"|\bKSAA\b"
    r"|\bGASR\b"
    r"|\bIIRD\b"
    r"|research\s+plus"
    r"|scholars\s+forum"
    r"|academics\s+world"
    r"|world\s+academics"
    r"|international conference alerts"
    r"|all\s+conference alerts?"
    r"|\bconference alerts?\b"
    r"|\bconference next\b",
    re.I,
)


def host_of(url):
    if not isinstance(url, str) or not url.strip():
        return ""
    raw = url.strip()
    if raw.startswith("//"):
        raw = "https:" + raw
    elif "://" not in raw:
        raw = "https://" + raw
    try:
        host = urllib.parse.urlparse(raw).hostname or ""
    except ValueError:
        return ""
    return host.lower().rstrip(".")


def host_blocked(host):
    labels = [p for p in (host or "").split(".") if p and p != "www"]
    if not labels:
        return False
    if any(label in LISTING_LABELS for label in labels):
        return True
    joined = ".".join(labels)
    return any(joined == d or joined.endswith("." + d) for d in ORGANISER_DOMAINS)


def _name_blocked(value):
    return isinstance(value, str) and bool(_NAME.search(value))


def blocked_event(ev, src=None):
    """True when the URL, source or organiser is a predatory conference listing."""
    ev = ev or {}
    src = src or {}
    urls = (ev.get("url"), ev.get("source_url"), src.get("url"), src.get("page"), src.get("feed"))
    if any(host_blocked(host_of(u)) for u in urls):
        return True
    names = (ev.get("organiser"), ev.get("source"), src.get("name"), src.get("organiser"))
    return any(_name_blocked(n) for n in names)


def blocked_source(src):
    """True when an event_sources entry points at a predatory listing or organiser."""
    if not isinstance(src, dict):
        return False
    return blocked_event({
        "url": src.get("url"),
        "source_url": src.get("page") or src.get("feed"),
        "source": src.get("name"),
        "organiser": src.get("organiser"),
    })


def _ids(approvals, key):
    return set((approvals or {}).get(key) or [])


def publication_status(event, approvals, preview, approvals_present, from_archive=False):
    """Status to show, or None to leave the event off the public calendar.

    Only an id in queue/approved.json events.approve is published. A stored
    status of "published" is not approval: that is how the International
    Conference Alerts rows were written into the archive and then shown.
    When the approval file is absent, the committed archive stays the public
    record and rows in data/events.json are not promoted. A predatory listing
    is omitted even if its id is on the approve list.
    """
    if not event or blocked_event(event):
        return None
    approvals = approvals or {}
    eid = event.get("id")
    if eid in _ids(approvals, "reject"):
        return None
    if eid in _ids(approvals, "approve"):
        return "published"
    if eid in _ids(approvals, "ready_for_owner"):
        return "owner" if preview else None
    if preview and not from_archive and event.get("status") in ("pending", "owner"):
        return event.get("status")
    if from_archive and not approvals_present and event.get("status") == "published":
        return "published"
    return None
