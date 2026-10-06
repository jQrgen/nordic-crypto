#!/usr/bin/env bash
# Local tests for the newsletter signup (POST /api/subscribe, GET /api/confirm, GET/POST /api/unsubscribe) against
# `wrangler dev --local` (Miniflare + local D1 in .wrangler/state – nothing touches Cloudflare, no email is sent:
# SUBSCRIBE_TEST=1 selects the in-memory test mailer and returns the confirmation token in the response).
# Usage: ./test_subscribe.sh   (port: TW_PORT, default 8789)
set -uo pipefail
cd "$(dirname "$0")"; source ./env.sh
NC=$(python3 -c 'import sys; sys.path.insert(0, ".."); import site_url; print(site_url.BASE)')
PORT=${TW_PORT:-8789}; B="http://127.0.0.1:$PORT"; GOOD=https://jqrgen.github.io; BAD=https://evil.example; SECRET=test-unsub-secret
pass=0; failc=0
ok() { echo "PASS  $1"; pass=$((pass+1)); }; ko() { echo "FAIL  $1  ($2)"; failc=$((failc+1)); }
chk() { [[ $2 == "$3" ]] && ok "$1" || ko "$1" "got $2, want $3"; }
has() { grep -qi -- "$3" <<<"$2" && ok "$1" || ko "$1" "missing $3"; }
hasnt() { grep -qi -- "$3" <<<"$2" && ko "$1" "unexpected $3" || ok "$1"; }
sql() { npx --no-install wrangler d1 execute nordic-crypto-tips --local --json --command "$1" 2>/dev/null; }
val() { grep -oE "\"$1\": *(\"[^\"]*\"|[0-9]+|null)" | head -1 | sed -E 's/^[^:]+: *"?([^"]*)"?$/\1/'; }
rm -rf .wrangler/state
npx --no-install wrangler d1 migrations apply nordic-crypto-tips --local >/dev/null 2>&1 || { echo "migration failed"; exit 1; }
curl -s -o /dev/null "$B/" 2>/dev/null && { echo "port $PORT is already in use"; exit 1; }
setsid npx --no-install wrangler dev --local --ip 127.0.0.1 --port "$PORT" --var SUBSCRIBE_TEST:1 --var UNSUB_SECRET:$SECRET >/tmp/tipworker-sub-dev.log 2>&1 & DEV=$!
trap 'kill -- -$DEV 2>/dev/null; wait $DEV 2>/dev/null' EXIT
for i in $(seq 1 60); do curl -fsS "$B/api/health" >/dev/null 2>&1 && break; sleep 0.5; done
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
hdr() { curl -s -D - -o /dev/null "$@"; }
J=(-H 'Content-Type: application/json' -H 'Accept: application/json')
CNT=$(mktemp); echo 0 >"$CNT"; ip() { local n=$(( $(cat "$CNT") + 1 )); echo $n >"$CNT"; echo "198.51.100.$n"; }   # $(...) runs in a subshell, so count in a file
sub() { curl -s -w '|%{http_code}' "${J[@]}" -H "CF-Connecting-IP: $2" -H "Origin: $GOOD" -d "$1" "$B/api/subscribe"; }
sig() { printf '%s' "$1" | openssl dgst -sha256 -hmac "$SECRET" -hex | sed 's/^.* //' | cut -c1-40; }
# CORS
h=$(hdr -X OPTIONS "$B/api/subscribe" -H "Origin: $GOOD" -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type')
has "preflight subscribe 204" "$h" "HTTP/1.1 204"; has "preflight ACAO github.io" "$h" "access-control-allow-origin: $GOOD"
h=$(hdr -X OPTIONS "$B/api/subscribe" -H "Origin: $BAD" -H 'Access-Control-Request-Method: POST'); has "preflight bad origin 403" "$h" "HTTP/1.1 403"; hasnt "no ACAO for bad origin" "$h" "access-control-allow-origin"
r=$(curl -s -w '|%{http_code}' "${J[@]}" -H "Origin: $BAD" -d '{"email":"a@example.org","site":"nordic-crypto"}' "$B/api/subscribe"); chk "POST bad origin 403" "${r##*|}" 403
# validation
I=$(ip)
r=$(sub '{"email":"not-an-email","site":"nordic-crypto","lang":"en"}' $I); chk "bad email 400" "${r##*|}" 400; has "bad email code" "$r" '"error":"email"'
r=$(sub '{"email":"a@b","site":"nordic-crypto"}' $I); chk "dotless domain 400" "${r##*|}" 400
r=$(sub '{"email":"a@example.org","site":"other"}' $I); chk "unknown site 400" "${r##*|}" 400; has "site code" "$r" '"error":"site"'
r=$(sub '{"email":"a@example.org","site":"kryptonytt","lang":"sv"}' $(ip)); chk "lang not on site 400" "${r##*|}" 400; has "lang code" "$r" '"error":"lang"'
r=$(sub '{"email":123,"site":"kryptonytt"}' $(ip)); chk "non-string 400" "${r##*|}" 400
r=$(sub '[1]' $(ip)); chk "array body 400" "${r##*|}" 400
r=$(curl -s -w '|%{http_code}' -H 'Content-Type: text/plain' -H "CF-Connecting-IP: $(ip)" -d x "$B/api/subscribe"); chk "text/plain 415" "${r##*|}" 415
big=$(printf 'y%.0s' $(seq 3000)); r=$(sub "{\"email\":\"a@example.org\",\"site\":\"kryptonytt\",\"x\":\"$big\"}" $(ip)); chk "body > 2 KB 413" "${r##*|}" 413
r=$(sub '{"email":"hp@example.org","site":"nordic-crypto","website":"http://spam"}' $(ip)); chk "honeypot 202" "${r##*|}" 202
hasnt "honeypot not stored" "$(sql "SELECT email FROM subscribers")" "hp@example.org"
# signup -> pending, token only as hash
r=$(sub '{"email":"  Kari@Example.ORG ","site":"kryptonytt","lang":"nb"}' $(ip)); chk "signup 202" "${r##*|}" 202; has "pending" "$r" '"pending":true'
TOK=$(val test_token <<<"$r"); [[ $TOK =~ ^[0-9a-f]{64}$ ]] && ok "test token returned (test mode only)" || ko "test token" "$TOK"
row=$(sql "SELECT email, site, lang, status, token_hash FROM subscribers WHERE email='kari@example.org'")
has "email lower-cased+trimmed" "$row" '"email": "kari@example.org"'; has "status pending" "$row" '"status": "pending"'; has "lang nb" "$row" '"lang": "nb"'
hasnt "token not stored in clear" "$row" "$TOK"; has "token hash stored" "$row" "$(printf '%s' "$TOK" | sha256sum | cut -c1-64)"
cols=$(sql "SELECT group_concat(name) AS c FROM pragma_table_info('subscribers')"); hasnt "no ip column" "$cols" "ip"; hasnt "no user agent column" "$cols" "agent"
# same address again within 10 min: same answer, no new token/email
r=$(sub '{"email":"kari@example.org","site":"kryptonytt","lang":"nb"}' $(ip)); chk "repeat 202" "${r##*|}" 202; hasnt "repeat: no resend" "$r" "test_token"
# same address on the other site is a separate subscription
r=$(sub '{"email":"kari@example.org","site":"nordic-crypto","lang":"sv"}' $(ip)); has "other site gets own token" "$r" "test_token"; TOK_NC=$(val test_token <<<"$r")
# confirm
h=$(hdr "$B/api/confirm?token=nothex&s=kryptonytt&l=nb"); has "bad token 303" "$h" "HTTP/1.1 303"; has "bad token -> invalid_link" "$h" "location: https://jqrgen.github.io/kryptonytt/bm/nyhetsbrev/?error=invalid_link"
h=$(hdr -I "$B/api/confirm?token=$TOK&s=kryptonytt&l=nb"); has "HEAD confirm 200" "$h" "HTTP/1.1 200"
has "HEAD does not confirm" "$(sql "SELECT status FROM subscribers WHERE email='kari@example.org' AND site='kryptonytt'")" '"pending"'
h=$(hdr "$B/api/confirm?token=$TOK&s=kryptonytt&l=nb"); has "confirm 303" "$h" "HTTP/1.1 303"; has "confirm -> confirmed=1 (bm)" "$h" "location: https://jqrgen.github.io/kryptonytt/bm/nyhetsbrev/?confirmed=1"
row=$(sql "SELECT status, token_hash, confirmed_at FROM subscribers WHERE email='kari@example.org' AND site='kryptonytt'")
has "status confirmed" "$row" '"confirmed"'; has "token hash cleared" "$row" '"token_hash": null'
h=$(hdr "$B/api/confirm?token=$TOK&s=kryptonytt&l=nb"); has "token single-use" "$h" "error=invalid_link"
r=$(sub '{"email":"kari@example.org","site":"kryptonytt","lang":"nn"}' $(ip)); chk "already confirmed: same 202" "${r##*|}" 202; hasnt "confirmed: no new token" "$r" "test_token"
has "confirmed stays confirmed" "$(sql "SELECT status FROM subscribers WHERE email='kari@example.org' AND site='kryptonytt'")" '"confirmed"'
# expiry
sql "UPDATE subscribers SET token_expires = 1 WHERE email='kari@example.org' AND site='nordic-crypto'" >/dev/null
h=$(hdr "$B/api/confirm?token=$TOK_NC&s=nordic-crypto&l=sv"); has "expired token -> invalid_link (sv page)" "$h" "location: ${NC}sv/newsletter/?error=invalid_link"
sub '{"email":"other@example.org","site":"nordic-crypto"}' $(ip) >/dev/null
hasnt "expired pending row deleted on next signup" "$(sql "SELECT site FROM subscribers WHERE email='kari@example.org'")" "nordic-crypto"
# form post (no JS) -> 303 back to the site's page
h=$(hdr -H "CF-Connecting-IP: $(ip)" -H "Origin: $GOOD" --data-urlencode 'email=form@example.org' --data-urlencode 'site=nordic-crypto' --data-urlencode 'lang=fi' "$B/api/subscribe")
has "form 303" "$h" "HTTP/1.1 303"; has "form -> fi page sent=1" "$h" "location: ${NC}fi/newsletter/?sent=1"
h=$(hdr -H "CF-Connecting-IP: $(ip)" -H "Origin: $GOOD" --data-urlencode 'email=nope' --data-urlencode 'site=kryptonytt' --data-urlencode 'lang=nn' "$B/api/subscribe")
has "form error -> nn page" "$h" "location: https://jqrgen.github.io/kryptonytt/nyhetsbrev/?error=email"
# unsubscribe (HMAC link, nothing stored)
ID=$(sql "SELECT id FROM subscribers WHERE email='kari@example.org' AND site='kryptonytt'" | val id)
S=$(sig "$ID|kari@example.org|kryptonytt"); U="$B/api/unsubscribe?id=$ID&sig=$S&s=kryptonytt&l=nn"
r=$(curl -s -w '|%{http_code}' "$U"); chk "unsubscribe page 200" "${r##*|}" 200; has "page asks (nn)" "$r" "Vil du melde deg av nyheitsbrevet frå Kryptonytt Norge"; has "page has POST button" "$r" 'method="post"'
has "GET does not unsubscribe" "$(sql "SELECT status FROM subscribers WHERE id=$ID")" '"confirmed"'
chk "bad sig page 400" "$(code "$B/api/unsubscribe?id=$ID&sig=$(printf '0%.0s' $(seq 40))&s=kryptonytt&l=nn")" 400
h=$(hdr -X POST -H "Origin: null" "$B/api/unsubscribe?id=$ID&sig=$(printf 'a%.0s' $(seq 40))"); has "POST bad sig -> invalid_link" "$h" "error=invalid_link"
h=$(hdr -X POST -H "Origin: null" -H 'Content-Type: application/x-www-form-urlencoded' -d '' "$U"); has "POST unsubscribe 303" "$h" "HTTP/1.1 303"; has "-> unsubscribed=1 (nb row lang)" "$h" "location: https://jqrgen.github.io/kryptonytt/bm/nyhetsbrev/?unsubscribed=1"
has "status unsubscribed" "$(sql "SELECT status FROM subscribers WHERE id=$ID")" '"unsubscribed"'
r=$(sub '{"email":"kari@example.org","site":"kryptonytt","lang":"nn"}' $(ip)); has "re-subscribe after unsubscribe gets a new token" "$r" "test_token"
has "re-subscribe -> pending" "$(sql "SELECT status FROM subscribers WHERE id=$ID")" '"pending"'
OID=$(sql "SELECT id FROM subscribers WHERE email='other@example.org'" | val id)
r=$(curl -s -w '|%{http_code}' -X POST -d 'List-Unsubscribe=One-Click' "$B/api/unsubscribe?id=$OID&sig=$(sig "$OID|other@example.org|nordic-crypto")"); chk "RFC 8058 one-click 200" "${r##*|}" 200
has "one-click unsubscribed" "$(sql "SELECT status FROM subscribers WHERE id=$OID")" '"unsubscribed"'
# rate limit: 5 signups per hashed IP per 10 min
for i in 1 2 3 4 5; do sub "{\"email\":\"rl$i@example.org\",\"site\":\"nordic-crypto\"}" 203.0.113.50 >/dev/null; done
r=$(sub '{"email":"rl6@example.org","site":"nordic-crypto"}' 203.0.113.50); chk "6th signup in 10 min 429" "${r##*|}" 429
hasnt "no raw IP in D1" "$(sql "SELECT * FROM subscribers"; sql "SELECT * FROM rate_hits")" "203.0.113"
# CSV export: only confirmed rows (local D1)
r=$(sub '{"email":"exp@example.org","site":"kryptonytt","lang":"en"}' $(ip)); T2=$(val test_token <<<"$r"); curl -s -o /dev/null "$B/api/confirm?token=$T2&s=kryptonytt&l=en"
X=$(mktemp -d)/k.csv; o=$(python3 export_subscribers.py --site kryptonytt --local --out "$X" 2>&1)
has "export ran" "$o" "confirmed subscribers for kryptonytt"; hasnt "export prints no addresses" "$o" "@example.org"
chk "export = header + confirmed only" "$(cat "$X" | cut -d, -f1 | tr '\n' ' ')" "email exp@example.org "
# tips still work next to it
r=$(curl -s -w '|%{http_code}' "${J[@]}" -H "CF-Connecting-IP: $(ip)" -d '{"url":"https://e24.no/x","country":"NO"}' "$B/api/tip"); chk "tip endpoint still 201" "${r##*|}" 201
sleep 1; hasnt "dev log has no emails" "$(cat /tmp/tipworker-sub-dev.log)" "example.org"
echo "---- $pass passed, $failc failed"
[[ $failc == 0 ]]
