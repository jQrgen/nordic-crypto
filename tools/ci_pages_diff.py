#!/usr/bin/env python3
"""Summarise how a built site/ differs from a gh-pages checkout.

Prints file counts and top-level path names. Does not print file contents.
"""
import hashlib
import os
import sys


def _digest(path, label):
    """Return (file count, content hash) for a file or directory. Skips .git."""
    h = hashlib.sha256()
    count = 0
    if os.path.isfile(path) or os.path.islink(path):
        h.update(label.encode())
        h.update(b"\0")
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return 1, h.hexdigest()
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for filename in sorted(filenames):
            full = os.path.join(dirpath, filename)
            if not os.path.isfile(full) and not os.path.islink(full):
                continue
            count += 1
            rel = os.path.relpath(full, os.path.dirname(path))
            h.update(rel.encode())
            h.update(b"\0")
            with open(full, "rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(chunk)
    return count, h.hexdigest()


def _tops(root):
    if not os.path.isdir(root):
        raise SystemExit(f"not a directory: {root}")
    total = 0
    tops = {}
    for name in sorted(os.listdir(root)):
        if name == ".git":
            continue
        count, digest = _digest(os.path.join(root, name), name)
        tops[name] = (count, digest)
        total += count
    return total, tops


def _fmt(names):
    return ", ".join(f"`{name}`" for name in names) if names else "(none)"


def compare(site, pages):
    """Markdown summary of top-level differences. Hashes stay internal."""
    site_n, site_tops = _tops(site)
    pages_n, pages_tops = _tops(pages)
    only_site = sorted(set(site_tops) - set(pages_tops))
    only_pages = sorted(set(pages_tops) - set(site_tops))
    changed = sorted(
        name for name in set(site_tops) & set(pages_tops)
        if site_tops[name] != pages_tops[name]
    )
    lines = [
        "### CI build vs current gh-pages",
        "",
        f"- CI `site/`: {site_n} files",
        f"- current `gh-pages`: {pages_n} files",
        "",
        f"Top-level paths only in the CI build: {_fmt(only_site)}",
        "",
        f"Top-level paths only on gh-pages: {_fmt(only_pages)}",
        "",
        f"Top-level paths whose files differ: {_fmt(changed)}",
        "",
        "A publish keeps `CNAME`, `kiosk/`, and every top-level name in `publish-keep.txt`.",
        "Any other top-level path that is only on gh-pages is removed.",
        "",
    ]
    return "\n".join(lines)


def main(argv):
    if len(argv) != 3:
        print("usage: tools/ci_pages_diff.py <site-dir> <gh-pages-dir>", file=sys.stderr)
        return 2
    sys.stdout.write(compare(argv[1], argv[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
