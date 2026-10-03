#!/usr/bin/env bash
# Pushes ONLY tip-endpoint.json to gh-pages (via the .publish/ clone) when the public tip endpoint has changed.
# Nothing else on the site is rebuilt or republished. Shares a lock with publish.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
exec 9>/tmp/nordic-crypto-publish.lock; flock -w 300 9
ep=$(python3 tipserver/endpoint.py); kind=$(python3 -c 'import sys;sys.path.insert(0,"tipserver");import endpoint;print(endpoint.current()[1] or "")')
[ -n "$ep" ] || { echo "no tip endpoint known yet"; exit 1; }
[ -d .publish/.git ] || { echo ".publish/ missing – run ./publish.sh --yes once"; exit 1; }
git -C .publish pull -q --ff-only origin gh-pages
cur=$(python3 -c 'import json;print(json.load(open(".publish/tip-endpoint.json")).get("endpoint",""))' 2>/dev/null || true)
write() { python3 -c 'import json,sys,datetime;json.dump({"endpoint":sys.argv[1],"kind":sys.argv[2],"updated":datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")},open(sys.argv[3],"w"),indent=1);open(sys.argv[3],"a").write("\n")' "$ep" "$kind" "$1"; }
[ -d site ] && write site/tip-endpoint.json
[ "$cur" = "$ep" ] && { echo "tip-endpoint.json unchanged ($ep)"; exit 0; }
write .publish/tip-endpoint.json
git -C .publish add tip-endpoint.json
git -C .publish commit -q -m "Update tip endpoint" -- tip-endpoint.json
git -C .publish push -q origin gh-pages || { git -C .publish pull -q --rebase origin gh-pages && git -C .publish push -q origin gh-pages; }
echo "tip-endpoint.json pushed: $ep"
