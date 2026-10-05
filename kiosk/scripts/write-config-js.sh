#!/usr/bin/env bash
# Build web/config.js from config.env (no secrets; all public).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${1:-$ROOT/config.env}"
OUT="$ROOT/web/config.js"

API_BASE="https://raw.githubusercontent.com/jQrgen/nordic-crypto/gh-pages"
NEWS_PATH="/api/v1/news.json"
NEWS_REFRESH_SEC=900
SLIDE_SEC=22
LANG=en
MAX_ITEMS=24

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE"; set +a
fi

cat > "$OUT" <<JS
window.NCK_CONFIG = {
  apiBase: $(printf '%s' "$API_BASE" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))'),
  newsPath: $(printf '%s' "$NEWS_PATH" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))'),
  newsRefreshSec: ${NEWS_REFRESH_SEC},
  slideSec: ${SLIDE_SEC},
  lang: $(printf '%s' "$LANG" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))'),
  maxItems: ${MAX_ITEMS}
};
JS
echo "Wrote $OUT"
