#!/usr/bin/env bash
# Deploys the Nordic Crypto push Worker (Workers + KV). Does not publish the website.
# Needs CLOUDFLARE_API_TOKEN. Does not print secret values.
# Token permissions: Account › Workers Scripts › Edit, Account › Workers KV Storage › Edit,
# Account › Account Settings › Read. The account needs a workers.dev subdomain.
set -euo pipefail
cd "$(dirname "$0")"
WORKER=nordic-crypto-push
[ -n "${CLOUDFLARE_API_TOKEN:-}" ] || { echo "CLOUDFLARE_API_TOKEN is not set"; exit 1; }
[ -d node_modules/wrangler ] || npm ci --no-audit --no-fund
api() { curl -fsS -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H "Content-Type: application/json" "https://api.cloudflare.com/client/v4$1" ${2:+-d "$2"}; }
api /user/tokens/verify | python3 -c 'import json,sys;d=json.load(sys.stdin);assert d["success"] and d["result"]["status"]=="active",d'
if [ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]; then
  CLOUDFLARE_ACCOUNT_ID=$(api /accounts | python3 -c 'import json,sys;r=json.load(sys.stdin)["result"];print(r[0]["id"] if len(r)==1 else "")')
  [ -n "$CLOUDFLARE_ACCOUNT_ID" ] || { echo "token sees 0 or several accounts; set CLOUDFLARE_ACCOUNT_ID"; exit 1; }
fi
export CLOUDFLARE_ACCOUNT_ID
echo "account: $CLOUDFLARE_ACCOUNT_ID"
kvid=$(api "/accounts/$CLOUDFLARE_ACCOUNT_ID/storage/kv/namespaces" | python3 -c "import json,sys;r=[d for d in json.load(sys.stdin)['result'] if d['title']=='$WORKER'];print(r[0]['id'] if r else '')")
if [ -z "$kvid" ]; then
  echo "creating KV namespace $WORKER"
  kvid=$(api "/accounts/$CLOUDFLARE_ACCOUNT_ID/storage/kv/namespaces" "{\"title\":\"$WORKER\"}" | python3 -c 'import json,sys;print(json.load(sys.stdin)["result"]["id"])')
fi
[ -n "$kvid" ] || { echo "could not find or create the KV namespace"; exit 1; }
python3 - "$kvid" <<'PY'
import re, sys
p = "wrangler.toml"
s = open(p, encoding="utf-8").read()
s2 = re.sub(r'(binding = "SUBSCRIPTIONS"\n)id = "[^"]*"', lambda m: m.group(1) + 'id = "' + sys.argv[1] + '"', s, count=1)
open(p, "w", encoding="utf-8").write(s2)
PY
echo "KV SUBSCRIPTIONS: $kvid"
if ! npx wrangler secret list 2>/dev/null | python3 -c 'import json,sys;names={x.get("name") for x in json.load(sys.stdin)};need={"VAPID_PUBLIC_KEY","VAPID_PRIVATE_KEY","PUBLISH_TOKEN"};missing=need-names;sys.exit(0 if not missing else print("missing secrets:", ", ".join(sorted(missing))) or 1)'; then
  echo "Set the three secrets, then run deploy.sh again. Generate them with: node keys.mjs"
  echo "  npx wrangler secret put VAPID_PUBLIC_KEY"
  echo "  npx wrangler secret put VAPID_PRIVATE_KEY"
  echo "  npx wrangler secret put PUBLISH_TOKEN"
  echo "Do not write those values into the repo."
  exit 1
fi
out=$(npx wrangler deploy 2>&1) || { echo "$out"; exit 1; }
echo "$out" | grep -viE 'token|vapid|bearer' | tail -20
url=$(echo "$out" | grep -oE 'https://[A-Za-z0-9.-]+\.workers\.dev' | head -1 || true)
if [ -z "$url" ]; then
  sub=$(api "/accounts/$CLOUDFLARE_ACCOUNT_ID/workers/subdomain" | python3 -c 'import json,sys;print(json.load(sys.stdin)["result"]["subdomain"])')
  url="https://$WORKER.$sub.workers.dev"
fi
echo "worker URL: $url"
ok=""
for i in $(seq 1 20); do
  curl -fsS --max-time 10 "$url/api/push/health" | grep -q '"ok": *true' && { ok=1; break; }
  sleep 3
done
[ -n "$ok" ] || { echo "health check failed at $url/api/push/health"; exit 1; }
python3 - "$url" <<'PY'
import json, sys
p = "public.json"
c = json.load(open(p, encoding="utf-8"))
c["public_endpoint"] = sys.argv[1].rstrip("/")
json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
open(p, "a", encoding="utf-8").write("\n")
PY
echo "workers/push/public.json public_endpoint = $url"
echo "Next, on the machine that runs publish.sh: export PUSH_PUBLISH_TOKEN to the same PUBLISH_TOKEN."
echo "The site picks up the Worker URL on the next approved ./publish.sh --yes. This script does not publish."
