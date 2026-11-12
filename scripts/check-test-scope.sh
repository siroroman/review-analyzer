#!/usr/bin/env bash
# Decides which test jobs a pull request needs (scope table: docs/agents/testing.md, Test scope).
# Usage: git diff --name-only <base> <head> | check-test-scope.sh
# Reads changed paths on stdin, prints `backend=true|false` and `frontend=true|false`.
# Docs (*.md, docs/**) and workflow files never trigger tests. A change to tests.yml still runs the `changes` job
# (with the tests of this script) and `tests-passed`, which is all it can break without code to test.
set -euo pipefail

backend=false
frontend=false

while IFS= read -r path || [[ -n "$path" ]]; do
  [[ -n "$path" ]] || continue
  case "$path" in
    *.md) ;;
    app/*|tests/*|pyproject.toml|uv.lock|importlinter.ini|.coveragerc) backend=true ;;
    frontend/*) frontend=true ;;
  esac
done

echo "backend=$backend"
echo "frontend=$frontend"
