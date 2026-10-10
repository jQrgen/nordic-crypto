#!/usr/bin/env python3
"""Editor queue for the nightly fetch on Actions.

prepare remembers which stories and events are already on main, then folds
queue/pending back into the working data files so this run can see them.

pack writes queue/pending with stories and events that are still awaiting the
editor and were not already on main, plus queue/fetch_report.json (counts).
It does not print story text. It does not read or write state/private_terms.json.

The files under queue/pending are not what the public build publishes. data/news.json
and data/events.json on main stay the published files.
"""
import json
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Force-added onto the fetch-queue branch. Nothing else.
ALLOWED = (
    "queue/review.json",
    "queue/pending/news.json",
    "queue/pending/events.json",
    "queue/fetch_report.json",
    "state/teasers.json",
    "state/html_seen.json",
    "state/html_lists.json",
    "state/source_status.json",
)
# Already on the branch when the editor has written decisions there. The fetch does not create it.
TOLERATED = ALLOWED + ("queue/approved.json",)
BASELINE = os.path.join("state", "fetch_baseline.json")
TERMS = os.path.join("state", "private_terms.json")


class QueueError(Exception):
    """A problem we can report without quoting a story or the term list."""


def _root(path):
    return os.path.abspath(path or ROOT)


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default


def _save(path, data):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


def norm(url):
    """Host and path, so a tracking parameter does not make a second story."""
    if not url:
        return ""
    parsed = urllib.parse.urlparse(str(url).strip())
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host + (parsed.path.rstrip("/") or "/")


def _ids(items):
    return {item.get("id") for item in items or [] if item.get("id")}


def _urls(items):
    return {norm(item.get("url")) for item in items or [] if item.get("url")}


def prepare(root):
    """Record main's stories and events, then fold yesterday's pending rows into the working files."""
    root = _root(root)
    news_path = os.path.join(root, "data", "news.json")
    events_path = os.path.join(root, "data", "events.json")
    news = _load(news_path, {"items": []})
    events = _load(events_path, {"events": []})
    items = list(news.get("items") or [])
    rows = list(events.get("events") or [])
    baseline = {
        "story_ids": sorted(_ids(items)),
        "story_urls": sorted(u for u in _urls(items) if u),
        "event_ids": sorted(_ids(rows)),
    }
    pending_news = _load(os.path.join(root, "queue", "pending", "news.json"), {"items": []})
    pending_events = _load(os.path.join(root, "queue", "pending", "events.json"), {"events": []})
    items = _overlay(items, pending_news.get("items") or [], "story")
    rows = _overlay(rows, pending_events.get("events") or [], "event")
    baseline["seen_story_ids"] = sorted(_ids(items))
    baseline["seen_event_ids"] = sorted(_ids(rows))
    news["items"] = items
    events["events"] = rows
    _save(news_path, news)
    _save(events_path, events)
    _save(os.path.join(root, BASELINE), baseline)
    print(
        f"queue prepare: {len(baseline['story_ids'])} stories already on main, "
        f"{len(items) - len(baseline['story_ids'])} pending folded in"
    )
    return baseline


def _overlay(base, extra, kind):
    seen_ids = _ids(base)
    seen_urls = _urls(base)
    out = list(base)
    for item in extra:
        if not isinstance(item, dict) or item.get("status") != "pending":
            raise QueueError(f"queue/pending has a {kind} that is not awaiting the editor")
        if item.get("id") in seen_ids or (item.get("url") and norm(item.get("url")) in seen_urls):
            continue
        out.append(item)
        if item.get("id"):
            seen_ids.add(item["id"])
        url = norm(item.get("url"))
        if url:
            seen_urls.add(url)
    return out


def _on_main(item, ids, urls):
    if item.get("id") and item.get("id") in ids:
        return True
    url = norm(item.get("url"))
    return bool(url and url in urls)


def pack(root):
    """Write the awaiting-editor files and the count report. Leave main's data files on disk as the fetch left them."""
    root = _root(root)
    baseline_path = os.path.join(root, BASELINE)
    if not os.path.exists(baseline_path):
        raise QueueError("no fetch baseline; run prepare before the fetch")
    baseline = _load(baseline_path, {})
    main_story_ids = set(baseline.get("story_ids") or [])
    main_story_urls = set(baseline.get("story_urls") or [])
    main_event_ids = set(baseline.get("event_ids") or [])
    seen_story_ids = set(baseline.get("seen_story_ids") or [])
    seen_event_ids = set(baseline.get("seen_event_ids") or [])

    news = _load(os.path.join(root, "data", "news.json"), {"items": []})
    events = _load(os.path.join(root, "data", "events.json"), {"events": []})
    review = _load(os.path.join(root, "queue", "review.json"), {"items_needing_summary": [], "candidate_entities": []})

    awaiting_news = []
    new_news = []
    for item in news.get("items") or []:
        if item.get("status") != "pending":
            continue
        if _on_main(item, main_story_ids, main_story_urls):
            continue
        awaiting_news.append(item)
        if item.get("id") not in seen_story_ids:
            new_news.append(item)

    awaiting_events = []
    new_events = []
    for item in events.get("events") or []:
        if item.get("status") != "pending":
            continue
        if item.get("id") in main_event_ids:
            continue
        awaiting_events.append(item)
        if item.get("id") not in seen_event_ids:
            new_events.append(item)

    keep_ids = {item.get("id") for item in awaiting_news}
    keep_events = {item.get("id") for item in awaiting_events}
    review["items_needing_summary"] = [
        row for row in (review.get("items_needing_summary") or []) if row.get("id") in keep_ids
    ]
    review["events_pending"] = [
        row for row in (review.get("events_pending") or []) if row.get("id") in keep_events
    ]
    _save(os.path.join(root, "queue", "review.json"), review)
    _save(os.path.join(root, "queue", "pending", "news.json"), {"items": awaiting_news})
    _save(os.path.join(root, "queue", "pending", "events.json"), {"events": awaiting_events})

    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import fetch_health

    status = _load(os.path.join(root, "state", "source_status.json"), {})
    ok, health = fetch_health.assess(status)
    by_country = {}
    for item in new_news:
        country = item.get("country") or "?"
        by_country[country] = by_country.get(country, 0) + 1
    failed, total = _health_counts(health)
    report = {
        "new_stories": len(new_news),
        "new_events": len(new_events),
        "awaiting_stories": len(awaiting_news),
        "awaiting_events": len(awaiting_events),
        "new_stories_by_country": by_country,
        "sources_failed": failed,
        "sources_total": total,
        "sources_ok": bool(ok),
        "health": health,
    }
    _save(os.path.join(root, "queue", "fetch_report.json"), report)
    print(
        f"queue: {len(awaiting_news)} stories and {len(awaiting_events)} events awaiting the editor "
        f"({len(new_news)} new stories, {len(new_events)} new events)"
    )
    return report


def _health_counts(health):
    """Parse 'fetch health: 2/140 sources failed' without trusting the rest of the line."""
    line = (health or "").splitlines()[0] if health else ""
    try:
        left = line.split(":", 1)[1].strip().split()[0]
        failed, total = left.split("/")
        return int(failed), int(total)
    except (IndexError, ValueError):
        return 0, 0


def _count(n, one, many):
    n = int(n or 0)
    return f"{n} {one if n == 1 else many}"


def summary_text(report, missing=False):
    """Job summary. Counts and the health lines only."""
    lines = ["### Nightly fetch", ""]
    if missing or not report:
        lines.append("The fetch did not finish, so `fetch-queue` was not updated.")
        lines.append("Nothing was pushed to `main` or `gh-pages`.")
        return "\n".join(lines) + "\n"
    lines.append(f"- New stories: {report.get('new_stories', 0)}")
    lines.append(f"- New events: {report.get('new_events', 0)}")
    by_country = report.get("new_stories_by_country") or {}
    if by_country:
        bits = ", ".join(f"{key} {by_country[key]}" for key in sorted(by_country))
        lines.append(f"- New stories by country: {bits}")
    lines.append(
        "- Awaiting the editor: "
        f"{_count(report.get('awaiting_stories', 0), 'story', 'stories')}, "
        f"{_count(report.get('awaiting_events', 0), 'event', 'events')}"
    )
    lines.append(
        "- Source health: "
        f"{report.get('sources_failed', 0)}/{report.get('sources_total', 0)} sources failed"
    )
    health = (report.get("health") or "").strip()
    if health:
        lines.extend(["", "```", health, "```"])
    lines.append("")
    lines.append("Nothing in this run is published. `main` and `gh-pages` are not pushed by the fetch.")
    if not report.get("sources_ok"):
        lines.append("Source health failed, so the queue branch is left as it was.")
    return "\n".join(lines) + "\n"


def commit_message(report):
    report = report or {}
    return (
        "Fetch queue: "
        f"{_count(report.get('new_stories', 0), 'new story', 'new stories')}, "
        f"{_count(report.get('new_events', 0), 'new event', 'new events')} [skip ci]"
    )


def pr_body(report):
    """Pull request text. No story bodies and no term list."""
    counts = summary_text(report).strip()
    return f"""{counts}

Do not merge this pull request. Merging it does not publish a story, and it should not land the editor queue on `main`.

`fetch-queue` is the nightly fetch. Stories and events here are `pending`: awaiting the editor, not approved and not published. `data/news.json` and `data/events.json` on this branch match `main`. The public build does not read `queue/pending/`.

On this branch, and not published:

- `queue/review.json` — `items_needing_summary` and `events_pending`
- `queue/pending/news.json` — pending stories that are not already in `data/news.json` on `main`
- `queue/pending/events.json` — pending events that are not already in `data/events.json` on `main`
- `queue/fetch_report.json` — the counts above
- `state/teasers.json`, `state/html_seen.json`, `state/html_lists.json`, `state/source_status.json` — what the next fetch needs

`state/private_terms.json` is not on this branch. If that file is ever committed there, the job refuses to push. `state/http_cache.json` is an Actions cache, not a commit.

How the editor approves a story so it can reach the site:

1. Read this branch. Leave this pull request open. The next nightly run updates it. Do not commit on `fetch-queue`; that commit would be rebased away if the push is rejected.
2. Branch from `main`. Copy only the rows you are approving or rejecting from `queue/pending/news.json` into `data/news.json` (and the event rows into `data/events.json`). Leave every other pending row out.
3. Write the decision in `queue/approved.json` (English summary, or `rejected`). That file is gitignored. It stays on the checkout that applies the decision.
4. Run `python3 tools/apply_approvals.py` for stories. For an event, add its id to `events.approve` or `events.reject` and let the build archive approved events the way the box does.
5. Before committing, run `python3 tools/ci_fetch_queue.py lint-promotion news BEFORE.json AFTER.json` (and `lint-promotion events` for the events file). It refuses a new row that is still `pending`.
6. Open a pull request into `main` with the public files only (`data/news.json`, and `archive/events.json` when the build wrote it). Do not commit `queue/` or `state/`.
7. Merging that pull request is the approval. The deploy workflow publishes the site from `main`. A story is on the site only when its status is `published` and it has a summary.

The next fetch sees approved URLs on `main` and drops them from this queue.
"""


def promotion_ok(before, after, key):
    """A new row must be published, rejected, or merged. Rows already on main may stay pending."""
    previous = {item.get("id") for item in (before or {}).get(key) or [] if isinstance(item, dict)}
    for item in (after or {}).get(key) or []:
        if not isinstance(item, dict) or item.get("id") in previous:
            continue
        if item.get("status") not in ("published", "rejected", "merged"):
            return False
    return True


def stage(root, dest):
    """Copy the committable files into `dest`. Does not copy the term list or the HTTP cache."""
    root = _root(root)
    dest = _root(dest)
    if os.path.basename(dest) in ("", "/", "."):
        raise QueueError("refusing to stage over the repo")
    for rel in ALLOWED:
        src = os.path.join(root, rel)
        if not os.path.isfile(src):
            continue
        target = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(src, "rb") as fh:
            data = fh.read()
        with open(target, "wb") as fh:
            fh.write(data)
    terms = os.path.join(dest, TERMS)
    if os.path.exists(terms):
        os.remove(terms)
        raise QueueError("refusing: the term list was staged")


def install(root, src):
    """Copy a staged tree back. Only the allowed relative paths."""
    root = _root(root)
    src = _root(src)
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [name for name in dirnames if name != ".git"]
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, src).replace("\\", "/")
            if rel not in ALLOWED:
                raise QueueError("refusing to install a file that is not part of the editor queue")
            target = os.path.join(root, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(full, "rb") as fh:
                data = fh.read()
            with open(target, "wb") as fh:
                fh.write(data)


def check(root):
    """Refuse a pending file that contains anything other than a pending row, or a term list in the tree."""
    root = _root(root)
    if os.path.exists(os.path.join(root, TERMS)):
        raise QueueError("refusing: state/private_terms.json is in the queue tree")
    news = _load(os.path.join(root, "queue", "pending", "news.json"), None)
    events = _load(os.path.join(root, "queue", "pending", "events.json"), None)
    if news is not None:
        bad = [item for item in (news.get("items") or []) if not isinstance(item, dict) or item.get("status") != "pending"]
        if bad:
            raise QueueError("refusing: queue/pending/news.json has a story that is not awaiting the editor")
    if events is not None:
        bad = [item for item in (events.get("events") or []) if not isinstance(item, dict) or item.get("status") != "pending"]
        if bad:
            raise QueueError("refusing: queue/pending/events.json has an event that is not awaiting the editor")


def check_paths(paths, allowed):
    allowed = set(allowed)
    for raw in paths:
        path = (raw or "").strip().replace("\\", "/")
        if not path:
            continue
        if path.startswith("../") or "/../" in path or path.startswith("/"):
            raise QueueError("refusing a path outside the repo")
        if path == TERMS or path.endswith("/private_terms.json") or "private_terms" in path:
            raise QueueError("refusing: state/private_terms.json must not be committed")
        if path not in allowed:
            raise QueueError(f"refusing to commit {path}")


def _print_paths(paths):
    for path in paths:
        print(path)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--root":
        if len(argv) < 3:
            print("usage: ci_fetch_queue.py --root DIR COMMAND", file=sys.stderr)
            return 2
        os.environ["NC_ROOT"] = argv[1]
        argv = argv[2:]
    root = os.environ.get("NC_ROOT") or ROOT
    if not argv:
        print("usage: ci_fetch_queue.py COMMAND", file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    try:
        if cmd == "prepare":
            prepare(root)
        elif cmd == "pack":
            pack(root)
        elif cmd == "stage":
            if len(rest) != 1:
                raise QueueError("usage: stage DIR")
            stage(root, rest[0])
        elif cmd == "install":
            if len(rest) != 1:
                raise QueueError("usage: install DIR")
            install(root, rest[0])
            check(root)
        elif cmd == "check":
            check(rest[0] if rest else root)
        elif cmd == "check-index":
            check_paths(sys.stdin.read().splitlines(), ALLOWED)
        elif cmd == "check-diff":
            check_paths(sys.stdin.read().splitlines(), TOLERATED)
        elif cmd == "allowed-paths":
            _print_paths(ALLOWED)
        elif cmd == "summary":
            report = None if "--missing" in rest else _load(os.path.join(root, "queue", "fetch_report.json"), None)
            sys.stdout.write(summary_text(report, missing=report is None))
        elif cmd == "commit-message":
            print(commit_message(_load(os.path.join(root, "queue", "fetch_report.json"), {})))
        elif cmd == "pr-body":
            sys.stdout.write(pr_body(_load(os.path.join(root, "queue", "fetch_report.json"), None)))
        elif cmd == "lint-promotion":
            if len(rest) != 3 or rest[0] not in ("news", "events"):
                raise QueueError("usage: lint-promotion news|events BEFORE.json AFTER.json")
            key = "items" if rest[0] == "news" else "events"
            before = _load(rest[1], None)
            after = _load(rest[2], None)
            if before is None or after is None:
                raise QueueError("lint-promotion: could not read both files")
            if not promotion_ok(before, after, key):
                raise QueueError("refusing: a new row is still awaiting the editor")
            print("promotion: ok")
        else:
            raise QueueError(f"unknown command {cmd}")
    except QueueError as ex:
        print(f"::error::{ex}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
