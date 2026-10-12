#!/usr/bin/env python3
"""No npm installs, wrangler/Miniflare state, Worker secrets or bytecode in git.

publish.sh runs `git add -A`, so anything .gitignore misses gets committed.
Skips outside a git checkout.

  python3 -m unittest tests.test_repo_hygiene
"""
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAD_DIRS = {"node_modules", ".wrangler", "__pycache__"}


def _git(*args):
    try:
        out = subprocess.run(
            ["git", "-C", ROOT, *args], check=True, capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return [p.decode("utf-8", "replace") for p in out.stdout.split(b"\0") if p]


def _bad(path):
    parts = path.split("/")
    if BAD_DIRS.intersection(parts[:-1]):
        return True
    name = parts[-1]
    if name == ".dev.vars" or name.startswith(".dev.vars."):
        return not name.endswith(".example")
    return False


class RepoHygiene(unittest.TestCase):
    def test_no_generated_or_secret_files_tracked(self):
        paths = _git("ls-files", "-z")
        if paths is None:
            self.skipTest("not a git checkout")
        bad = sorted(p for p in paths if _bad(p))
        self.assertEqual(bad, [], "tracked paths that must not be in git")

    def test_no_tracked_file_is_ignored(self):
        # A tracked file the rules ignore is either a leak .gitignore came too
        # late for, or a rule that would hide a file meant to stay tracked.
        paths = _git("ls-files", "-z", "-ci", "--exclude-standard")
        if paths is None:
            self.skipTest("not a git checkout")
        self.assertEqual(sorted(paths), [], "tracked files matched by .gitignore")


if __name__ == "__main__":
    unittest.main()
