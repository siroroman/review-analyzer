#!/usr/bin/env bash
# Decides which test jobs a pull request needs (scope table: docs/agents/testing.md, Test scope).
# Usage: check-test-scope.sh <base> <head>   what the PR changed since it branched off (CI)
#        <list of paths> | check-test-scope.sh   changed paths on stdin (tests)
# Prints `backend=true|false` and `frontend=true|false`.
# Docs (*.md, docs/**) and workflow files never trigger tests. A change to tests.yml still runs the `changes` job
# (with the tests of this script) and `tests-passed`, which is all it can break without code to test.
set -euo pipefail

# --no-renames: a moved file is listed under its old path too, so code leaving `app/` still counts as a change there.
# The list is captured first: under `set -e` a failing `git diff` stops the script, whereas a failing process
# substitution would be ignored and the empty list would read as "no tests needed" (a filter that fails open).
if [[ $# -eq 2 ]]; then
  changed=$(git diff --name-only --no-renames "$1...$2")
  exec <<< "$changed"
elif [[ $# -ne 0 ]]; then
  echo "usage: check-test-scope.sh [<base> <head>]  (paths on stdin without arguments)" >&2
  exit 1
fi

backend=false
frontend=false

while IFS= read -r path || [[ -n "$path" ]]; do
  [[ -n "$path" ]] || continue
  case "$path" in
    *.md) ;;
    app/*|tests/*|pyproject.toml|uv.lock|importlinter.ini|.coveragerc) backend=true ;;
    web/*) frontend=true ;;
  esac
done

echo "backend=$backend"
echo "frontend=$frontend"
