#!/usr/bin/env bash
# Decides which test jobs a pull request needs (scope table: docs/agents/testing.md, Test scope).
# Usage: git diff --name-only <base> <head> | check-test-scope.sh
# Reads changed paths on stdin, prints `backend=true|false` and `frontend=true|false`.
# Docs (*.md, docs/**) never trigger tests. The CI workflow file triggers both, so a change to it is always tested.
set -euo pipefail

backend=false
frontend=false

while IFS= read -r path || [[ -n "$path" ]]; do
  [[ -n "$path" ]] || continue
  case "$path" in
    .github/workflows/tests.yml) backend=true; frontend=true ;;
    *.md) ;;
    app/*|tests/*|pyproject.toml|uv.lock|importlinter.ini|.coveragerc) backend=true ;;
    frontend/*) frontend=true ;;
  esac
done

echo "backend=$backend"
echo "frontend=$frontend"
