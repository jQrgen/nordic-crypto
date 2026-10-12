#!/usr/bin/env bash
# Print the commands that create the D1 database. Creates it only when
# CLOUDFLARE_API_TOKEN is set and this script is run with --apply.
# Without the token, nothing is created.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

cat <<'EOF'
Nordic Crypto D1 setup. Nothing is created unless you pass --apply and CLOUDFLARE_API_TOKEN is set.

  export CLOUDFLARE_API_TOKEN='…'          # Account / D1 / Edit, and Workers Scripts / Edit
  export CLOUDFLARE_ACCOUNT_ID='…'
  export CF_ACCOUNT_ID="$CLOUDFLARE_ACCOUNT_ID"

  npx wrangler d1 create nordic-crypto-content
  # replace the zeros in wrangler.toml with the database_id that command prints
  npx wrangler d1 migrations apply nordic-crypto-content --remote

  export CF_D1_DATABASE_ID='…'
  python3 ../../tools/d1_import.py

  npx wrangler secret put EDITOR_TOKEN
  npx wrangler deploy

  gh secret set CLOUDFLARE_API_TOKEN
  gh variable set CF_ACCOUNT_ID --body "$CF_ACCOUNT_ID"
  gh variable set CF_D1_DATABASE_ID --body "$CF_D1_DATABASE_ID"
  gh variable set NC_DATA_SOURCE --body d1

Optional redeploy when an editor approves (fine-grained PAT, Actions: Read and write):
  npx wrangler secret put GITHUB_DISPATCH_TOKEN

Optional R2 copy of the nightly JSON backup:
  npx wrangler r2 bucket create nordic-crypto-content-backup
  gh variable set CF_R2_BUCKET --body nordic-crypto-content-backup
EOF

if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then
  echo "CLOUDFLARE_API_TOKEN is not set. Nothing was created." >&2
  exit 2
fi

if [ "${1:-}" != "--apply" ]; then
  echo "Token is set. Pass --apply to create the database. Nothing was created." >&2
  exit 0
fi

npx wrangler d1 create nordic-crypto-content
echo "Copy database_id into wrangler.toml, then: npx wrangler d1 migrations apply nordic-crypto-content --remote" >&2
