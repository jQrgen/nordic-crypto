#!/usr/bin/env bash
# Put the editor queue on the fetch-queue branch and push that branch.
# Never pushes main or gh-pages. Never commits state/private_terms.json.
# A rejected push is rebased and tried again. This script does not force-push.
#
# restore: copy the previous queue onto the current checkout (main) so the fetch can see it.
# push:    commit the packed queue onto fetch-queue. Discards other working-tree edits first.
#
# Usage: tools/ci_push_fetch_queue.sh restore|push
set -euo pipefail

tool_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
repo=${NC_FETCH_REPO:-$tool_root}
cd "$repo"
export NC_ROOT="$repo"
export GIT_TERMINAL_PROMPT=0

py() { python3 "$tool_root/tools/ci_fetch_queue.py" "$@"; }

terms_present() {
  [ -e state/private_terms.json ] || [ -e state/private_terms.json.tmp ]
}

refuse_terms() {
  if terms_present; then
    rm -f state/private_terms.json state/private_terms.json.tmp
    echo "refusing: state/private_terms.json must not be committed" >&2
    exit 1
  fi
}

cmd=${1:-push}

if [ "$cmd" = "restore" ]; then
  git fetch origin fetch-queue || true
  if ! git rev-parse --verify origin/fetch-queue >/dev/null 2>&1; then
    echo "fetch-queue: no previous queue"
    exit 0
  fi
  while IFS= read -r path; do
    git checkout origin/fetch-queue -- "$path" 2>/dev/null || true
  done < <(py allowed-paths)
  git checkout origin/fetch-queue -- queue/approved.json 2>/dev/null || true
  git reset -q HEAD
  refuse_terms
  echo "fetch-queue: restored"
  exit 0
fi

if [ "$cmd" != "push" ]; then
  echo "usage: tools/ci_push_fetch_queue.sh restore|push" >&2
  exit 2
fi

if terms_present; then
  echo "refusing: state/private_terms.json is on disk" >&2
  exit 1
fi

tmp=$(mktemp -d)
cache=$(mktemp)
trap 'rm -rf "$tmp"; rm -f "$cache"' EXIT
py stage "$tmp"
py check "$tmp"

kept_cache=0
if [ -f state/http_cache.json ]; then
  cp state/http_cache.json "$cache"
  kept_cache=1
fi

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git config commit.gpgsign false

git reset --hard HEAD
rm -rf queue state logs site
mkdir -p state
if [ "$kept_cache" -eq 1 ]; then
  cp "$cache" state/http_cache.json
fi

git fetch origin main
git fetch origin fetch-queue || true

if git rev-parse --verify origin/fetch-queue >/dev/null 2>&1; then
  git checkout -B fetch-queue origin/fetch-queue
  if ! git merge origin/main --no-edit; then
    echo "refusing: merge from main conflicted. Not force-pushing." >&2
    exit 1
  fi
else
  git checkout -B fetch-queue origin/main
fi

refuse_terms

py install "$tmp"

add=()
while IFS= read -r path; do
  if [ -f "$path" ]; then
    add+=("$path")
  fi
done < <(py allowed-paths)
if [ "${#add[@]}" -eq 0 ]; then
  echo "refusing: no queue files to commit" >&2
  exit 1
fi
git add -f -- "${add[@]}"

git diff --cached --name-only | py check-index
git diff --name-only origin/main | py check-diff

if git ls-files --error-unmatch state/private_terms.json >/dev/null 2>&1; then
  echo "refusing: state/private_terms.json is tracked" >&2
  exit 1
fi

if git diff --cached --quiet; then
  if ! git rev-parse --verify origin/fetch-queue >/dev/null 2>&1 \
    || [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/fetch-queue)" ]; then
    echo "fetch-queue: no changes"
    exit 0
  fi
else
  git commit -m "$(py commit-message)"
fi

branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$branch" != "fetch-queue" ]; then
  echo "refusing: not on fetch-queue" >&2
  exit 1
fi
if ! git diff --quiet origin/main -- data; then
  echo "refusing: data/ differs from main" >&2
  exit 1
fi

attempt=1
while [ "$attempt" -le 3 ]; do
  if git push origin HEAD:fetch-queue; then
    echo "fetch-queue: pushed"
    exit 0
  fi
  echo "push rejected (attempt ${attempt}/3); rebasing on fetch-queue" >&2
  if ! git pull --rebase origin fetch-queue; then
    echo "::error::fetch-queue rebase conflicted. Not force-pushing." >&2
    exit 1
  fi
  attempt=$((attempt + 1))
done
echo "::error::fetch-queue push failed after 3 attempts. Not force-pushing." >&2
exit 1
