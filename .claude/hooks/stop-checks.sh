#!/usr/bin/env bash
# Stop hook: when code changed (since origin/main or in the working tree), runs `make lint test`.
# On failure it prints the output to stderr and exits 2, so the agent sees it and continues.
# It does not loop: a second stop in a row (`stop_hook_active`) is let through.
# Tests: scripts/test-stop-checks.sh
set -uo pipefail

if command -v jq >/dev/null; then
  ACTIVE=$(jq -r '.stop_hook_active // false' 2>/dev/null) || ACTIVE=false
  [ "$ACTIVE" = true ] && exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

BASE=$(git merge-base HEAD origin/main 2>/dev/null) || BASE=HEAD
CHANGED=$({
  git diff --name-only "$BASE" 2>/dev/null
  git ls-files --others --exclude-standard 2>/dev/null
})
printf '%s\n' "$CHANGED" | grep -qE '\.py$|^(pyproject\.toml|uv\.lock|importlinter\.ini)$' || exit 0

if OUT=$(make lint test 2>&1); then
  exit 0
fi
{
  echo "Stop hook: 'make lint test' failed. Fix it before you finish."
  printf '%s\n' "$OUT" | tail -n 60
} >&2
exit 2
