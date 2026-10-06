#!/usr/bin/env python3
"""gh-pages publish must keep CNAME and paths the build does not produce.

  python3 tests/test_publish_keep.py

markets/ and regulation-videos/ are not in publish-keep.txt: build.py writes both
on every build (build_markets and build_regulation_videos from build_lang).
"""
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLISH = os.path.join(ROOT, "publish.sh")
KEEP = os.path.join(ROOT, "publish-keep.txt")


def keep_names():
    names = []
    for raw in open(KEEP, encoding="utf-8"):
        line = raw.split("#", 1)[0].strip().strip("/")
        if line:
            names.append(line.split("/", 1)[0])
    return names


def stage(dest, src, keep):
    return subprocess.run(
        ["bash", "-c", 'set -euo pipefail; source "$1"; stage_gh_pages "$2" "$3" "$4"',
         "bash", PUBLISH, dest, src, keep],
        capture_output=True, text=True, timeout=30,
    )


class PublishKeep(unittest.TestCase):
    def test_keep_file_lists_cname_and_kiosk_only(self):
        names = keep_names()
        self.assertIn("CNAME", names)
        self.assertIn("kiosk", names)
        # Produced by build.py on every public build, so a publish replaces them.
        self.assertNotIn("markets", names)
        self.assertNotIn("regulation-videos", names)

    def test_build_writes_cname(self):
        tmp = tempfile.mkdtemp(prefix="nc-cname-")
        self.addCleanup(shutil.rmtree, tmp, True)
        code = textwrap.dedent(
            """\
            import os, sys
            os.environ["NC_SITE_DIR"] = sys.argv[1]
            sys.path.insert(0, sys.argv[2])
            import build
            build.write_cname()
            print(open(os.path.join(sys.argv[1], "CNAME"), encoding="utf-8").read(), end="")
            """
        )
        r = subprocess.run(
            ["python3", "-c", code, tmp, ROOT],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "cryptonordic.no\n")

    def test_stage_preserves_keep_and_replaces_built_trees(self):
        tmp = tempfile.mkdtemp(prefix="nc-stage-")
        self.addCleanup(shutil.rmtree, tmp, True)
        dest, src = os.path.join(tmp, "publish"), os.path.join(tmp, "site")
        os.makedirs(os.path.join(dest, ".git"))
        os.makedirs(os.path.join(dest, "kiosk", "web"))
        os.makedirs(os.path.join(dest, "markets"))
        os.makedirs(os.path.join(src, "markets"))
        open(os.path.join(dest, ".git", "HEAD"), "w").write("ref: refs/heads/gh-pages\n")
        open(os.path.join(dest, "CNAME"), "w").write("cryptonordic.no\n")
        open(os.path.join(dest, "kiosk", "web", "index.html"), "w").write("kiosk\n")
        open(os.path.join(dest, "doomed.txt"), "w").write("gone\n")
        open(os.path.join(dest, "markets", "index.html"), "w").write("OLD\n")
        open(os.path.join(dest, "markets", "stale.txt"), "w").write("stale\n")
        open(os.path.join(src, "index.html"), "w").write("NEW\n")
        open(os.path.join(src, "CNAME"), "w").write("cryptonordic.no\n")
        open(os.path.join(src, "markets", "index.html"), "w").write("NEW\n")
        keep = os.path.join(tmp, "keep.txt")
        open(keep, "w").write("# comment\nCNAME\nkiosk/\nextra\n")
        os.makedirs(os.path.join(dest, "extra"))
        open(os.path.join(dest, "extra", "note.txt"), "w").write("keep me\n")
        r = stage(dest, src, keep)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(open(os.path.join(dest, "CNAME"), encoding="utf-8").read(), "cryptonordic.no\n")
        self.assertEqual(open(os.path.join(dest, "kiosk", "web", "index.html"), encoding="utf-8").read(), "kiosk\n")
        self.assertEqual(open(os.path.join(dest, "extra", "note.txt"), encoding="utf-8").read(), "keep me\n")
        self.assertEqual(open(os.path.join(dest, "index.html"), encoding="utf-8").read(), "NEW\n")
        self.assertEqual(open(os.path.join(dest, "markets", "index.html"), encoding="utf-8").read(), "NEW\n")
        self.assertFalse(os.path.exists(os.path.join(dest, "markets", "stale.txt")))
        self.assertFalse(os.path.exists(os.path.join(dest, "doomed.txt")))
        self.assertTrue(os.path.exists(os.path.join(dest, ".git", "HEAD")))

    def test_stage_aborts_before_wipe_when_cname_missing(self):
        tmp = tempfile.mkdtemp(prefix="nc-nocname-")
        self.addCleanup(shutil.rmtree, tmp, True)
        dest, src = os.path.join(tmp, "publish"), os.path.join(tmp, "site")
        os.makedirs(os.path.join(dest, "kiosk"))
        os.makedirs(src)
        open(os.path.join(dest, "kiosk", "VERSION"), "w").write("1\n")
        open(os.path.join(dest, "doomed.txt"), "w").write("stay\n")
        open(os.path.join(src, "index.html"), "w").write("NEW\n")
        r = stage(dest, src, KEEP)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("lacks CNAME", r.stderr)
        self.assertTrue(os.path.exists(os.path.join(dest, "doomed.txt")))
        self.assertTrue(os.path.exists(os.path.join(dest, "kiosk", "VERSION")))
        self.assertFalse(os.path.exists(os.path.join(dest, "index.html")))

    def test_stage_aborts_when_site_cname_is_wrong(self):
        tmp = tempfile.mkdtemp(prefix="nc-badcname-")
        self.addCleanup(shutil.rmtree, tmp, True)
        dest, src = os.path.join(tmp, "publish"), os.path.join(tmp, "site")
        os.makedirs(dest)
        os.makedirs(src)
        open(os.path.join(dest, "CNAME"), "w").write("cryptonordic.no\n")
        open(os.path.join(dest, "doomed.txt"), "w").write("stay\n")
        open(os.path.join(src, "CNAME"), "w").write("example.com\n")
        r = stage(dest, src, KEEP)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("lacks CNAME", r.stderr)
        self.assertEqual(open(os.path.join(dest, "CNAME"), encoding="utf-8").read(), "cryptonordic.no\n")
        self.assertTrue(os.path.exists(os.path.join(dest, "doomed.txt")))

    def test_stage_keeps_existing_cname_when_site_has_none(self):
        tmp = tempfile.mkdtemp(prefix="nc-keepcname-")
        self.addCleanup(shutil.rmtree, tmp, True)
        dest, src = os.path.join(tmp, "publish"), os.path.join(tmp, "site")
        os.makedirs(os.path.join(dest, "kiosk"))
        os.makedirs(src)
        open(os.path.join(dest, "CNAME"), "w").write("cryptonordic.no\n")
        open(os.path.join(dest, "kiosk", "VERSION"), "w").write("1\n")
        open(os.path.join(src, "index.html"), "w").write("NEW\n")
        r = stage(dest, src, KEEP)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(open(os.path.join(dest, "CNAME"), encoding="utf-8").read(), "cryptonordic.no\n")
        self.assertEqual(open(os.path.join(dest, "index.html"), encoding="utf-8").read(), "NEW\n")
        self.assertEqual(open(os.path.join(dest, "kiosk", "VERSION"), encoding="utf-8").read(), "1\n")

    def test_publish_script_sets_pages_domain_and_checks_it(self):
        text = open(PUBLISH, encoding="utf-8").read()
        self.assertIn(
            'gh api -X PUT repos/jQrgen/nordic-crypto/pages -f "cname=$(site_host)" '
            "-f 'source[branch]=gh-pages' -f 'source[path]=/'",
            text,
        )
        self.assertIn(
            'gh api -X POST repos/jQrgen/nordic-crypto/pages -f "source[branch]=gh-pages" -f "source[path]=/"',
            text,
        )
        self.assertIn("URL=$(site_base)", text)
        self.assertIn('CUSTOM="$URL"', text)
        self.assertIn('wait_url "$CUSTOM" 120', text)
        host = subprocess.run(
            ["python3", "-c", "import site_url; print(site_url.HOST)"],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(host.stdout.strip(), "cryptonordic.no", host.stderr)

    def test_wait_url_warns_quickly_and_accepts_200(self):
        r = subprocess.run(
            ["bash", "-c",
             'set -euo pipefail; source "$1"; wait_url "http://127.0.0.1:1/" 0',
             "bash", PUBLISH],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("warning:", r.stdout)
        self.assertIn("did not return HTTP 200", r.stdout)
        port_py = textwrap.dedent(
            """\
            import socket, subprocess, sys, time
            s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
            root = sys.argv[1]
            proc = subprocess.Popen(
                [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            try:
                for _ in range(50):
                    try:
                        c = socket.create_connection(("127.0.0.1", port), 0.2)
                        c.close()
                        break
                    except OSError:
                        time.sleep(0.05)
                else:
                    raise SystemExit("server did not start")
                out = subprocess.run(
                    ["bash", "-c", 'set -euo pipefail; source "$1"; wait_url "$2" 20',
                     "bash", sys.argv[2], "http://127.0.0.1:%d/" % port],
                    capture_output=True, text=True, timeout=30,
                )
                sys.stdout.write(out.stdout)
                sys.stderr.write(out.stderr)
                raise SystemExit(out.returncode)
            finally:
                proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill()
            """
        )
        srv = tempfile.mkdtemp(prefix="nc-http-")
        self.addCleanup(shutil.rmtree, srv, True)
        open(os.path.join(srv, "index.html"), "w").write("ok\n")
        r2 = subprocess.run(
            ["python3", "-c", port_py, srv, PUBLISH],
            capture_output=True, text=True, timeout=40,
        )
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertIn("HTTP 200", r2.stdout)
        self.assertNotIn("warning:", r2.stdout)


if __name__ == "__main__":
    unittest.main()
