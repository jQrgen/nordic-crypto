#!/usr/bin/env bash
# Commit a staged D1 JSON backup onto the d1-backup branch and push that branch.
# Never pushes main or gh-pages. Never commits private terms, teasers or the HTML cache.
# A rejected push is not force-pushed.
#
# Usage: tools/d1_backup.sh STAGED_DIR YYYY-MM-DD
set -euo pipefail

tool_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
repo=${NC_BACKUP_REPO:-$tool_root}
staged=${1:-}
date=${2:-}
branch=d1-backup

if [ -z "$staged" ] || [ -z "$date" ]; then
  echo "usage: tools/d1_backup.sh STAGED_DIR YYYY-MM-DD" >&2
  exit 2
fi
if [ ! -d "$staged" ]; then
  echo "d1 backup: staged directory is missing" >&2
  exit 1
fi

export NC_TOOL_ROOT="$tool_root"
python3 -c 'import os, sys; sys.path.insert(0, os.environ["NC_TOOL_ROOT"]); from tools.d1_store import assert_backup_dir; assert_backup_dir(sys.argv[1])' "$staged"

if [ -e "$repo/state/private_terms.json" ] || [ -e "$staged/private_terms.json" ]; then
  echo "refusing: private terms must not be committed" >&2
  exit 1
fi

cd "$repo"
export GIT_TERMINAL_PROMPT=0
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git config commit.gpgsign false

parent=$(mktemp -d)
wt="$parent/wt"
cleanup() {
  git worktree remove --force "$wt" >/dev/null 2>&1 || true
  rm -rf "$parent"
}
trap cleanup EXIT

if git rev-parse --verify "refs/remotes/origin/$branch" >/dev/null 2>&1; then
  git worktree add --detach "$wt" "origin/$branch"
elif git rev-parse --verify "refs/heads/$branch" >/dev/null 2>&1; then
  git worktree add --detach "$wt" "$branch"
else
  git worktree add --detach "$wt" HEAD
  git -C "$wt" checkout --orphan "$branch"
  git -C "$wt" rm -rf . >/dev/null 2>&1 || true
fi

mkdir -p "$wt/backup/$date"
cp -a "$staged"/. "$wt/backup/$date"/
python3 -c 'import os, sys; sys.path.insert(0, os.environ["NC_TOOL_ROOT"]); from tools.d1_store import assert_backup_dir; assert_backup_dir(sys.argv[1])' "$wt/backup/$date"

git -C "$wt" add "backup/$date"
if git -C "$wt" diff --cached --quiet; then
  echo "d1 backup: no change"
  exit 0
fi
git -C "$wt" commit -m "D1 backup $date [skip ci]"
git -C "$wt" push origin "HEAD:$branch"
echo "d1 backup: pushed $branch backup/$date"
