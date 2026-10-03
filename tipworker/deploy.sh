#!/usr/bin/env bash
# Deploys the Nordic Crypto tip Worker to workers.dev (Cloudflare Workers + D1). Needs env CLOUDFLARE_API_TOKEN
# (permissions: Account > Workers Scripts:Edit, Account > D1:Edit, Account > Account Settings:Read, User > Memberships:Read is enough).
#  1. finds the account id with the token (or uses CLOUDFLARE_ACCOUNT_ID)
#  2. creates the D1 database 'nordic-crypto-tips' if missing and writes its id into wrangler.toml
#  3. applies migrations/ to the remote database
#  4. deploys the Worker and checks https://<worker>.<subdomain>.workers.dev/api/health
#  5. sets public_endpoint in tipserver/config.json to that URL (the next ./publish.sh bakes it into /tip/)
# Publishes nothing to gh-pages.
set -euo pipefail
cd "$(dirname "$0")"; source ./env.sh
DBNAME=nordic-crypto-tips; WORKER=nordic-crypto-tips
[ -n "${CLOUDFLARE_API_TOKEN:-}" ] || { echo "CLOUDFLARE_API_TOKEN is not set"; exit 1; }
[ -d node_modules/wrangler ] || npm ci --no-audit --no-fund
api() { curl -fsS -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" "https://api.cloudflare.com/client/v4$1"; }
api /user/tokens/verify | python3 -c 'import json,sys;d=json.load(sys.stdin);assert d["success"] and d["result"]["status"]=="active",d' \
  || { echo "token is not valid/active"; exit 1; }
if [ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]; then
  CLOUDFLARE_ACCOUNT_ID=$(api /accounts | python3 -c 'import json,sys;r=json.load(sys.stdin)["result"];print(r[0]["id"] if len(r)==1 else "")')
  [ -n "$CLOUDFLARE_ACCOUNT_ID" ] || { echo "token sees 0 or several accounts; set CLOUDFLARE_ACCOUNT_ID"; exit 1; }
fi
export CLOUDFLARE_ACCOUNT_ID; echo "account: $CLOUDFLARE_ACCOUNT_ID"
# 2) D1 database
dbid=$(api "/accounts/$CLOUDFLARE_ACCOUNT_ID/d1/database?name=$DBNAME" | python3 -c "import json,sys;r=[d for d in json.load(sys.stdin)['result'] if d['name']=='$DBNAME'];print(r[0]['uuid'] if r else '')")
if [ -z "$dbid" ]; then
  echo "creating D1 database $DBNAME"; wr d1 create "$DBNAME" >/dev/null
  dbid=$(api "/accounts/$CLOUDFLARE_ACCOUNT_ID/d1/database?name=$DBNAME" | python3 -c "import json,sys;r=[d for d in json.load(sys.stdin)['result'] if d['name']=='$DBNAME'];print(r[0]['uuid'] if r else '')")
fi
[ -n "$dbid" ] || { echo "could not find/create D1 database"; exit 1; }
python3 - "$dbid" <<'PY'
import re,sys;p="wrangler.toml";s=open(p).read()
s2=re.sub(r'(database_id = ")[^"]*(")', lambda m: m.group(1)+sys.argv[1]+m.group(2), s); open(p,"w").write(s2)
PY
echo "D1: $DBNAME ($dbid)"
# 3) migrations
wr d1 migrations apply "$DBNAME" --remote
# 4) deploy (needs a workers.dev subdomain on the account; register one once in the dashboard if missing)
out=$(wr deploy 2>&1) || { echo "$out"; exit 1; }
echo "$out" | grep -v -i "token" | tail -15
url=$(echo "$out" | grep -oE 'https://[A-Za-z0-9.-]+\.workers\.dev' | head -1 || true)
if [ -z "$url" ]; then
  sub=$(api "/accounts/$CLOUDFLARE_ACCOUNT_ID/workers/subdomain" | python3 -c 'import json,sys;print(json.load(sys.stdin)["result"]["subdomain"])')
  url="https://$WORKER.$sub.workers.dev"
fi
echo "worker URL: $url"
ok=""; for i in $(seq 1 30); do curl -fsS --max-time 10 "$url/api/health" | grep -q '"ok": *true' && { ok=1; break; }; sleep 3; done
[ -n "$ok" ] || { echo "health check FAILED at $url/api/health – config.json not changed"; exit 1; }
echo "health: ok"
# 5) public_endpoint -> tipserver/config.json
python3 - "$url" <<'PY'
import json,sys;p="../tipserver/config.json";c=json.load(open(p));c["public_endpoint"]=sys.argv[1].rstrip("/");c["quick_tunnel"]=False
json.dump(c,open(p,"w"),ensure_ascii=False,indent=1);open(p,"a").write("\n")
PY
echo "tipserver/config.json: public_endpoint = $url (then tipworker/publish_tip_page.sh --yes, with jQrgen's approval, puts ONLY /tip/ live)"
