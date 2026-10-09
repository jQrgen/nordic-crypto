#!/bin/sh
# Install a hot-wallet key into Cloudflare's Worker secret store.
# The operator runs this. It is not part of the build, and it refuses unless
# MINT_KEYGEN_I_AM_THE_OPERATOR=yes.
#
# The key is not written to a file. It is read with echo off and piped into
# `wrangler secret put`, which stores it in Cloudflare's secret store. A later
# deploy or a new isolate loads that same secret. That store is how the key
# survives a restart. An extra copy in a password manager is optional and is
# not how a new instance recovers.
#
# Create the key in Wally (Nexa) or Electron Cash (Bitcoin Cash), which know
# the address format. This script does not invent an address.
set -eu
cd "$(dirname "$0")"
if [ "${MINT_KEYGEN_I_AM_THE_OPERATOR:-}" != "yes" ]; then
  echo "Refusing. The operator runs this, with MINT_KEYGEN_I_AM_THE_OPERATOR=yes." >&2
  exit 1
fi
chain="${1:-}"
case "$chain" in
  nexa) name=NEXA_HOT_KEY ;;
  bch) name=BCH_HOT_KEY ;;
  *) echo "Usage: MINT_KEYGEN_I_AM_THE_OPERATOR=yes $0 nexa|bch" >&2; exit 1 ;;
esac
if ! command -v npx >/dev/null 2>&1; then
  echo "npx is required so the key can be piped into wrangler." >&2
  exit 1
fi
echo "Paste the $chain private key. It will not be echoed and will not be saved to a file."
printf "> "
stty -echo
IFS= read -r key
stty echo
printf "\n"
if [ "${#key}" -lt 32 ]; then
  unset key
  echo "Key too short. Nothing was stored." >&2
  exit 1
fi
printf "%s" "$key" | npx --no-install wrangler secret put "$name"
unset key
echo "Stored as Worker secret $name. A redeploy keeps it. No file was written."
echo "Optional: a copy in your password manager is your own affair. The server does not read it. Do not commit a key and do not leave one on disk."
