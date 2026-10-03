#!/usr/bin/env bash
# Builds site/, runs the privacy gate and publishes ONLY site/ to gh-pages in jQrgen/nordic-crypto.
# Code (not data/, state/, queue/, logs/) goes to main.
# Usage:  ./publish.sh        -> public build + privacy gate only (nothing is pushed)
#         ./publish.sh --yes  -> build, check and publish (ONLY after jQrgen has approved)
set -euo pipefail
cd "$(dirname "$0")"
exec 9>/tmp/nordic-crypto-publish.lock; flock -w 300 9   # shared with tipserver/publish_endpoint.sh
DRY=${1:-}
REPO=https://github.com/jQrgen/nordic-crypto.git
URL=https://jqrgen.github.io/nordic-crypto/
# on the first approved publish, stamp the launch date into changelog.json (entries dated "launch")
[ "$DRY" = "--yes" ] && .venv/bin/python -c "import json,datetime;p='changelog.json';d=json.load(open(p));d['launch_date']=d.get('launch_date') or datetime.date.today().isoformat();json.dump(d,open(p,'w'),ensure_ascii=False,indent=1)"
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
# 1) gh-pages: separate clone in .publish/ that only contains site/
if [ ! -d .publish/.git ]; then
  rm -rf .publish
  if git ls-remote --exit-code --heads "$REPO" gh-pages >/dev/null 2>&1; then git clone -q --branch gh-pages --single-branch "$REPO" .publish
  else mkdir .publish && git -C .publish init -q -b gh-pages && git -C .publish remote add origin "$REPO"; fi
fi
git -C .publish config user.name "$(git config user.name)"; git -C .publish config user.email "$(git config user.email)"
git -C .publish pull -q --ff-only origin gh-pages 2>/dev/null || true
find .publish -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} + && cp -a site/. .publish/
git -C .publish add -A
if git -C .publish diff --cached --quiet; then echo "gh-pages: no changes"; else
  git -C .publish commit -q -m "Publish $(date '+%Y-%m-%d %H:%M %Z')" && git -C .publish push -q origin gh-pages && echo "gh-pages: pushed"; fi
gh api -X POST repos/jQrgen/nordic-crypto/pages -f "source[branch]=gh-pages" -f "source[path]=/" >/dev/null 2>&1 || true
# 2) main: code and config only (see .gitignore)
git add -A && { git diff --cached --quiet || git commit -q -m "Update pipeline $(date '+%Y-%m-%d')"; } && git push -q -u origin main || echo "warning: push to main failed"
# 3) check that the site answers
for i in $(seq 1 30); do code=$(curl -s -o /dev/null -w '%{http_code}' "$URL" || true); [ "$code" = 200 ] && break; sleep 10; done
echo "live: $URL -> HTTP $code"
