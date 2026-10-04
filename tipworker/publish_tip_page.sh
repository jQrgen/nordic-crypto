#!/usr/bin/env bash
# Publishes ONLY the /tip/ pages (tip/index.html in every language + tip-endpoint.json) to gh-pages – nothing else from the
# pipeline (no pending or newly approved stories). Builds a public build into a scratch dir, runs the privacy gate on it,
# copies just those files into the .publish/ gh-pages clone, commits, pushes and checks the live page.
# Endpoint modes:  fixed  – tipserver/config.json public_endpoint (e.g. Cloudflare Worker / named tunnel), baked into the page
#                  quick  – box tip server behind a Cloudflare quick tunnel; the page reads /tip-endpoint.json at runtime.
#                           Needs tip_page_uses_server: true in tipserver/config.json (or env TIP_PAGE_SERVER=1).
# Usage: tipworker/publish_tip_page.sh        -> dry run: build + gate + show the diff against gh-pages (pushes nothing)
#        tipworker/publish_tip_page.sh --yes  -> publish (ONLY with jQrgen's approval)
set -euo pipefail
cd "$(dirname "$0")/.."
exec 9>/tmp/nordic-crypto-publish.lock; flock -w 300 9   # shared with publish.sh / tipserver/publish_endpoint.sh
ep=$(python3 -c 'import json;print((json.load(open("tipserver/config.json")).get("public_endpoint") or "").strip().rstrip("/"))')
srv=$(python3 -c 'import json,os;print("1" if os.environ.get("TIP_PAGE_SERVER")=="1" or json.load(open("tipserver/config.json")).get("tip_page_uses_server") else "")')
[ -n "$ep" ] || [ -n "$srv" ] || { echo "neither public_endpoint nor tip_page_uses_server set in tipserver/config.json"; exit 1; }
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
NC_SITE_DIR="$tmp/site" .venv/bin/python build.py >/dev/null
[ -e "$tmp/site/.preview" ] && { echo "refusing: preview build"; exit 1; }
.venv/bin/python tools/privacy_gate.py "$tmp/site/tip" || exit 1
want="FIXED=\"$ep\""; [ -n "$ep" ] || want="FIXED=null"
grep -q "$want" "$tmp/site/tip/index.html" || { echo "built tip page does not use ${ep:-the runtime tip-endpoint.json}"; exit 1; }
grep -q 'issues/new?template=tip.yml' "$tmp/site/tip/index.html" || { echo "GitHub fallback link missing"; exit 1; }
[ -d .publish/.git ] || { echo ".publish/ missing – run ./publish.sh --yes once"; exit 1; }
[ "${1:-}" = "--yes" ] && git -C .publish pull -q --ff-only origin gh-pages
pages=$(cd "$tmp/site" && ls -d tip */tip 2>/dev/null | sed 's#$#/index.html#')
for p in $pages; do diff -u ".publish/$p" "$tmp/site/$p" | head -40 || true; done
cat "$tmp/site/tip-endpoint.json"
[ "${1:-}" = "--yes" ] || { echo "dry run: nothing pushed (run with --yes, only with jQrgen's approval)"; exit 0; }
for p in $pages; do mkdir -p ".publish/$(dirname "$p")"; cp "$tmp/site/$p" ".publish/$p"; done; cp "$tmp/site/tip-endpoint.json" .publish/tip-endpoint.json
git -C .publish add $pages tip-endpoint.json
git -C .publish diff --cached --quiet && { echo "gh-pages: tip page unchanged"; exit 0; }
git -C .publish diff --cached --name-only
git -C .publish commit -q -m "Tip page: post tips to our own tip server (${ep:-quick tunnel, runtime tip-endpoint.json})" -- $pages tip-endpoint.json
git -C .publish push -q origin gh-pages
for i in $(seq 1 40); do curl -fsS "https://jqrgen.github.io/nordic-crypto/tip/?t=$(date +%s)" | grep -q "$want" && { echo "live: /tip/ uses ${ep:-runtime tip-endpoint.json}"; exit 0; }; sleep 10; done
echo "pushed, but the live page does not show the new version yet"; exit 1
