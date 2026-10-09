#!/usr/bin/env python3
"""CI deploy: privacy-term writer, gh-pages publish helper, and workflow contract.

  python3 tests/test_ci_deploy.py
"""
import io
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import ci_pages_diff
import ci_write_terms

PUBLISH = os.path.join(ROOT, "tools", "ci_gh_pages.sh")
DEPLOY = os.path.join(ROOT, ".github", "workflows", "deploy.yml")
MARKETS = os.path.join(ROOT, ".github", "workflows", "markets-refresh.yml")
SECRET = "super-secret-term-xyz-not-a-real-pattern"


def _git(cwd, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=check, capture_output=True, text=True,
    )


def _init_identity(path):
    _git(path, "config", "user.name", "Test")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "commit.gpgsign", "false")


class WriteTerms(unittest.TestCase):
    def test_empty_secret_is_refused_and_not_echoed(self):
        before = os.path.exists(ci_write_terms.DEST)
        err = io.StringIO()
        old = os.environ.pop("NC_PRIVATE_TERMS_JSON", None)
        try:
            with redirect_stderr(err):
                code = ci_write_terms.main()
        finally:
            if old is not None:
                os.environ["NC_PRIVATE_TERMS_JSON"] = old
        self.assertEqual(code, 1)
        self.assertIn("empty", err.getvalue())
        self.assertNotIn(SECRET, err.getvalue())
        self.assertEqual(os.path.exists(ci_write_terms.DEST), before)

    def test_invalid_json_does_not_quote_the_secret(self):
        path = os.path.join(tempfile.mkdtemp(prefix="nc-terms-"), "private_terms.json")
        self.addCleanup(shutil.rmtree, os.path.dirname(path), True)
        err = io.StringIO()
        with self.assertRaises(ci_write_terms.TermsError):
            with redirect_stderr(err):
                ci_write_terms.write_terms("not json " + SECRET, path)
        self.assertNotIn(SECRET, err.getvalue())
        self.assertFalse(os.path.exists(path))

    def test_bad_pattern_does_not_quote_the_pattern(self):
        path = os.path.join(tempfile.mkdtemp(prefix="nc-terms-"), "private_terms.json")
        self.addCleanup(shutil.rmtree, os.path.dirname(path), True)
        raw = json.dumps({"k": "(unclosed"})
        with self.assertRaises(ci_write_terms.TermsError) as caught:
            ci_write_terms.write_terms(raw, path)
        self.assertNotIn("unclosed", str(caught.exception))
        self.assertFalse(os.path.exists(path))

    def test_writes_mode_0600_and_prints_only_the_count(self):
        path = os.path.join(tempfile.mkdtemp(prefix="nc-terms-"), "private_terms.json")
        self.addCleanup(shutil.rmtree, os.path.dirname(path), True)
        raw = json.dumps({SECRET: "a^"})
        out = io.StringIO()
        with redirect_stdout(out):
            n = ci_write_terms.write_terms(raw, path)
        self.assertEqual(n, 1)
        self.assertNotIn(SECRET, out.getvalue())
        self.assertEqual(json.load(open(path, encoding="utf-8")), {SECRET: "a^"})
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_rejects_empty_object_list_and_non_strings(self):
        path = os.path.join(tempfile.mkdtemp(prefix="nc-terms-"), "private_terms.json")
        self.addCleanup(shutil.rmtree, os.path.dirname(path), True)
        for raw in ("{}", "[]", "   ", json.dumps({"k": 1}), json.dumps({"": "a"})):
            with self.assertRaises(ci_write_terms.TermsError):
                ci_write_terms.write_terms(raw, path)
            self.assertFalse(os.path.exists(path))


class PagesDiff(unittest.TestCase):
    def test_names_changed_tops_and_not_contents(self):
        tmp = tempfile.mkdtemp(prefix="nc-diff-")
        self.addCleanup(shutil.rmtree, tmp, True)
        site, pages = os.path.join(tmp, "site"), os.path.join(tmp, "pages")
        os.makedirs(os.path.join(site, "markets"))
        os.makedirs(os.path.join(pages, "markets"))
        os.makedirs(os.path.join(pages, "kiosk"))
        os.makedirs(os.path.join(pages, ".git"))
        open(os.path.join(site, "index.html"), "w").write("NEW\n")
        open(os.path.join(site, "markets", "index.html"), "w").write("same\n")
        open(os.path.join(site, "only-site.txt"), "w").write("secret-looking\n")
        open(os.path.join(pages, "index.html"), "w").write("OLD\n")
        open(os.path.join(pages, "markets", "index.html"), "w").write("same\n")
        open(os.path.join(pages, "kiosk", "index.html"), "w").write("keep\n")
        open(os.path.join(pages, ".git", "HEAD"), "w").write("ref: refs/heads/gh-pages\n")
        text = ci_pages_diff.compare(site, pages)
        self.assertIn("CI `site/`: 3 files", text)
        self.assertIn("current `gh-pages`: 3 files", text)
        self.assertIn("`only-site.txt`", text)
        self.assertIn("`kiosk`", text)
        self.assertIn("`index.html`", text)
        self.assertNotIn("`markets`", text)
        self.assertNotIn("secret-looking", text)
        self.assertNotIn("NEW", text)
        self.assertNotIn(".git", text)


class GhPagesPublish(unittest.TestCase):
    def _repo(self):
        tmp = tempfile.mkdtemp(prefix="nc-pages-")
        self.addCleanup(shutil.rmtree, tmp, True)
        bare = os.path.join(tmp, "bare.git")
        seed = os.path.join(tmp, "seed")
        dest = os.path.join(tmp, "dest")
        site = os.path.join(tmp, "site")
        keep = os.path.join(tmp, "keep.txt")
        _git(tmp, "init", "--bare", "-b", "gh-pages", bare)
        _git(tmp, "init", "-b", "gh-pages", seed)
        _init_identity(seed)
        os.makedirs(os.path.join(seed, "kiosk", "web"))
        open(os.path.join(seed, "CNAME"), "w").write("nordiccrypto.no\n")
        open(os.path.join(seed, "kiosk", "web", "index.html"), "w").write("kiosk\n")
        open(os.path.join(seed, "index.html"), "w").write("OLD\n")
        open(os.path.join(seed, "doomed.txt"), "w").write("gone\n")
        _git(seed, "add", "-A")
        _git(seed, "commit", "-m", "initial")
        _git(seed, "remote", "add", "origin", bare)
        _git(seed, "push", "origin", "gh-pages")
        _git(tmp, "clone", "--branch", "gh-pages", "--single-branch", bare, dest)
        _init_identity(dest)
        os.makedirs(os.path.join(site, "markets"))
        open(os.path.join(site, "CNAME"), "w").write("nordiccrypto.no\n")
        open(os.path.join(site, "index.html"), "w").write("NEW\n")
        open(os.path.join(site, "markets", "index.html"), "w").write("prices\n")
        open(keep, "w").write("# comment\nCNAME\nkiosk/\n")
        return tmp, bare, dest, site, keep

    def _run(self, dest, site, keep, msg="Publish test from main@abc [skip ci]"):
        return subprocess.run(
            ["bash", PUBLISH, dest, site, keep, msg],
            capture_output=True, text=True, timeout=30,
        )

    def test_publish_keeps_kiosk_and_replaces_the_tree(self):
        _tmp, bare, dest, site, keep = self._repo()
        r = self._run(dest, site, keep)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("gh-pages: pushed", r.stdout)
        self.assertEqual(open(os.path.join(dest, "index.html"), encoding="utf-8").read(), "NEW\n")
        self.assertEqual(open(os.path.join(dest, "kiosk", "web", "index.html"), encoding="utf-8").read(), "kiosk\n")
        self.assertEqual(open(os.path.join(dest, "CNAME"), encoding="utf-8").read(), "nordiccrypto.no\n")
        self.assertEqual(open(os.path.join(dest, "markets", "index.html"), encoding="utf-8").read(), "prices\n")
        self.assertFalse(os.path.exists(os.path.join(dest, "doomed.txt")))
        tip = _git(bare, "log", "-1", "--format=%an%n%s")
        self.assertEqual(tip.stdout.splitlines(), ["github-actions[bot]", "Publish test from main@abc [skip ci]"])

    def test_bad_cname_refuses_and_does_not_push(self):
        _tmp, bare, dest, site, keep = self._repo()
        before = _git(bare, "rev-parse", "gh-pages").stdout.strip()
        open(os.path.join(site, "CNAME"), "w").write("example.com\n")
        r = self._run(dest, site, keep)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("refusing", r.stderr)
        self.assertNotIn("gh-pages: pushed", r.stdout)
        self.assertEqual(_git(bare, "rev-parse", "gh-pages").stdout.strip(), before)
        self.assertEqual(open(os.path.join(dest, "index.html"), encoding="utf-8").read(), "OLD\n")

    def test_preview_build_is_refused(self):
        _tmp, bare, dest, site, keep = self._repo()
        before = _git(bare, "rev-parse", "gh-pages").stdout.strip()
        open(os.path.join(site, ".preview"), "w").write("local preview build – never publish\n")
        r = self._run(dest, site, keep)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("preview", r.stderr)
        self.assertEqual(_git(bare, "rev-parse", "gh-pages").stdout.strip(), before)

    def test_rejected_push_is_restaged_without_force(self):
        tmp, bare, dest, site, keep = self._repo()
        side = os.path.join(tmp, "side")
        _git(tmp, "clone", "--branch", "gh-pages", "--single-branch", bare, side)
        _init_identity(side)
        hook = os.path.join(dest, ".git", "hooks", "pre-push")
        flag = os.path.join(dest, ".git", "push-attempts")
        raced = os.path.join(side, "raced.txt")
        os.makedirs(os.path.dirname(hook), exist_ok=True)
        open(hook, "w").write(
            "#!/bin/bash\n"
            "unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX\n"
            f"flag={shlex.quote(flag)}\n"
            "n=0\n"
            '[ -f "$flag" ] && n=$(cat "$flag")\n'
            "n=$((n + 1))\n"
            'echo "$n" > "$flag"\n'
            'if [ "$n" -eq 1 ]; then\n'
            f"  echo raced > {shlex.quote(raced)}\n"
            f"  git -C {shlex.quote(side)} add raced.txt\n"
            f"  git -C {shlex.quote(side)} commit -m race\n"
            f"  git -C {shlex.quote(side)} push origin gh-pages\n"
            "  exit 1\n"
            "fi\n"
            "exit 0\n"
        )
        os.chmod(hook, 0o755)
        r = self._run(dest, site, keep, "Publish after race [skip ci]")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("non-fast-forward", r.stderr)
        self.assertIn("gh-pages: pushed", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(dest, "raced.txt")))
        self.assertEqual(open(os.path.join(dest, "index.html"), encoding="utf-8").read(), "NEW\n")
        self.assertEqual(open(os.path.join(dest, "kiosk", "web", "index.html"), encoding="utf-8").read(), "kiosk\n")
        parent = _git(dest, "rev-parse", "HEAD^").stdout.strip()
        race = _git(side, "rev-parse", "HEAD").stdout.strip()
        self.assertEqual(parent, race)
        script = open(PUBLISH, encoding="utf-8").read()
        self.assertNotIn("--force", script)
        self.assertNotIn("push -f", script)


class WorkflowContract(unittest.TestCase):
    def test_shared_concurrency_and_secret_handling(self):
        deploy = open(DEPLOY, encoding="utf-8").read()
        markets = open(MARKETS, encoding="utf-8").read()
        for text in (deploy, markets):
            self.assertIn("group: gh-pages-deploy", text)
            self.assertIn("cancel-in-progress: false", text)
            self.assertIn("queue: max", text)
            self.assertNotIn("cancel-in-progress: true", text)
        self.assertIn("NC_PRIVATE_TERMS_JSON", deploy)
        self.assertIn("NC_CI_DEPLOY", deploy)
        self.assertIn("tools/ci_write_terms.py", deploy)
        self.assertIn("tools/privacy_gate.py", deploy)
        self.assertIn("tools/text_gate.py", deploy)
        self.assertIn("tools/ci_gh_pages.sh", deploy)
        self.assertIn("workflow_dispatch", deploy)
        self.assertIn("[skip ci]", deploy)
        self.assertIn("github-actions[bot]", deploy)
        self.assertIn("fetch-depth: 1", deploy)
        self.assertNotIn("set -x", deploy)
        self.assertNotIn("upload-artifact", deploy)
        self.assertNotIn("build.py --preview", deploy)
        self.assertNotIn("--force", deploy)
        self.assertNotIn("git push", deploy)
        self.assertIn('branches: [main]', deploy)


if __name__ == "__main__":
    unittest.main()
