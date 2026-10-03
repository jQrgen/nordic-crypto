# Sourced by the tipworker scripts: wrangler 4 needs Node >= 22. Uses ~/.local/node22 when the system node is older.
if [ -x "$HOME/.local/node22/bin/node" ] && ! node -e 'process.exit(+process.versions.node.split(".")[0] < 22)' 2>/dev/null; then
  export PATH="$HOME/.local/node22/bin:$PATH"
fi
export WRANGLER_SEND_METRICS=false
TW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
wr() { (cd "$TW_DIR" && npx --no-install wrangler "$@"); }
