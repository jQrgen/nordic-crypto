"""Add talk speakers to the who's who, and link talks, events and people.

A speaker named on a talk is one person. The same name, or the same public
handle, matches an existing who's who entry and does not create a second one.
An affiliation is stored only when the video page states it next to that name
("Name (Organisation)" or "Name, role at Organisation"), with the talk date
when the talk has one, the page URL and the retrieval time. The platform
description is not copied into the data. No photo is added.

  python3 tools/talk_speakers.py
"""
import datetime as dt
import html
import json
import os
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import event_block  # noqa: E402
import talks as talks_mod  # noqa: E402

TALKS_PATH = os.path.join(ROOT, "data", "talks.json")
ORG_PATH = os.path.join(ROOT, "data", "orgchart.json")
SPEAKERS_PATH = os.path.join(ROOT, "data", "orgchart_speakers.json")

_HANDLE = re.compile(r"(?:https?://)?(?:www\.)?(?:x|twitter)\.com/([^/?#]+)", re.I)
# A title the page puts before the employer. The organisation is the part after it.
_ROLE_LEAD = re.compile(
    r"^(?:co[\s-])?(?:founder|founding|partner|ceo|cto|cdo|cfo|cio|coo|"
    r"phd(?:\s+student)?|professor|dr|senior|junior|advisor|adviser|director|"
    r"student|engineer|researcher|president|chair(?:man|woman|person)?|"
    r"head|lead|chief|manager|officer|associate|assistant|lecturer|fellow)\b",
    re.I,
)
# Words that continue a sentence after the employer ("speaking at Slush").
_TRAILING = re.compile(r"^(?:speaking|presenting|talking|discussing|moderating|who|which|and|during|about)\b", re.I)
# A single word left over when "of" sat inside a title ("of Practice"), not an employer.
_NOT_ORG = {"practice", "science", "engineering", "affairs", "innovation", "discovery", "speaking", "student"}


def norm_name(value):
    """Fold a name or handle for comparison. Case and accents do not make a new person."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().strip().lstrip("@")
    for src, dst in (("ø", "o"), ("æ", "ae"), ("å", "a"), ("ä", "a"), ("ö", "o"), ("ð", "d"), ("þ", "th")):
        text = text.replace(src, dst)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def handles(entity):
    """Public handles already stored on a who's who entry."""
    found = set()
    if not isinstance(entity, dict):
        return found
    urls = [entity.get("profile_url") or ""]
    for profile in entity.get("profiles") or []:
        if isinstance(profile, dict):
            urls.append(profile.get("url") or "")
    for url in urls:
        match = _HANDLE.search(url or "")
        if match:
            token = norm_name(match.group(1))
            if token and token not in {"share", "intent", "home"}:
                found.add(token)
    return found


def _clean_org(text):
    text = html.unescape(text or "")
    text = re.sub(r"\s+", " ", text.strip(" \t.,;:"))
    if not text or len(text) > 80 or len(text.split()) > 12:
        return None
    low = text.casefold()
    if low.startswith("http") or "www." in low or "://" in low:
        return None
    if re.fullmatch(r"[\d:.\- ]+", text):
        return None
    # A title or a leftover clause is not the employer.
    if " at " in f" {low} " or _TRAILING.match(text) or " speaking " in f" {low} ":
        return None
    if _ROLE_LEAD.match(text) or low in _NOT_ORG:
        return None
    if "," in text:
        parts = [part.strip() for part in text.split(",") if part.strip()]
        if any(part.casefold() in _NOT_ORG for part in parts):
            return None
    if event_block._name_blocked(text) or talks_mod.PREDATORY.search(text):
        return None
    return text


def _clean_role(text):
    text = html.unescape(text or "")
    text = re.sub(r"\s+", " ", text.strip(" \t.;:"))
    if not text or len(text) > 80 or len(text.split()) > 10 or "." in text:
        return None
    if not _ROLE_LEAD.match(text):
        return None
    return text


def _paren_affiliation(inner):
    """Organisation inside ``Name ( … )``. A title in front of it is stored as the role."""
    inner = re.sub(r"\s+", " ", (inner or "").strip())
    # A comma separates the title from the employer. "of" after that comma is part of the name
    # ("Indian Institute of Science"), not the word that introduces the employer.
    if "," in inner:
        role_part, rest = [part.strip() for part in inner.split(",", 1)]
        employed = re.fullmatch(r"(.+?)\s+at\s+(.+)", rest, re.I)
        if employed and _clean_role(role_part):
            role = _clean_role(role_part + ", " + employed.group(1).strip())
            org = _clean_org(employed.group(2))
            if role and org:
                return {"organisation": org, "role": role}
        role = _clean_role(role_part)
        org = _clean_org(rest)
        if role and org:
            return {"organisation": org, "role": role}
        return None
    match = re.fullmatch(r"(.+?)\s+(at|of)\s+(.+)", inner, re.I)
    if match:
        role = _clean_role(match.group(1))
        org = _clean_org(match.group(3))
        if role and org:
            return {"organisation": org, "role": role}
    org = _clean_org(inner)
    if org:
        return {"organisation": org}
    return None


def _clause_affiliation(description, name):
    """``Name, role at Organisation`` or ``Name, role, Organisation``.

    A comma that only introduces "speaking at …" is not part of the employer.
    ``of`` inside a title ("Professor Emeritus of Practice, Swedish House of Finance")
    stays in the role. The organisation is the following name.
    """
    match = re.search(re.escape(name) + r",\s+([^.\n]{1,160})", description)
    if not match:
        return None
    clause = re.sub(r"\s+", " ", match.group(1).strip())
    parts = re.match(r"([^,]{1,80}?)\s+(at|of)\s+([^,]{1,80})(?:,\s*(.+))?$", clause, re.I)
    if parts:
        role = _clean_role(parts.group(1))
        org = _clean_org(parts.group(3))
        rest = (parts.group(4) or "").strip()
        if role and org and (not rest or _TRAILING.match(rest)):
            return {"organisation": org, "role": role}
        if rest and not _TRAILING.match(rest):
            role2 = _clean_role(f"{parts.group(1)} {parts.group(2)} {parts.group(3)}")
            org2 = _clean_org(rest)
            if role2 and org2:
                return {"organisation": org2, "role": role2}
        return None
    bits = [bit.strip() for bit in clause.split(",")]
    if len(bits) == 2:
        role = _clean_role(bits[0])
        org = _clean_org(bits[1])
        if role and org:
            return {"organisation": org, "role": role}
    return None


def affiliation_in(description, name):
    """Organisation the description states for this speaker, or None.

    Accepted forms are ``Name (Organisation)``, ``Name (role at Organisation)`` and
    ``Name, role at/of Organisation``. Two different organisations, or a sentence
    that merely mentions the name, are not an affiliation.
    """
    if not description or not name:
        return None
    description = html.unescape(description)
    found = []
    paren = re.search(re.escape(name) + r"\s*\(([^)\n]{1,120})\)", description)
    if paren:
        item = _paren_affiliation(paren.group(1))
        if item:
            found.append(item)
    item = _clause_affiliation(description, name)
    if item:
        found.append(item)
    orgs = {row["organisation"].casefold() for row in found}
    if len(orgs) != 1:
        return None
    with_role = [row for row in found if row.get("role")]
    return dict(with_role[0] if with_role else found[0])


def _slug(name):
    base = norm_name(name).replace(" ", "-")
    base = re.sub(r"[^a-z0-9-]", "", base).strip("-") or "speaker"
    return ("spk-" + base)[:80]


def _video_id(talk):
    if (talk.get("id") or "").startswith("yt-"):
        return talk["id"][3:]
    url = talk.get("video_url") or ""
    return talks_mod.youtube_id(url) if hasattr(talks_mod, "youtube_id") else ""


def fetch_descriptions(talks, workers=4):
    """Platform description per talk id. Failures are omitted. Descriptions are not stored."""
    wanted = []
    for talk in talks:
        if not (talk.get("speakers") or []):
            continue
        vid = _video_id(talk)
        if vid:
            wanted.append((talk["id"], vid))

    def one(item):
        talk_id, vid = item
        try:
            meta = talks_mod.watch_youtube(vid)
        except Exception:
            return talk_id, None
        if not isinstance(meta, dict) or meta.get("http_status") != 200:
            return talk_id, None
        desc = meta.get("description")
        return talk_id, desc if isinstance(desc, str) and desc.strip() else None

    out = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for talk_id, desc in pool.map(one, wanted):
            if desc:
                out[talk_id] = desc
    return out


def _index(people):
    by_name = {}
    by_handle = {}
    ids = set()
    for person in people:
        if not isinstance(person, dict) or person.get("type") != "person":
            continue
        ids.add(person.get("id"))
        key = norm_name(person.get("name"))
        if key:
            by_name.setdefault(key, []).append(person)
        for handle in handles(person):
            by_handle.setdefault(handle, []).append(person)
    return by_name, by_handle, ids


def _match(name, by_name, by_handle):
    key = norm_name(name)
    if not key:
        return None
    hits = list(by_name.get(key) or [])
    if not hits:
        hits = list(by_handle.get(key) or [])
    if len(hits) == 1:
        return hits[0]
    return None


def _source(talk):
    url = (talk.get("source_url") or talk.get("video_url") or "").strip()
    if not url.startswith("http"):
        return None
    if event_block.host_blocked(event_block.host_of(url)):
        return None
    when = str(talk.get("retrieved_at") or "")
    day = when[:10] if len(when) >= 10 else ""
    name = (talk.get("channel") or "").split("*", 1)[0].strip() or "Video page"
    return {"url": url, "title": talk.get("title") or url, "source_name": name, "date": day or when}


def build_index(talks, people, descriptions, retrieved_at):
    """Return (new entities, patches for existing ids, speaker id per talk id, report).

    ``descriptions`` maps a talk id to the platform description. It is read and not copied.
    """
    by_name, by_handle, ids = _index(people)
    new = {}
    patches = {}
    per_talk = {}
    added = []
    matched = []
    affiliated_talks = 0

    def bucket(person_id, created):
        if created:
            return new[person_id]
        return patches.setdefault(person_id, {"talk_ids": [], "event_ids": [], "affiliations": [], "talks": [], "sources": []})

    for talk in talks:
        names = [s for s in (talk.get("speakers") or []) if isinstance(s, str) and s.strip()]
        ids_for_talk = []
        description = descriptions.get(talk.get("id")) if descriptions else None
        for name in names:
            name = name.strip()
            hit = _match(name, by_name, by_handle)
            created = False
            if hit is None:
                ident = _slug(name)
                n = 2
                while ident in ids or ident in new:
                    ident = _slug(name)[:70] + "-" + str(n)
                    n += 1
                ids.add(ident)
                entity = {
                    "id": ident,
                    "name": name,
                    "type": "person",
                    "sector": "private",
                    "country": None,
                    "description": None,
                    "role": None,
                    "org": None,
                    "image": None,
                    "sources": [],
                    "talk_ids": [],
                    "event_ids": [],
                    "talks": [],
                    "affiliations": [],
                    "from_talks": True,
                    "origin": "Talks archive",
                    "caveat": False,
                    "status": "published",
                }
                new[ident] = entity
                by_name.setdefault(norm_name(name), []).append(entity)
                added.append(ident)
                person_id = ident
                created = True
            else:
                person_id = hit.get("id")
                created = person_id in new
                if not created:
                    matched.append(person_id)
            ids_for_talk.append(person_id)
            row = bucket(person_id, created)
            if talk.get("id") and talk["id"] not in row["talk_ids"]:
                row["talk_ids"].append(talk["id"])
            event_id = talk.get("event_id") or talk.get("calendar_event_id")
            if event_id and event_id not in row["event_ids"]:
                row["event_ids"].append(event_id)
            brief = {"id": talk.get("id"), "title": talk.get("title") or "", "video_url": talk.get("video_url") or ""}
            if event_id:
                brief["event_id"] = event_id
            if talk.get("date"):
                brief["date"] = talk["date"]
            if not any(item.get("id") == brief["id"] for item in row["talks"]):
                row["talks"].append(brief)
            source = _source(talk)
            if source and not any(item.get("url") == source["url"] for item in row["sources"]):
                row["sources"].append(source)
            stated = affiliation_in(description, name) if description else None
            if stated:
                aff = {
                    "talk_id": talk.get("id"),
                    "organisation": stated["organisation"],
                    "source_url": (talk.get("source_url") or talk.get("video_url")),
                    "source_name": (talk.get("channel") or "").split("*", 1)[0].strip() or "Video page",
                    "retrieved_at": retrieved_at,
                }
                if stated.get("role"):
                    aff["role"] = stated["role"]
                if event_id:
                    aff["event_id"] = event_id
                if talk.get("date"):
                    aff["date"] = talk["date"]
                if not any(item.get("talk_id") == aff["talk_id"] and item.get("organisation") == aff["organisation"] for item in row["affiliations"]):
                    row["affiliations"].append(aff)
                    affiliated_talks += 1
        per_talk[talk.get("id")] = ids_for_talk

    for row in list(new.values()) + list(patches.values()):
        row["talk_ids"] = sorted(row["talk_ids"])
        row["event_ids"] = sorted(row["event_ids"])
        row["talks"] = sorted(row["talks"], key=lambda item: (item.get("date") or "", item.get("id") or ""), reverse=True)
        row["affiliations"] = sorted(row["affiliations"], key=lambda item: (item.get("date") or "", item.get("talk_id") or ""))
    report = {
        "added": len(set(added)),
        "matched": len(set(matched)),
        "speaker_mentions": sum(len(ids) for ids in per_talk.values()),
        "with_affiliation": sum(1 for row in list(new.values()) + [patches[k] for k in patches] if row.get("affiliations")),
        "affiliation_records": affiliated_talks,
        "descriptions_read": len(descriptions or {}),
    }
    # A person counted in both is a bug; added ids are new.
    report["matched"] = len(set(matched) - set(added))
    return list(new.values()), patches, per_talk, report


def merge_into(entities, doc=None):
    """Copy talk speakers onto a who's who entity list. Existing names are not duplicated."""
    doc = doc if doc is not None else _load(SPEAKERS_PATH, {"entities": [], "matched": {}})
    out = [dict(entity) for entity in entities or []]
    by_id = {entity.get("id"): entity for entity in out}
    by_name = {}
    for entity in out:
        if entity.get("type") == "person":
            by_name.setdefault(norm_name(entity.get("name")), entity)
    for raw in doc.get("entities") or []:
        if raw.get("id") in by_id:
            _overlay(by_id[raw["id"]], raw)
            continue
        key = norm_name(raw.get("name"))
        if key and key in by_name:
            _overlay(by_name[key], raw, into_matched=True)
            continue
        out.append(dict(raw))
        by_id[raw.get("id")] = out[-1]
    for ident, extra in (doc.get("matched") or {}).items():
        entity = by_id.get(ident)
        if entity:
            _overlay(entity, extra, into_matched=True)
    return out


def _overlay(entity, extra, into_matched=False):
    """Add talk links. Do not replace a role, an organisation or a photo."""
    for key in ("talk_ids", "event_ids"):
        current = list(entity.get(key) or [])
        for item in extra.get(key) or []:
            if item and item not in current:
                current.append(item)
        if current:
            entity[key] = sorted(current)
    talks = list(entity.get("talks") or [])
    seen = {item.get("id") for item in talks if isinstance(item, dict)}
    for item in extra.get("talks") or []:
        if isinstance(item, dict) and item.get("id") not in seen:
            talks.append(item)
            seen.add(item.get("id"))
    if talks:
        entity["talks"] = talks
    aff = list(entity.get("affiliations") or [])
    have = {(item.get("talk_id"), item.get("organisation")) for item in aff if isinstance(item, dict)}
    for item in extra.get("affiliations") or []:
        if isinstance(item, dict) and (item.get("talk_id"), item.get("organisation")) not in have:
            aff.append(item)
            have.add((item.get("talk_id"), item.get("organisation")))
    if aff:
        entity["affiliations"] = aff
    if not into_matched:
        for key in ("from_talks", "origin", "type", "name", "sector", "country", "caveat", "status"):
            if key in extra and entity.get(key) in (None, "", []):
                entity[key] = extra.get(key)
        if extra.get("from_talks"):
            entity["from_talks"] = True
            entity.setdefault("origin", extra.get("origin") or "Talks archive")
            entity.setdefault("image", None)
    sources = list(entity.get("sources") or [])
    seen_urls = {item.get("url") for item in sources if isinstance(item, dict)}
    for item in extra.get("sources") or []:
        if isinstance(item, dict) and item.get("url") and item["url"] not in seen_urls:
            sources.append(item)
            seen_urls.add(item["url"])
    if sources:
        entity["sources"] = sources


def _load(path, default):
    if not os.path.exists(path):
        return default
    return json.load(open(path, encoding="utf-8"))


def _dump(path, data, newline):
    text = json.dumps(data, ensure_ascii=False, indent=1)
    if newline:
        text += "\n"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def apply_descriptions(descriptions, retrieved_at=None):
    """Write speaker links from talk rows and already-fetched descriptions."""
    retrieved_at = retrieved_at or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    talks_doc = _load(TALKS_PATH, {"talks": []})
    org_doc = _load(ORG_PATH, {"entities": [], "relations": []})
    people = [e for e in org_doc.get("entities") or [] if e.get("type") == "person" and not e.get("from_talks")]
    entities, patches, per_talk, report = build_index(talks_doc.get("talks") or [], people, descriptions, retrieved_at)
    for talk in talks_doc.get("talks") or []:
        talk["speaker_ids"] = per_talk.get(talk.get("id")) or []
    raw_talks = open(TALKS_PATH, encoding="utf-8").read()
    _dump(TALKS_PATH, talks_doc, raw_talks.endswith("\n"))
    doc = {
        "_note": (
            "Speakers named on a talk in data/talks.json. An existing who's who name or handle is matched, not copied. "
            "affiliations are copied only from the video page, one per talk, with date, source URL and retrieved_at. "
            "A missing affiliation was not stated. No photo is stored. from_talks rows are published with the talks archive. "
            "tools/import_orgchart.py merges this file, so a later who's who build keeps the links."
        ),
        "retrieved_at": retrieved_at,
        "entities": entities,
        "matched": patches,
    }
    _dump(SPEAKERS_PATH, doc, True)
    org_doc["entities"] = merge_into(org_doc.get("entities") or [], doc)
    raw_org = open(ORG_PATH, encoding="utf-8").read()
    _dump(ORG_PATH, org_doc, raw_org.endswith("\n"))
    return report


def main():
    talks_doc = _load(TALKS_PATH, {"talks": []})
    descriptions = fetch_descriptions(talks_doc.get("talks") or [])
    report = apply_descriptions(descriptions)
    public = dict(report)
    print(json.dumps(public, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
