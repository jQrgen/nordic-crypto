#!/usr/bin/env python3
"""Re-checks the code profiles in data/developers.json against the public GitHub and GitLab APIs.

For every person: does each profile still exist, how many public repos it has, when it was last active
(newest public event on GitHub, last_activity_on on GitLab), and whether each notable repo still exists,
is still not a fork, and how many stars it has now. Contribution counts (commits, merged pull requests) are
not re-counted here; they need the search API and stay as recorded on the "checked" date.

No token is needed for basic checks. Without one, GitHub allows 60 requests an hour, which covers about
20 people; the run stops cleanly when the limit is reached and says how many were left. With GITHUB_TOKEN
(or GH_TOKEN) set, a full run takes a few minutes. Nothing private is read or written.

  python3 tools/check_dev_profiles.py                 # report only
  python3 tools/check_dev_profiles.py --ids a,b       # only these rows
  python3 tools/check_dev_profiles.py --write         # also update stars, last_push and "checked" in data/developers.json

Exit code 1 when a profile or a notable repo is gone or has become a fork (the row needs the editor), else 0."""
import argparse, datetime, json, os, sys, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "developers.json")
UA = "nordiccrypto.no developer-profile check (+https://github.com/jQrgen/nordic-crypto)"


class RateLimited(Exception):
    pass


def get(url, token=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    if token and "api.github.com" in url:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        if e.code in (403, 429) and "api.github.com" in url:
            raise RateLimited(url)
        raise


def check_github(login, notable, token):
    out = {"problems": [], "repos": {}}
    u = get(f"https://api.github.com/users/{urllib.parse.quote(login)}", token)
    if not u:
        out["problems"].append(f"GitHub profile {login} is gone")
        return out
    out["public_repos"] = u.get("public_repos")
    ev = get(f"https://api.github.com/users/{urllib.parse.quote(login)}/events/public?per_page=1", token) or []
    out["last_activity"] = (ev[0]["created_at"][:10] if ev else None) or (u.get("updated_at") or "")[:10]
    for n in notable:
        if n.get("kind") != "repo" or not n["url"].startswith("https://github.com/"):
            continue
        r = get("https://api.github.com/repos/" + n["name"], token)
        if not r:
            out["problems"].append(f"repo {n['name']} is gone")
        elif r.get("fork"):
            out["problems"].append(f"repo {n['name']} is now a fork")
        else:
            out["repos"][n["name"]] = {"stars": r["stargazers_count"], "last_push": (r.get("pushed_at") or "")[:10], "language": r.get("language")}
    return out


def check_gitlab(login):
    out = {"problems": []}
    users = get(f"https://gitlab.com/api/v4/users?username={urllib.parse.quote(login)}") or []
    if not users:
        out["problems"].append(f"GitLab profile {login} is gone")
        return out
    projects = get(f"https://gitlab.com/api/v4/users/{users[0]['id']}/projects?per_page=100&order_by=last_activity_at") or []
    own = [p for p in projects if not p.get("forked_from_project")]
    out["public_repos"] = len(own)
    out["last_activity"] = (own[0].get("last_activity_at") or "")[:10] if own else None
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ids", help="comma-separated row ids")
    ap.add_argument("--write", action="store_true", help="update stars, last_push and checked in data/developers.json")
    a = ap.parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    data = json.load(open(PATH, encoding="utf-8"))
    ids = set(a.ids.split(",")) if a.ids else None
    people = [p for p in data["people"] if not ids or p["id"] in ids]
    today = datetime.date.today().isoformat()
    bad, done = 0, 0
    try:
        for p in people:
            res = []
            for prof in p["profiles"]:
                login = prof.get("login") or prof["url"].rstrip("/").rsplit("/", 1)[-1]
                if prof["kind"] == "github":
                    res.append(("github", check_github(login, p["notable"], token)))
                elif prof["kind"] == "gitlab":
                    res.append(("gitlab", check_gitlab(login)))
            problems = [x for _k, r in res for x in r["problems"]]
            info = "; ".join(f'{k}: {r.get("public_repos")} public repos, last active {r.get("last_activity") or "?"}' for k, r in res if "public_repos" in r)
            print(f'{"FAIL" if problems else "ok  "} {p["id"]} ({p["status"]}) {info}' + (" | " + "; ".join(problems) if problems else ""))
            bad += bool(problems)
            done += 1
            if a.write and not problems:
                for _k, r in res:
                    for n in p["notable"]:
                        if n.get("kind") == "repo" and n["name"] in r.get("repos", {}):
                            n.update({k: v for k, v in r["repos"][n["name"]].items() if v is not None})
                p["checked"] = today
    except RateLimited:
        print(f"GitHub rate limit reached after {done} of {len(people)} people; set GITHUB_TOKEN or run again later with --ids.", file=sys.stderr)
    if a.write:
        data["updated"] = today
        json.dump(data, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("wrote " + os.path.relpath(PATH, ROOT))
    print(f"checked {done} of {len(people)}; {bad} need the editor")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
