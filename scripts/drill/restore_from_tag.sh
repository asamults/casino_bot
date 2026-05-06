#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

require_cmd git
require_cmd docker

tag="${1:-}"
[[ -n "$tag" ]] || fail "usage: scripts/drill/restore_from_tag.sh <git-tag>"

echo "Runbook: docs/runbooks/rollback-procedure.md"
echo "Restoring from tag=$tag via git worktree (non-destructive)"

wt_dir=".worktrees/restore-$tag"
rm -rf "$wt_dir"
mkdir -p ".worktrees"

git fetch --tags >/dev/null 2>&1 || true
git worktree add "$wt_dir" "$tag" >/dev/null

(
  cd "$wt_dir"
  echo "Building and starting services from tag worktree..."
  docker compose up -d --build >/dev/null
  API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}" scripts/drill/smoke.sh
)

pass "restore_from_tag OK (tag=$tag, worktree=$wt_dir)"

