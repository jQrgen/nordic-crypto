#!/usr/bin/env bash
# Keeps tip-endpoint.json in step with the current public tip endpoint (tipserver/endpoint.py; empty = none/down).
#  - Always: writes site/tip-endpoint.json (local build dir; never pushed by this step).
#  - Only if tipserver/config.json has "auto_publish_endpoint": true (set ONLY after jQrgen approves the tip page):
#    pushes ONLY tip-endpoint.json to gh-pages (via the .publish/ clone) when the endpoint changed. Nothing else is published.
# Shares a lock with publish.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
exec 9>/tmp/nordic-crypto-publish.lock; flock -w 300 9
ep=$(python3 tipserver/endpoint.py); kind=$(python3 -c 'import sys;sys.path.insert(0,"tipserver");import endpoint;print(endpoint.current()[1] or "")')
auto=$(python3 -c 'import json;print("1" if json.load(open("tipserver/config.json")).get("auto_publish_endpoint") else "")')
write() { python3 -c 'import json,sys,datetime;json.dump({"endpoint":sys.argv[1] or None,"kind":sys.argv[2] or None,"updated":datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")},open(sys.argv[3],"w"),indent=1);open(sys.argv[3],"a").write("\n")' "$ep" "$kind" "$1"; }
[ -d site ] && write site/tip-endpoint.json
[ -d site-tip-preview ] && write site-tip-preview/tip-endpoint.json
[ -n "$auto" ] || { echo "site/tip-endpoint.json updated locally (${ep:-no endpoint}); auto_publish_endpoint is off – nothing pushed"; exit 0; }
[ -n "$ep" ] || { echo "no tip endpoint right now – gh-pages left as is (the page falls back to GitHub when unreachable)"; exit 0; }
[ -d .publish/.git ] || { echo ".publish/ missing – run ./publish.sh --yes once"; exit 1; }
git -C .publish pull -q --ff-only origin gh-pages
cur=$(python3 -c 'import json;print(json.load(open(".publish/tip-endpoint.json")).get("endpoint") or "")' 2>/dev/null || true)
[ "$cur" = "$ep" ] && { echo "tip-endpoint.json unchanged ($ep)"; exit 0; }
write .publish/tip-endpoint.json
git -C .publish add tip-endpoint.json
git -C .publish commit -q -m "Update tip endpoint" -- tip-endpoint.json
git -C .publish push -q origin gh-pages || { git -C .publish pull -q --rebase origin gh-pages && git -C .publish push -q origin gh-pages; }
echo "tip-endpoint.json pushed: $ep"
