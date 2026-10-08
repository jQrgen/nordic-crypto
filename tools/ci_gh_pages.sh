#!/usr/bin/env bash
# Publish a built site/ onto a gh-pages checkout.
# Keeps CNAME, kiosk/ and the names in publish-keep.txt (stage_gh_pages in publish.sh).
# A rejected push is fetched and staged again. This script does not force-push.
# Usage: tools/ci_gh_pages.sh <gh-pages-checkout> <site-dir> <keepfile> <commit-message>
set -euo pipefail

if [ "$#" -ne 4 ]; then
  echo "usage: tools/ci_gh_pages.sh <gh-pages-checkout> <site-dir> <keepfile> <commit-message>" >&2
  exit 2
fi

dest=$1
src=$2
keep=$3
msg=$4
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=../publish.sh
source "$root/publish.sh"

if [ -e "$src/.preview" ]; then
  echo "refusing: $src is a preview build" >&2
  exit 1
fi

export GIT_TERMINAL_PROMPT=0
git -C "$dest" config user.name "github-actions[bot]"
git -C "$dest" config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git -C "$dest" config commit.gpgsign false

attempt=1
max=3
while [ "$attempt" -le "$max" ]; do
  git -C "$dest" fetch --depth 1 origin gh-pages
  git -C "$dest" reset --hard FETCH_HEAD
  stage_gh_pages "$dest" "$src" "$keep"
  git -C "$dest" add -A
  if git -C "$dest" diff --cached --quiet; then
    echo "gh-pages: no changes"
    exit 0
  fi
  git -C "$dest" commit -m "$msg"
  if git -C "$dest" push origin HEAD:gh-pages; then
    echo "gh-pages: pushed"
    exit 0
  fi
  echo "gh-pages push rejected (attempt ${attempt}/${max}); a non-fast-forward is fetched and staged again" >&2
  attempt=$((attempt + 1))
done

echo "::error::gh-pages push failed after ${max} attempts. Not force-pushing." >&2
exit 1
