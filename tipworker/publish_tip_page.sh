#!/usr/bin/env bash
# Publishes ONLY the /tip/ page (tip/index.html + tip-endpoint.json) to gh-pages – nothing else from the pipeline
# (no pending or newly approved stories). Builds a public build into a scratch dir, runs the privacy gate on it,
# copies just those two files into the .publish/ gh-pages clone, commits, pushes and checks the live page.
# Usage: tipworker/publish_tip_page.sh        -> dry run: build + gate + show the diff against gh-pages (pushes nothing)
#        tipworker/publish_tip_page.sh --yes  -> publish (ONLY with jQrgen's approval)
set -euo pipefail
cd "$(dirname "$0")/.."
exec 9>/tmp/nordic-crypto-publish.lock; flock -w 300 9   # shared with publish.sh / tipserver/publish_endpoint.sh
ep=$(python3 tipserver/endpoint.py); [ -n "$ep" ] || { echo "no public_endpoint in tipserver/config.json – run tipworker/deploy.sh first"; exit 1; }
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
NC_SITE_DIR="$tmp/site" .venv/bin/python build.py >/dev/null
[ -e "$tmp/site/.preview" ] && { echo "refusing: preview build"; exit 1; }
.venv/bin/python tools/privacy_gate.py "$tmp/site/tip" || exit 1
grep -q "FIXED=\"$ep\"" "$tmp/site/tip/index.html" || { echo "built tip page does not use $ep"; exit 1; }
grep -q 'issues/new?template=tip.yml' "$tmp/site/tip/index.html" || { echo "GitHub fallback link missing"; exit 1; }
[ -d .publish/.git ] || { echo ".publish/ missing – run ./publish.sh --yes once"; exit 1; }
[ "${1:-}" = "--yes" ] && git -C .publish pull -q --ff-only origin gh-pages
diff -u .publish/tip/index.html "$tmp/site/tip/index.html" | head -60 || true
[ "${1:-}" = "--yes" ] || { echo "dry run: nothing pushed (run with --yes, only with jQrgen's approval)"; exit 0; }
cp "$tmp/site/tip/index.html" .publish/tip/index.html; cp "$tmp/site/tip-endpoint.json" .publish/tip-endpoint.json
git -C .publish add tip/index.html tip-endpoint.json
git -C .publish diff --cached --quiet && { echo "gh-pages: tip page unchanged"; exit 0; }
git -C .publish diff --cached --name-only
git -C .publish commit -q -m "Tip page: post tips to the Cloudflare Worker ($ep)" -- tip/index.html tip-endpoint.json
git -C .publish push -q origin gh-pages
for i in $(seq 1 40); do curl -fsS "https://jqrgen.github.io/nordic-crypto/tip/?t=$(date +%s)" | grep -q "FIXED=\"$ep\"" && { echo "live: /tip/ uses $ep"; exit 0; }; sleep 10; done
echo "pushed, but the live page does not show the new endpoint yet"; exit 1
