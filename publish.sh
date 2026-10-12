#!/usr/bin/env bash
# Builds site/, runs the privacy gate and publishes site/ to gh-pages in jQrgen/nordic-crypto.
# Paths the build does not produce (CNAME, kiosk/, publish-keep.txt) stay on gh-pages.
# Code (not data/, state/, queue/, logs/) goes to main.
# Usage:  ./publish.sh        -> public build + privacy gate only (nothing is pushed)
#         ./publish.sh --yes  -> build, check and publish (ONLY after jQrgen has approved)
# Sourced by tests/test_publish_keep.py. Running the file publishes; sourcing it only defines helpers.

_publish_root() {
  local src="${BASH_SOURCE[0]}"
  (cd "$(dirname "$src")" && pwd)
}

site_base() {
  # Public origin, including the trailing slash. Defined in site_url.json.
  python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import site_url; print(site_url.BASE)' "$(_publish_root)"
}

site_host() {
  python3 -c 'import sys; sys.path.insert(0, sys.argv[1]); import site_url; print(site_url.HOST)' "$(_publish_root)"
}

gh_pages_cname_ok() {
  # $1 is a tree root. True when CNAME is exactly the live custom domain.
  local f="$1/CNAME" got
  [ -f "$f" ] || return 1
  got=$(tr -d '[:space:]' < "$f" || true)
  [ "$got" = "$(site_host)" ]
}

stage_gh_pages() {
  # Replace $dest with $src, but keep top-level names from $keepfile (plus CNAME and kiosk).
  # Aborts before the wipe when the staged tree would not contain CNAME, and again after the copy.
  local dest="$1" src="$2" keepfile="$3"
  local line n x found
  local -a names=()
  [ -d "$dest" ] || { echo "refusing: $dest is not a directory" >&2; return 1; }
  [ -d "$src" ] || { echo "refusing: $src is not a directory" >&2; return 1; }
  [ -f "$keepfile" ] || { echo "refusing: $keepfile is missing" >&2; return 1; }
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%%#*}"
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    line="${line%/}"
    [ -n "$line" ] || continue
    line="${line%%/*}"
    [ -n "$line" ] || continue
    names+=("$line")
  done < "$keepfile"
  for n in CNAME kiosk; do
    found=0
    if [ "${#names[@]}" -gt 0 ]; then
      for x in "${names[@]}"; do
        [ "$x" = "$n" ] && found=1
      done
    fi
    [ "$found" = 1 ] || names+=("$n")
  done
  if [ -e "$src/CNAME" ] && ! gh_pages_cname_ok "$src"; then
    echo "refusing: staged gh-pages tree lacks CNAME ($(site_host)); not publishing" >&2
    return 1
  fi
  if ! gh_pages_cname_ok "$src" && ! gh_pages_cname_ok "$dest"; then
    echo "refusing: staged gh-pages tree lacks CNAME ($(site_host)); not publishing" >&2
    return 1
  fi
  # Exclude list: do not delete .git or any kept top-level name. Everything else is the build output.
  local -a pred=()
  pred+=(! -name .git)
  for n in "${names[@]}"; do
    pred+=(! -name "$n")
  done
  find "$dest" -mindepth 1 -maxdepth 1 "${pred[@]}" -exec rm -rf {} +
  cp -a "$src"/. "$dest"/
  if ! gh_pages_cname_ok "$dest"; then
    echo "refusing: staged gh-pages tree lacks CNAME ($(site_host)); not publishing" >&2
    return 1
  fi
}

wait_url() {
  # $1 URL, $2 budget seconds. Prints the live line on HTTP 200, otherwise a warning. Does not abort.
  local url="$1" budget="$2" code="" end
  end=$((SECONDS + budget))
  while :; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$url" || true)
    if [ "$code" = 200 ]; then echo "live: $url -> HTTP $code"; return 0; fi
    [ "$SECONDS" -ge "$end" ] && break
    sleep 10
  done
  echo "warning: $url did not return HTTP 200 within ${budget} seconds (last status HTTP ${code:-none}). The custom domain looks offline; check CNAME and the GitHub Pages custom domain setting."
}

if [ "${BASH_SOURCE[0]}" != "$0" ]; then
  return 0
fi

set -euo pipefail
cd "$(dirname "$0")"
exec 9>/tmp/nordic-crypto-publish.lock; flock -w 300 9   # shared with tipserver/publish_endpoint.sh
DRY=${1:-}
require_current_main() {
  # Publish only main at or ahead of origin/main. A stale tree would delete newer pages from gh-pages.
  local branch
  git fetch -q origin main || { echo "refusing: could not fetch origin/main" >&2; exit 1; }
  branch=$(git symbolic-ref --short -q HEAD || true)
  if [ "$branch" != main ] || ! git merge-base --is-ancestor origin/main HEAD; then
    echo "refusing: publish only from main at or ahead of origin/main (on ${branch:-detached HEAD} at $(git rev-parse --short HEAD); origin/main is $(git rev-parse --short origin/main)). Pull/rebase onto origin/main first: git pull --ff-only origin main" >&2
    exit 1
  fi
}
if [ "$DRY" = "--yes" ]; then
  require_current_main
  # source of this publish, taken before the changelog stamp and the build rewrite tracked files
  SRC="main@$(git rev-parse --short HEAD)"
  [ -z "$(git status --porcelain)" ] || SRC="$SRC+dirty"
fi
REPO=https://github.com/jQrgen/nordic-crypto.git
URL=$(site_base)
CUSTOM="$URL"
# on the first approved publish, stamp the launch date into changelog.json (entries dated "launch")
[ "$DRY" = "--yes" ] && .venv/bin/python -c "import json,datetime;p='changelog.json';d=json.load(open(p));d['launch_date']=d.get('launch_date') or datetime.date.today().isoformat();json.dump(d,open(p,'w'),ensure_ascii=False,indent=1)"
# build.py also fetches Nordic exchange prices into site/api/v1/markets.json (tools/markets.py)
# and always writes site/CNAME (nordiccrypto.no)
.venv/bin/python build.py            # never --preview here
[ -e site/.preview ] && { echo "refusing: site/ is a preview build"; exit 1; }
.venv/bin/python tools/privacy_gate.py site
.venv/bin/python tools/text_gate.py
[ "$DRY" = "--yes" ] || { echo "Built and checked locally. Not published (run ./publish.sh --yes to publish, only with jQrgen's approval)."; exit 0; }
# first run: create the local repo and the GitHub repo (public, for GitHub Pages)
[ -d .git ] || git init -q -b main
# commit identity: GitHub login + noreply address of the authenticated gh account (never a private email)
if [ -z "$(git config user.name || true)" ]; then
  login=$(gh api user -q .login); uid=$(gh api user -q .id)
  git config user.name "$login"; git config user.email "${uid}+${login}@users.noreply.github.com"
fi
git remote get-url origin >/dev/null 2>&1 || { gh repo view jQrgen/nordic-crypto >/dev/null 2>&1 || gh repo create jQrgen/nordic-crypto --public -d "Bitcoin, blockchain and crypto news from the Nordics"; git remote add origin "$REPO"; }
# 1) gh-pages: separate clone in .publish/. Built files are replaced; publish-keep.txt paths are not.
if [ ! -d .publish/.git ]; then
  rm -rf .publish
  if git ls-remote --exit-code --heads "$REPO" gh-pages >/dev/null 2>&1; then git clone -q --branch gh-pages --single-branch "$REPO" .publish
  else mkdir .publish && git -C .publish init -q -b gh-pages && git -C .publish remote add origin "$REPO"; fi
fi
git -C .publish config user.name "$(git config user.name)"; git -C .publish config user.email "$(git config user.email)"
git -C .publish pull -q --ff-only origin gh-pages 2>/dev/null || true
# previous public news list, so the push step can name only stories that were not already on gh-pages
OLD_NEWS=$(mktemp)
trap 'rm -f "$OLD_NEWS"' EXIT
if [ -f .publish/data/news.json ]; then cp .publish/data/news.json "$OLD_NEWS"; else printf '%s\n' '{"items":[]}' > "$OLD_NEWS"; fi
# main may have moved during the build; do not overwrite a newer CI publish
require_current_main
stage_gh_pages .publish site publish-keep.txt
git -C .publish add -A
GH_PUSHED=0
if git -C .publish diff --cached --quiet; then echo "gh-pages: no changes"; else
  git -C .publish commit -q -m "Publish $(date '+%Y-%m-%d %H:%M %Z') from $SRC" && git -C .publish push -q origin gh-pages && echo "gh-pages: pushed" && GH_PUSHED=1; fi
# Keep the custom domain set. Deleting CNAME from the branch clears this; the PUT puts it back.
# POST remains the fallback for a repo that does not have Pages yet.
gh api -X PUT repos/jQrgen/nordic-crypto/pages -f "cname=$(site_host)" -f 'source[branch]=gh-pages' -f 'source[path]=/' >/dev/null 2>&1 \
  || gh api -X POST repos/jQrgen/nordic-crypto/pages -f "source[branch]=gh-pages" -f "source[path]=/" >/dev/null 2>&1 \
  || true
# 2) main: code and config only (see .gitignore)
git add -A && { git diff --cached --quiet || git commit -q -m "Update pipeline $(date '+%Y-%m-%d')"; } && git push -q -u origin main || echo "warning: push to main failed"
# 3) check that the site answers
for i in $(seq 1 30); do code=$(curl -s -o /dev/null -w '%{http_code}' "$URL" || true); [ "$code" = 200 ] && break; sleep 10; done
echo "live: $URL -> HTTP $code"
wait_url "$CUSTOM" 120
# one batched browser notification for stories that were not in the previous gh-pages news.json
# read-only on our data; skips (exit 0) when the Worker or PUSH_PUBLISH_TOKEN is not set
if [ "${GH_PUSHED:-0}" = 1 ]; then
  .venv/bin/python tools/push_notify.py --previous "$OLD_NEWS" --current site/data/news.json || echo "warning: browser push notify failed"
fi
