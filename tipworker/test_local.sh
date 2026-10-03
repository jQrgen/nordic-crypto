#!/usr/bin/env bash
# Local tests against `wrangler dev --local` (Miniflare, local D1 in .wrangler/state – nothing touches Cloudflare).
# Usage: ./test_local.sh   (port: TW_PORT, default 8788)
set -uo pipefail
cd "$(dirname "$0")"; source ./env.sh
PORT=${TW_PORT:-8788}; B="http://127.0.0.1:$PORT"; GOOD=https://jqrgen.github.io; BAD=https://evil.example
pass=0; failc=0
ok() { echo "PASS  $1"; pass=$((pass+1)); }; ko() { echo "FAIL  $1  ($2)"; failc=$((failc+1)); }
chk() { [[ $2 == "$3" ]] && ok "$1" || ko "$1" "got $2, want $3"; }   # name got want
has() { grep -qi -- "$3" <<<"$2" && ok "$1" || ko "$1" "missing $3"; }
hasnt() { grep -qi -- "$3" <<<"$2" && ko "$1" "unexpected $3" || ok "$1"; }
sql() { npx --no-install wrangler d1 execute nordic-crypto-tips --local --json --command "$1" 2>/dev/null; }
rm -rf .wrangler/state
npx --no-install wrangler d1 migrations apply nordic-crypto-tips --local >/dev/null 2>&1 || { echo "migration failed"; exit 1; }
curl -s -o /dev/null "$B/" 2>/dev/null && { echo "port $PORT is already in use – stop the old wrangler dev first"; exit 1; }
setsid npx --no-install wrangler dev --local --ip 127.0.0.1 --port "$PORT" >/tmp/tipworker-dev.log 2>&1 & DEV=$!
trap 'kill -- -$DEV 2>/dev/null; wait $DEV 2>/dev/null' EXIT   # whole process group (npx, wrangler, workerd)
for i in $(seq 1 60); do curl -fsS "$B/api/health" >/dev/null 2>&1 && break; sleep 0.5; done
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
hdr() { curl -s -D - -o /dev/null "$@"; }
J=(-H 'Content-Type: application/json' -H 'Accept: application/json')
# health
chk "health 200" "$(code "$B/api/health")" 200
has "health body ok" "$(curl -s "$B/api/health")" '"ok":true'
chk "unknown path 404" "$(code "$B/nope")" 404
# CORS
h=$(hdr -X OPTIONS "$B/api/tip" -H "Origin: $GOOD" -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type')
has "preflight good origin 204" "$h" "HTTP/1.1 204"; has "preflight ACAO = github.io" "$h" "access-control-allow-origin: $GOOD"
has "preflight allows POST" "$h" "access-control-allow-methods: POST"; has "preflight allows content-type" "$h" "access-control-allow-headers: Content-Type"
h=$(hdr -X OPTIONS "$B/api/tip" -H "Origin: $BAD" -H 'Access-Control-Request-Method: POST')
has "preflight bad origin 403" "$h" "HTTP/1.1 403"; hasnt "preflight bad origin no ACAO" "$h" "access-control-allow-origin"
h=$(hdr -X OPTIONS "$B/api/tip" -H "Origin: https://jqrgen.github.io.evil.example" -H 'Access-Control-Request-Method: POST')
has "preflight look-alike origin 403" "$h" "HTTP/1.1 403"
h=$(hdr -X OPTIONS "$B/api/tip" -H "Origin: null" -H 'Access-Control-Request-Method: POST'); has "preflight Origin null 403" "$h" "HTTP/1.1 403"
h=$(hdr "$B/api/health" -H "Origin: $GOOD"); has "health ACAO for github.io" "$h" "access-control-allow-origin: $GOOD"; has "Vary: Origin" "$h" "vary: Origin"
h=$(hdr "$B/api/health" -H "Origin: $BAD"); hasnt "health no ACAO for other origin" "$h" "access-control-allow-origin"
r=$(curl -s -w '|%{http_code}' "${J[@]}" -H "Origin: $BAD" -d '{"url":"https://e24.no/x-cors-bad","country":"NO"}' "$B/api/tip")
chk "POST bad origin 403" "${r##*|}" 403
h=$(hdr "${J[@]}" -H "Origin: $GOOD" -d '{"url":"https://e24.no/a1","country":"NO","note":"hello","name":"Kari"}' "$B/api/tip")
has "POST good origin 201" "$h" "HTTP/1.1 201"; has "POST ACAO = github.io" "$h" "access-control-allow-origin: $GOOD"
has "no-store" "$h" "cache-control: no-store"; has "nosniff" "$h" "x-content-type-options: nosniff"
# validation (no Origin = curl/server-side, allowed like the box server)
# each request from its own test IP (CF-Connecting-IP), so the 5-per-10-min limit doesn't interfere
CNT=$(mktemp); echo 0 >"$CNT"; ipn() { local n=$(( $(cat "$CNT") + 1 )); echo $n >"$CNT"; echo "198.51.100.$n"; }   # runs in $(...) subshells, so count in a file
v() { curl -s -w '|%{http_code}' "${J[@]}" -H "CF-Connecting-IP: $(ipn)" -H "Origin: $GOOD" -d "$1" "$B/api/tip"; }
r=$(v '{"country":"NO"}'); chk "missing url 400" "${r##*|}" 400; has "missing url msg" "$r" "Please enter the article URL"
r=$(v '{"url":"ftp://x.no/a"}'); chk "ftp url 400" "${r##*|}" 400; has "bad url msg" "$r" "full http"
r=$(v '{"url":"https://localhost/a"}'); chk "dotless host 400" "${r##*|}" 400
r=$(v '{"url":"https://e24.no/a b"}'); chk "space in url 400" "${r##*|}" 400
r=$(v '{"url":"https://e24.no/a","country":"DE"}'); chk "country DE 400" "${r##*|}" 400; has "country msg" "$r" "Country must be"
r=$(v '{"url":123,"country":"NO"}'); chk "non-string field 400" "${r##*|}" 400; has "type msg" "$r" "Invalid field type"
r=$(v "{\"url\":\"https://e24.no/a\",\"note\":\"$(printf 'x%.0s' $(seq 1001))\"}"); chk "note 1001 chars 400" "${r##*|}" 400
r=$(v "{\"url\":\"https://e24.no/a\",\"name\":\"$(printf 'n%.0s' $(seq 101))\"}"); chk "name 101 chars 400" "${r##*|}" 400
r=$(v '[1,2]'); chk "JSON array 400" "${r##*|}" 400
r=$(v '{bad json'); chk "broken JSON 400" "${r##*|}" 400
r=$(curl -s -w '|%{http_code}' -H 'Content-Type: text/plain' -H "CF-Connecting-IP: $(ipn)" -H "Origin: $GOOD" -d 'x' "$B/api/tip"); chk "text/plain 415" "${r##*|}" 415
big=$(printf 'y%.0s' $(seq 5000)); r=$(v "{\"url\":\"https://e24.no/a\",\"note\":\"$big\"}"); chk "body > 4 KB 413" "${r##*|}" 413
# honeypot: 200 ok, nothing stored
r=$(v '{"url":"https://e24.no/honeypot","country":"NO","website":"http://spam"}'); chk "honeypot 200" "${r##*|}" 200
# form post (no JS) -> 303 to /tip/?sent=1; country 'Sweden (SE)' normalised
h=$(hdr -H "CF-Connecting-IP: $(ipn)" -H "Origin: $GOOD" --data-urlencode 'url=https://di.se/b2' --data-urlencode 'country=Sweden (SE)' "$B/api/tip")
has "form 303" "$h" "HTTP/1.1 303"; has "form redirect sent=1" "$h" "location: https://jqrgen.github.io/nordic-crypto/tip/?sent=1"
h=$(hdr -H "CF-Connecting-IP: $(ipn)" -H "Origin: $GOOD" --data-urlencode 'url=nope' "$B/api/tip"); has "form error redirect" "$h" "location: https://jqrgen.github.io/nordic-crypto/tip/?error="
# stored rows: a1 (NO) and b2 (SE), no honeypot row; no IP column anywhere
rows=$(sql "SELECT url, country, note, name, status FROM tips ORDER BY id")
has "stored a1" "$rows" "https://e24.no/a1"; has "stored b2 as SE" "$rows" '"country": "SE"'; hasnt "honeypot not stored" "$rows" "honeypot"
cols=$(sql "SELECT group_concat(name) AS c FROM pragma_table_info('tips')"); hasnt "no ip column" "$cols" "ip"
rh=$(sql "SELECT h FROM rate_hits LIMIT 1"); hasnt "rate_hits has no raw IP" "$rh" "127.0.0.1"
# rate limit: 5 per hashed IP per 10 min (same CF-Connecting-IP); a different IP still passes
sql "DELETE FROM rate_hits" >/dev/null
for i in 1 2 3 4 5; do curl -s -o /dev/null "${J[@]}" -H 'CF-Connecting-IP: 203.0.113.9' -d '{"url":"https://e24.no/rl","country":"NO","website":"x"}' "$B/api/tip"; done
r=$(curl -s -w '|%{http_code}' "${J[@]}" -H 'CF-Connecting-IP: 203.0.113.9' -d '{"url":"https://e24.no/rl"}' "$B/api/tip"); chk "6th tip in 10 min 429" "${r##*|}" 429
r=$(curl -s -w '|%{http_code}' "${J[@]}" -H 'CF-Connecting-IP: 203.0.113.10' -d '{"url":"https://e24.no/other-ip","country":"FI"}' "$B/api/tip"); chk "other IP still 201" "${r##*|}" 201
hasnt "rate_hits stores no raw IP" "$(sql 'SELECT h FROM rate_hits')" "203.0.113"
hasnt "no raw IP anywhere in D1" "$(sql "SELECT * FROM tips"; sql "SELECT * FROM rate_hits"; sql "SELECT * FROM rate_salt")" "198.51.100"
chk "one salt row (today)" "$(sql "SELECT COUNT(*) AS n FROM rate_salt" | grep -oE '"n": *[0-9]+' | grep -oE '[0-9]+$')" 1
# logging: the dev log must not contain bodies or IPs
sleep 1; hasnt "dev log has no tip bodies" "$(cat /tmp/tipworker-dev.log)" "e24.no"; hasnt "dev log has no test IPs" "$(cat /tmp/tipworker-dev.log)" "203.0.113"
echo "---- $pass passed, $failc failed"
[[ $failc == 0 ]]
