#!/usr/bin/env python3
"""The nightly fetch on Actions commits the editor queue, not published stories.

  python3 -m unittest tests.test_ci_fetch
"""
import io
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
sys.path.insert(0, os.path.join(ROOT, "tools"))
import ci_fetch_queue

PUSH = os.path.join(ROOT, "tools", "ci_push_fetch_queue.sh")
PR = os.path.join(ROOT, "tools", "ci_fetch_pr.sh")
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "nightly-fetch.yml")
NIGHTLY = os.path.join(ROOT, "routines", "nightly-fetch.sh")
SECRET = "super-secret-term-xyz-not-a-real-pattern"
TITLE = "Awaiting piece the log must not treat as a commit subject"


def _git(cwd, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=check, capture_output=True, text=True,
    )


def _init(path):
    _git(path, "config", "user.name", "Test")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "commit.gpgsign", "false")


def _dump(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
        fh.write("\n")


def _story(sid, url, status, title="t"):
    return {"id": sid, "url": url, "title": title, "status": status, "country": "NO"}


def _event(sid, status, title="Meetup"):
    return {"id": sid, "title": title, "status": status, "url": "https://example.com/e/" + sid}


class Pack(unittest.TestCase):
    def _root(self):
        root = tempfile.mkdtemp(prefix="nc-queue-")
        self.addCleanup(shutil.rmtree, root, True)
        _dump(os.path.join(root, "data", "news.json"), {"items": [
            _story("a", "https://example.com/a", "published", "Already public"),
            _story("b", "https://example.com/b", "pending", "Already on main"),
        ]})
        _dump(os.path.join(root, "data", "events.json"), {"events": [
            _event("m", "pending", "Already listed"),
        ]})
        _dump(os.path.join(root, "queue", "pending", "news.json"), {"items": [
            _story("c", "https://example.com/c", "pending", "From yesterday"),
        ]})
        _dump(os.path.join(root, "queue", "pending", "events.json"), {"events": []})
        _dump(os.path.join(root, "queue", "review.json"), {
            "items_needing_summary": [
                {"id": "b", "title": "Already on main"},
                {"id": "c", "title": "From yesterday"},
            ],
            "events_pending": [{"id": "m", "title": "Already listed"}],
            "candidate_entities": [{"name": "Firi"}],
        })
        _dump(os.path.join(root, "state", "source_status.json"), {
            "feed-a": {"ok": True, "error": None},
            "feed-b": {"ok": False, "error": "Timeout"},
        })
        return root

    def test_pack_keeps_only_stories_that_are_not_on_main(self):
        root = self._root()
        ci_fetch_queue.prepare(root)
        news = json.load(open(os.path.join(root, "data", "news.json"), encoding="utf-8"))
        news["items"].append(_story("d", "https://example.com/d", "pending", TITLE))
        news["items"].append(_story("e", "https://example.com/e", "published", "Fetched but already decided"))
        _dump(os.path.join(root, "data", "news.json"), news)
        events = json.load(open(os.path.join(root, "data", "events.json"), encoding="utf-8"))
        events["events"].append(_event("f", "pending", "New meetup"))
        _dump(os.path.join(root, "data", "events.json"), events)
        review = json.load(open(os.path.join(root, "queue", "review.json"), encoding="utf-8"))
        review["items_needing_summary"].append({"id": "d", "title": TITLE})
        review["events_pending"].append({"id": "f", "title": "New meetup"})
        _dump(os.path.join(root, "queue", "review.json"), review)

        out = io.StringIO()
        with redirect_stdout(out):
            report = ci_fetch_queue.pack(root)
        pending = json.load(open(os.path.join(root, "queue", "pending", "news.json"), encoding="utf-8"))
        ids = [item["id"] for item in pending["items"]]
        self.assertEqual(ids, ["c", "d"])
        self.assertTrue(all(item["status"] == "pending" for item in pending["items"]))
        ev = json.load(open(os.path.join(root, "queue", "pending", "events.json"), encoding="utf-8"))
        self.assertEqual([item["id"] for item in ev["events"]], ["f"])
        queued = json.load(open(os.path.join(root, "queue", "review.json"), encoding="utf-8"))
        self.assertEqual([row["id"] for row in queued["items_needing_summary"]], ["c", "d"])
        self.assertEqual([row["id"] for row in queued["events_pending"]], ["f"])
        self.assertEqual(queued["candidate_entities"], [{"name": "Firi"}])
        self.assertEqual(report["new_stories"], 1)
        self.assertEqual(report["new_events"], 1)
        self.assertEqual(report["awaiting_stories"], 2)
        self.assertEqual(report["awaiting_events"], 1)
        self.assertEqual(report["new_stories_by_country"], {"NO": 1})
        self.assertEqual(report["sources_failed"], 1)
        self.assertEqual(report["sources_total"], 2)
        self.assertNotIn(TITLE, out.getvalue())
        text = ci_fetch_queue.summary_text(report)
        self.assertIn("New stories: 1", text)
        self.assertIn("New events: 1", text)
        self.assertIn("Awaiting the editor: 2 stories, 1 event", text)
        self.assertIn("1/2 sources failed", text)
        self.assertNotIn(TITLE, text)
        self.assertNotIn(SECRET, text)
        self.assertNotIn(TITLE, ci_fetch_queue.commit_message(report))

    def test_a_published_row_in_the_pending_file_is_refused(self):
        root = self._root()
        _dump(os.path.join(root, "queue", "pending", "news.json"), {"items": [
            _story("z", "https://example.com/z", "published", TITLE),
        ]})
        with self.assertRaises(ci_fetch_queue.QueueError) as caught:
            ci_fetch_queue.prepare(root)
        self.assertNotIn(TITLE, str(caught.exception))
        self.assertNotIn(SECRET, str(caught.exception))

    def test_stage_does_not_copy_or_print_the_term_list(self):
        root = self._root()
        ci_fetch_queue.prepare(root)
        ci_fetch_queue.pack(root)
        _dump(os.path.join(root, "state", "private_terms.json"), {SECRET: "a^"})
        os.chmod(os.path.join(root, "state", "private_terms.json"), stat.S_IRUSR | stat.S_IWUSR)
        dest = tempfile.mkdtemp(prefix="nc-stage-")
        self.addCleanup(shutil.rmtree, dest, True)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            ci_fetch_queue.stage(root, dest)
        blob = out.getvalue() + err.getvalue()
        for dirpath, _dirs, names in os.walk(dest):
            for name in names:
                with open(os.path.join(dirpath, name), encoding="utf-8") as fh:
                    blob += fh.read()
        self.assertNotIn(SECRET, blob)
        self.assertFalse(os.path.exists(os.path.join(dest, "state", "private_terms.json")))
        self.assertFalse(os.path.exists(os.path.join(dest, "state", "http_cache.json")))

    def test_promotion_refuses_a_new_pending_row(self):
        before = {"items": [_story("a", "https://example.com/a", "published")]}
        ok = {"items": before["items"] + [_story("d", "https://example.com/d", "published")]}
        bad = {"items": before["items"] + [_story("d", "https://example.com/d", "pending")]}
        stay = {"items": [_story("b", "https://example.com/b", "pending"), _story("d", "https://example.com/d", "published")]}
        self.assertTrue(ci_fetch_queue.promotion_ok(before, ok, "items"))
        self.assertFalse(ci_fetch_queue.promotion_ok(before, bad, "items"))
        self.assertTrue(ci_fetch_queue.promotion_ok({"items": [_story("b", "https://example.com/b", "pending")]}, stay, "items"))
        root = tempfile.mkdtemp(prefix="nc-lint-")
        self.addCleanup(shutil.rmtree, root, True)
        before_path = os.path.join(root, "before.json")
        after_path = os.path.join(root, "after.json")
        _dump(before_path, before)
        _dump(after_path, bad)
        err = io.StringIO()
        with redirect_stderr(err):
            code = ci_fetch_queue.main(["lint-promotion", "news", before_path, after_path])
        self.assertEqual(code, 1)
        self.assertIn("awaiting the editor", err.getvalue())
        _dump(after_path, ok)
        self.assertEqual(ci_fetch_queue.main(["lint-promotion", "news", before_path, after_path]), 0)

    def test_check_index_refuses_main_and_the_term_list(self):
        ci_fetch_queue.check_paths(["queue/review.json", "queue/pending/news.json"], ci_fetch_queue.ALLOWED)
        for path in ("data/news.json", "data/events.json", "site/index.html", "state/http_cache.json", "state/private_terms.json"):
            with self.assertRaises(ci_fetch_queue.QueueError):
                ci_fetch_queue.check_paths([path], ci_fetch_queue.ALLOWED)
        ci_fetch_queue.check_paths(["queue/approved.json"], ci_fetch_queue.TOLERATED)
        with self.assertRaises(ci_fetch_queue.QueueError):
            ci_fetch_queue.check_paths(["queue/approved.json"], ci_fetch_queue.ALLOWED)


class Push(unittest.TestCase):
    def _repo(self):
        tmp = tempfile.mkdtemp(prefix="nc-fetch-git-")
        self.addCleanup(shutil.rmtree, tmp, True)
        bare = os.path.join(tmp, "bare.git")
        work = os.path.join(tmp, "work")
        _git(tmp, "init", "--bare", "-b", "main", bare)
        _git(tmp, "clone", bare, work)
        _init(work)
        _dump(os.path.join(work, "data", "news.json"), {"items": [
            _story("a", "https://example.com/a", "published", "Already public"),
        ]})
        _dump(os.path.join(work, "data", "events.json"), {"events": []})
        _git(work, "add", "data")
        _git(work, "commit", "-m", "main")
        _git(work, "push", "origin", "main")
        return bare, work

    def _queue(self, work):
        _dump(os.path.join(work, "queue", "pending", "news.json"), {"items": [
            _story("d", "https://example.com/d", "pending", TITLE),
        ]})
        _dump(os.path.join(work, "queue", "pending", "events.json"), {"events": [
            _event("f", "pending", "New meetup"),
        ]})
        _dump(os.path.join(work, "queue", "review.json"), {
            "items_needing_summary": [{"id": "d", "title": TITLE}],
            "events_pending": [{"id": "f"}],
        })
        _dump(os.path.join(work, "queue", "fetch_report.json"), {
            "new_stories": 1, "new_events": 1, "awaiting_stories": 1, "awaiting_events": 1,
            "sources_failed": 0, "sources_total": 3, "sources_ok": True, "health": "fetch health: 0/3 sources failed (0%)",
        })
        _dump(os.path.join(work, "state", "teasers.json"), {"d": "teaser"})
        _dump(os.path.join(work, "state", "http_cache.json"), {"https://example.com/feed": {"etag": "abc", "parsed": True}})

    def _run(self, work, *args):
        env = os.environ.copy()
        env["NC_FETCH_REPO"] = work
        env["GIT_TERMINAL_PROMPT"] = "0"
        return subprocess.run(
            ["bash", PUSH, *args], cwd=work, env=env, capture_output=True, text=True,
        )

    def _show(self, bare, spec):
        return _git(bare, "show", spec, check=False)

    def test_push_commits_the_queue_and_leaves_main_alone(self):
        bare, work = self._repo()
        main_sha = _git(bare, "rev-parse", "main").stdout.strip()
        self._queue(work)
        dirty = _story("nope", "https://example.com/nope", "pending", "must not reach main")
        news = json.load(open(os.path.join(work, "data", "news.json"), encoding="utf-8"))
        news["items"].append(dirty)
        _dump(os.path.join(work, "data", "news.json"), news)
        r = self._run(work, "push")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("fetch-queue: pushed", r.stdout)
        self.assertNotIn(TITLE, r.stdout + r.stderr)
        self.assertEqual(_git(bare, "rev-parse", "main").stdout.strip(), main_sha)
        self.assertNotEqual(_git(bare, "rev-parse", "refs/heads/gh-pages", check=False).returncode, 0)
        names = _git(bare, "ls-tree", "-r", "--name-only", "fetch-queue").stdout.splitlines()
        self.assertIn("queue/pending/news.json", names)
        self.assertNotIn("state/private_terms.json", names)
        self.assertNotIn("state/http_cache.json", names)
        queued = json.loads(self._show(bare, "fetch-queue:queue/pending/news.json").stdout)
        self.assertEqual([item["id"] for item in queued["items"]], ["d"])
        self.assertTrue(all(item["status"] == "pending" for item in queued["items"]))
        on_branch = self._show(bare, "fetch-queue:data/news.json").stdout
        on_main = self._show(bare, "main:data/news.json").stdout
        self.assertEqual(on_branch, on_main)
        self.assertNotIn("must not reach main", on_branch)
        subject = _git(bare, "log", "-1", "--format=%s", "fetch-queue").stdout.strip()
        self.assertEqual(subject, "Fetch queue: 1 new story, 1 new event [skip ci]")
        self.assertNotIn(TITLE, subject)
        again = self._run(work, "push")
        self.assertEqual(again.returncode, 0, again.stderr + again.stdout)
        self.assertIn("no changes", again.stdout)

    def test_a_published_story_is_not_pushed(self):
        bare, work = self._repo()
        before = _git(bare, "rev-parse", "main").stdout.strip()
        self._queue(work)
        _dump(os.path.join(work, "queue", "pending", "news.json"), {"items": [
            _story("z", "https://example.com/z", "published", TITLE),
        ]})
        r = self._run(work, "push")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn(TITLE, r.stdout + r.stderr)
        self.assertNotIn("fetch-queue: pushed", r.stdout)
        self.assertEqual(_git(bare, "rev-parse", "main").stdout.strip(), before)
        self.assertNotEqual(_git(bare, "rev-parse", "fetch-queue", check=False).returncode, 0)

    def test_the_term_list_is_not_committed_or_printed(self):
        bare, work = self._repo()
        before = _git(bare, "rev-parse", "main").stdout.strip()
        self._queue(work)
        _dump(os.path.join(work, "state", "private_terms.json"), {SECRET: "a^"})
        r = self._run(work, "push")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn(SECRET, r.stdout + r.stderr)
        self.assertNotIn("fetch-queue: pushed", r.stdout)
        self.assertEqual(_git(bare, "rev-parse", "main").stdout.strip(), before)
        self.assertNotEqual(_git(bare, "rev-parse", "fetch-queue", check=False).returncode, 0)

    def test_restore_brings_the_queue_back_and_refuses_a_term_list(self):
        bare, work = self._repo()
        self._queue(work)
        pushed = self._run(work, "push")
        self.assertEqual(pushed.returncode, 0, pushed.stderr + pushed.stdout)
        _git(work, "checkout", "main")
        shutil.rmtree(os.path.join(work, "queue"), ignore_errors=True)
        restored = self._run(work, "restore")
        self.assertEqual(restored.returncode, 0, restored.stderr + restored.stdout)
        self.assertTrue(os.path.exists(os.path.join(work, "queue", "pending", "news.json")))
        self.assertEqual(_git(work, "diff", "--cached", "--name-only").stdout.strip(), "")
        # A term list committed on the branch is not copied back onto main.
        # The next push sees it on fetch-queue and refuses, without printing it.
        shutil.rmtree(os.path.join(work, "queue"), ignore_errors=True)
        shutil.rmtree(os.path.join(work, "state"), ignore_errors=True)
        _git(work, "checkout", "fetch-queue")
        _dump(os.path.join(work, "state", "private_terms.json"), {SECRET: "a^"})
        _git(work, "add", "-f", "state/private_terms.json")
        _git(work, "commit", "-m", "bad")
        _git(work, "push", "origin", "HEAD:fetch-queue")
        _git(work, "checkout", "main")
        restored_bad = self._run(work, "restore")
        self.assertEqual(restored_bad.returncode, 0, restored_bad.stderr + restored_bad.stdout)
        self.assertFalse(os.path.exists(os.path.join(work, "state", "private_terms.json")))
        self.assertNotIn(SECRET, restored_bad.stdout + restored_bad.stderr)
        refused = self._run(work, "push")
        self.assertNotEqual(refused.returncode, 0)
        self.assertNotIn(SECRET, refused.stdout + refused.stderr)
        self.assertNotIn("fetch-queue: pushed", refused.stdout)
        tip = _git(bare, "log", "-1", "--format=%s", "fetch-queue").stdout.strip()
        self.assertEqual(tip, "bad")


class PullRequest(unittest.TestCase):
    def test_opens_a_pull_request_and_does_not_merge(self):
        script = open(PR, encoding="utf-8").read()
        push = open(PUSH, encoding="utf-8").read()
        self.assertNotIn("pr merge", script)
        self.assertNotIn("gh pr merge", script)
        code = "\n".join(line for line in push.splitlines() if not line.strip().startswith("#"))
        self.assertNotIn("--force", code)
        self.assertNotIn("HEAD:main", code)
        self.assertNotIn("gh-pages", code)
        self.assertIn("HEAD:fetch-queue", code)

        tmp = tempfile.mkdtemp(prefix="nc-pr-")
        self.addCleanup(shutil.rmtree, tmp, True)
        bare = os.path.join(tmp, "bare.git")
        work = os.path.join(tmp, "work")
        bindir = os.path.join(tmp, "bin")
        os.makedirs(bindir)
        log = os.path.join(tmp, "gh.log")
        body_copy = os.path.join(tmp, "body.md")
        open(os.path.join(bindir, "gh"), "w", encoding="utf-8").write(
            "#!/bin/bash\n"
            f"printf '%s\\n' \"$*\" >> {log!r}\n"
            "args=(\"$@\")\n"
            "for i in \"${!args[@]}\"; do\n"
            "  if [ \"${args[$i]}\" = \"--body-file\" ]; then\n"
            f"    cat \"${{args[$((i+1))]}}\" > {body_copy!r}\n"
            "  fi\n"
            "done\n"
            "if [ \"$1\" = \"pr\" ] && [ \"$2\" = \"list\" ]; then exit 0; fi\n"
            "if [ \"$1\" = \"pr\" ] && [ \"$2\" = \"create\" ]; then echo https://example.test/pr/7; exit 0; fi\n"
            "exit 0\n"
        )
        os.chmod(os.path.join(bindir, "gh"), 0o755)
        _git(tmp, "init", "--bare", "-b", "main", bare)
        _git(tmp, "clone", bare, work)
        _init(work)
        open(os.path.join(work, "README"), "w").write("hi\n")
        _git(work, "add", "README")
        _git(work, "commit", "-m", "main")
        _git(work, "push", "origin", "main")
        _git(work, "checkout", "-b", "fetch-queue")
        _dump(os.path.join(work, "queue", "fetch_report.json"), {
            "new_stories": 2, "new_events": 1, "awaiting_stories": 2, "awaiting_events": 1,
            "sources_failed": 0, "sources_total": 4, "sources_ok": True, "health": "fetch health: 0/4 sources failed (0%)",
        })
        _git(work, "add", "-f", "queue/fetch_report.json")
        _git(work, "commit", "-m", "queue")
        _git(work, "push", "origin", "fetch-queue")
        env = os.environ.copy()
        env["NC_FETCH_REPO"] = work
        env["GH_TOKEN"] = "test-token"
        env["NC_PRIVATE_TERMS_JSON"] = SECRET
        env["PATH"] = bindir + os.pathsep + env.get("PATH", "")
        env["GITHUB_STEP_SUMMARY"] = os.path.join(tmp, "summary.md")
        r = subprocess.run(["bash", PR], cwd=work, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("https://example.test/pr/7", r.stdout)
        recorded = open(log, encoding="utf-8").read()
        self.assertIn("pr create", recorded)
        self.assertNotIn("merge", recorded)
        body = open(body_copy, encoding="utf-8").read()
        self.assertIn("Do not merge", body)
        self.assertIn("New stories: 2", body)
        self.assertNotIn(SECRET, body)
        self.assertNotIn(SECRET, r.stdout + r.stderr)
        self.assertIn("https://example.test/pr/7", open(env["GITHUB_STEP_SUMMARY"], encoding="utf-8").read())


class WorkflowContract(unittest.TestCase):
    def test_schedule_gate_cache_and_secrets(self):
        text = open(WORKFLOW, encoding="utf-8").read()
        nightly = open(NIGHTLY, encoding="utf-8").read()
        self.assertIn('cron: "41 1 * * *"', text)
        self.assertIn("workflow_dispatch", text)
        self.assertIn("group: nightly-fetch", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("queue: max", text)
        self.assertNotIn("cancel-in-progress: true", text)
        self.assertNotIn("group: gh-pages-deploy", text)
        self.assertIn("timeout-minutes: 240", text)
        self.assertIn("vars.NC_CI_FETCH == 'true'", text)
        self.assertIn("vars.NC_CI_FETCH != 'true'", text)
        self.assertIn("NC_PRIVATE_TERMS_JSON", text)
        self.assertIn("tools/ci_write_terms.py", text)
        self.assertIn("tools/privacy_gate.py", text)
        self.assertIn("state/private_terms.json", text)
        self.assertIn("actions/cache/restore@v4", text)
        self.assertIn("actions/cache/save@v4", text)
        self.assertIn("state/http_cache.json", text)
        self.assertIn("routines/nightly-fetch.sh", text)
        self.assertIn('NIGHTLY_CI: "1"', text)
        self.assertIn("fetch-queue", text)
        self.assertIn("tools/ci_push_fetch_queue.sh", text)
        self.assertIn("tools/ci_fetch_pr.sh", text)
        self.assertNotIn("set -x", text)
        self.assertNotIn("echo \"$NC_PRIVATE_TERMS_JSON\"", text)
        self.assertNotIn("upload-artifact", text)
        self.assertNotIn("--force", text)
        self.assertNotIn("HEAD:main", text)
        self.assertNotIn("gh pr merge", text)
        self.assertNotIn("build.py --preview", text)
        self.assertIn("actions: write", text)
        ci = nightly.split('if [[ "${NIGHTLY_CI:-}" == 1 ]]; then', 1)[1].split("say \"-- fetch (./fetch.sh --days 3)\"", 1)[0]
        self.assertIn("fetch.py", ci)
        self.assertIn("fetch_health.py", ci)
        self.assertNotIn("tipserver", ci)
        self.assertNotIn("build.sh", ci)
        self.assertNotIn("crosssite_handoff", ci)


if __name__ == "__main__":
    unittest.main()
