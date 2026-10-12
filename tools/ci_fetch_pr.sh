#!/usr/bin/env bash
# Open or update the pull request that shows fetch-queue to the editor.
# Does not merge. Pending stories are not approved by opening this request.
set -euo pipefail

tool_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
repo=${NC_FETCH_REPO:-$tool_root}
cd "$repo"
export NC_ROOT="$repo"

if [ -z "${GH_TOKEN:-${GITHUB_TOKEN:-}}" ]; then
  echo "fetch-queue: no token, not opening a pull request"
  exit 0
fi
export GH_TOKEN="${GH_TOKEN:-$GITHUB_TOKEN}"

if ! git rev-parse --verify origin/fetch-queue >/dev/null 2>&1; then
  git fetch origin fetch-queue || true
fi
if ! git rev-parse --verify origin/fetch-queue >/dev/null 2>&1; then
  echo "fetch-queue: branch is not on origin, not opening a pull request"
  exit 0
fi

body=$(mktemp)
trap 'rm -f "$body"' EXIT
python3 "$tool_root/tools/ci_fetch_queue.py" pr-body > "$body"
title="Fetch queue: stories awaiting the editor"

existing=$(gh pr list --head fetch-queue --base main --state open --json number --jq '.[0].number')
if [ -z "$existing" ] || [ "$existing" = "null" ]; then
  url=$(gh pr create --base main --head fetch-queue --title "$title" --body-file "$body")
else
  gh pr edit "$existing" --title "$title" --body-file "$body" >/dev/null
  url=$(gh pr view "$existing" --json url --jq .url)
fi
printf '%s\n' "$url"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  printf '\nPull request: %s\n' "$url" >> "$GITHUB_STEP_SUMMARY"
fi
