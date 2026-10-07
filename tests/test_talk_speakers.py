#!/usr/bin/env python3
"""Talk speakers in the who's who. No invented affiliation, no photo, no duplicate person."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import talk_speakers

fails = []


def check(ok, msg):
    print(("ok  " if ok else "FAIL") + " " + msg)
    if not ok:
        fails.append(msg)


def main():
    check(talk_speakers.affiliation_in("Talk by Ada Lovelace, Engineer at Analytical Engines.", "Ada Lovelace") == {"organisation": "Analytical Engines", "role": "Engineer"}, "role at organisation")
    check(talk_speakers.affiliation_in("Grace Hopper (Navy)", "Grace Hopper") == {"organisation": "Navy"}, "organisation in parentheses")
    check(talk_speakers.affiliation_in("Andreas looks at how cashless countries work.", "Andreas") is None, "a sentence is not an affiliation")
    check(talk_speakers.affiliation_in("Ada Lovelace (WASET)", "Ada Lovelace") is None, "predatory organisation refused")
    check(talk_speakers.affiliation_in("Ada Lovelace (Analytical Engines) and later Ada Lovelace, Director at Other Co.", "Ada Lovelace") is None, "two organisations are not stored")
    check(talk_speakers.affiliation_in("Jacqueline Cooper (DARA - Digital Asset Regulatory Authority)", "Jacqueline Cooper") == {"organisation": "DARA - Digital Asset Regulatory Authority"}, "a parenthetical organisation stays")
    check(talk_speakers.affiliation_in("Speaker: Disha L. Dinesha (PhD Student, Indian Institute of Science, Bengaluru)", "Disha L. Dinesha") == {"organisation": "Indian Institute of Science, Bengaluru", "role": "PhD Student"}, "a title in parentheses is the role")
    check(talk_speakers.affiliation_in("Turo Pekari (Senior Advisor, Innovation & Discovery at Teosto)", "Turo Pekari") == {"organisation": "Teosto", "role": "Senior Advisor, Innovation & Discovery"}, "the employer is the name after at")
    check(talk_speakers.affiliation_in("Marko Ahtisaari (Founder of Sync Project)", "Marko Ahtisaari") == {"organisation": "Sync Project", "role": "Founder"}, "founder of names the organisation")
    check(talk_speakers.affiliation_in("The seminar was moderated by Pehr Wissén, Professor Emeritus of Practice, Swedish House of Finance.", "Pehr Wissén") == {"organisation": "Swedish House of Finance", "role": "Professor Emeritus of Practice"}, "of inside a title stays in the role")
    check(talk_speakers.affiliation_in("Nic Cary, Co-Founder of Blockchain, speaking at Slush 2016.", "Nic Cary") == {"organisation": "Blockchain", "role": "Co-Founder"}, "speaking at is not an organisation")

    people = [{
        "id": "ada-existing",
        "name": "Ada Lovelace",
        "type": "person",
        "sector": "private",
        "country": "NO",
        "role": "Researcher",
        "org": "some-org",
        "profiles": [{"url": "https://x.com/ada", "status": "published"}],
        "sources": [{"url": "https://example.test/ada", "title": "Profile", "source_name": "Example", "date": "2026-10-01"}],
    }]
    talks = [
        {"id": "yt-1", "title": "One", "speakers": ["Ada Lovelace"], "speaker_ids": [], "video_url": "https://www.youtube.com/watch?v=aaaaaaaaaaa", "source_url": "https://www.youtube.com/watch?v=aaaaaaaaaaa", "channel": "Archive", "retrieved_at": "2026-10-07T20:00:00Z", "date": "2016-04-19", "event_id": "evt1"},
        {"id": "yt-2", "title": "Two", "speakers": ["Grace Hopper", "@ada"], "video_url": "https://www.youtube.com/watch?v=bbbbbbbbbbb", "source_url": "https://www.youtube.com/watch?v=bbbbbbbbbbb", "channel": "Archive", "retrieved_at": "2026-10-07T20:00:00Z", "date": None, "event_id": None},
    ]
    descriptions = {
        "yt-1": "Ada Lovelace, Engineer at Analytical Engines.",
        "yt-2": "Grace Hopper (Navy) spoke. The handle is not an employer.",
    }
    entities, patches, per_talk, report = talk_speakers.build_index(talks, people, descriptions, "2026-10-07T23:00:00+00:00")
    check(report["added"] == 1 and report["matched"] == 1, f"one new person, one match ({report})")
    check(per_talk["yt-1"] == ["ada-existing"], "existing name is reused")
    check(per_talk["yt-2"][0].startswith("spk-grace-hopper") and per_talk["yt-2"][1] == "ada-existing", "new speaker, and the handle matches")
    ada = patches["ada-existing"]
    check(ada["talk_ids"] == ["yt-1", "yt-2"] and ada["event_ids"] == ["evt1"], "matched person links talks and the event")
    check(ada["affiliations"][0]["organisation"] == "Analytical Engines" and ada["affiliations"][0]["date"] == "2016-04-19", "affiliation keeps the talk date and source")
    check(ada["affiliations"][0]["source_url"].startswith("https://") and ada["affiliations"][0]["retrieved_at"], "affiliation has a source url and retrieval time")
    grace = entities[0]
    check(grace["image"] is None and not grace.get("role") and grace["country"] is None, "new person has no photo, role or invented country")
    check(grace["affiliations"][0]["organisation"] == "Navy" and "date" not in grace["affiliations"][0], "undated talk stores no affiliation date")
    check("spoke" not in json.dumps(grace) and "description" not in json.dumps(grace["affiliations"]), "the platform description is not copied")
    merged = talk_speakers.merge_into(people, {"entities": entities, "matched": patches})
    names = [e["name"] for e in merged if e["type"] == "person"]
    check(names.count("Ada Lovelace") == 1 and "Grace Hopper" in names, "merge does not duplicate a person")
    kept = next(e for e in merged if e["id"] == "ada-existing")
    check(kept["role"] == "Researcher" and kept["org"] == "some-org" and "yt-1" in kept["talk_ids"], "existing role is kept and talks are added")
    import api_feed
    feed = api_feed.Feed(None, False, "https://nordiccrypto.no/")
    published = feed.entity({
        "id": "spk-grace", "name": "Grace Hopper", "type": "person", "sources": [],
        "talk_ids": ["yt-2"], "talks": [{"id": "yt-2", "title": "Two", "video_url": "https://www.youtube.com/watch?v=bbbbbbbbbbb"}],
        "affiliations": [
            {"talk_id": "yt-2", "organisation": "Navy", "source_url": "https://www.youtube.com/watch?v=bbbbbbbbbbb", "source_name": "Archive", "retrieved_at": "2026-10-07T23:00:00+00:00"},
            {"organisation": "Unsourced"},
        ],
    })
    check(published["talk_ids"] == ["yt-2"] and published["talks"][0]["title"] == "Two", "who's who API lists the talk")
    check(len(published["affiliations"]) == 1 and published["affiliations"][0]["organisation"] == "Navy", "who's who API drops an affiliation with no source")

    raw = json.load(open(os.path.join(ROOT, "data", "talks.json"), encoding="utf-8"))
    org = json.load(open(os.path.join(ROOT, "data", "orgchart.json"), encoding="utf-8"))
    by_name = {}
    for entity in org["entities"]:
        if entity.get("type") == "person":
            by_name.setdefault(talk_speakers.norm_name(entity.get("name")), []).append(entity)
    dup = [name for name, rows in by_name.items() if len(rows) > 1]
    check(not dup, "no duplicate who's who name")
    linked = 0
    for talk in raw["talks"]:
        check("speaker_ids" in talk, talk["id"] + " speaker_ids")
        check(len(talk.get("speaker_ids") or []) == len(talk.get("speakers") or []), talk["id"] + " one id per speaker")
        linked += len(talk.get("speaker_ids") or [])
    people_talks = [e for e in org["entities"] if e.get("type") == "person" and (e.get("talk_ids") or e.get("from_talks"))]
    check(people_talks, "who's who lists speakers")
    check(all(not (e.get("from_talks") and e.get("image")) for e in org["entities"]), "talk speakers have no photo")
    sourced = [e for e in org["entities"] if e.get("affiliations")]
    check(all(a.get("source_url") and a.get("retrieved_at") and a.get("organisation") for e in sourced for a in e["affiliations"]), "every affiliation is sourced")
    by_id = {e["id"]: e for e in org["entities"]}
    talks_by_id = {t["id"]: t for t in raw["talks"]}
    loose = []
    for entity in sourced:
        for aff in entity["affiliations"]:
            org_name = aff["organisation"]
            if "," in org_name and not org_name.startswith("Indian Institute"):
                loose.append(org_name)
            if " at " in org_name.casefold() or "speaking" in org_name.casefold() or org_name.casefold().startswith("founder"):
                loose.append(org_name)
            talk = talks_by_id.get(aff.get("talk_id"))
            if aff.get("date"):
                if not talk or talk.get("date") != aff["date"]:
                    loose.append("date " + str(aff.get("talk_id")))
            elif talk and talk.get("date"):
                loose.append("missing date " + str(aff.get("talk_id")))
    check(not loose, "affiliations stay an organisation " + "; ".join(loose[:8]))
    for talk in raw["talks"]:
        for sid in talk.get("speaker_ids") or []:
            check(sid in by_id, talk["id"] + " speaker " + sid)
    print(f"mentions {linked}, people {len(people_talks)}, with affiliation {len(sourced)}")
    if fails:
        print(f"{len(fails)} failed")
        return 1
    print("all ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
