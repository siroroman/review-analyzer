#!/usr/bin/env bash
# Tests of scripts/check-coverage.sh. Run: scripts/test-check-coverage.sh
set -uo pipefail
cd "$(dirname "$0")"
fails=0
# file <path> <statements> <covered lines> <branches> <covered branches>
file() { jq -n --arg p "$1" --argjson s "$2" --argjson c "$3" --argjson b "$4" --argjson cb "$5" \
  '{($p): {summary: {num_statements: $s, covered_lines: $c, num_branches: $b, covered_branches: $cb}}}'; }
report() { jq -s '{files: (add)}'; }
ok()  { echo "$2" | ./check-coverage.sh >/dev/null 2>&1 || { echo "FAIL (should pass): $1"; fails=$((fails+1)); }; }
bad() { echo "$2" | ./check-coverage.sh >/dev/null 2>&1 && { echo "FAIL (should be rejected): $1"; fails=$((fails+1)); }; }

ok  "every file above 80, metrics above 95" \
  "$( { file app/metrics/_impl.py 100 100 20 20; file app/storage/_impl.py 100 85 0 0; } | report)"
bad "one file below 80 %" \
  "$( { file app/metrics/_impl.py 100 100 0 0; file app/storage/_impl.py 100 79 0 0; } | report)"
ok  "exactly 80 % passes" \
  "$( { file app/storage/_impl.py 100 80 0 0; } | report)"
bad "branches count: lines 100 % but branches drag a file below 80 %" \
  "$( { file app/storage/_impl.py 50 50 50 10; } | report)"
bad "critical module below 95 % although each file is above 80 %" \
  "$( { file app/sanitize/_impl.py 100 90 0 0; file app/sanitize/__init__.py 100 90 0 0; } | report)"
ok  "critical module at 95 %" \
  "$( { file app/budget/_impl.py 100 95 0 0; } | report)"
bad "llm is critical" \
  "$( { file app/llm/_impl.py 100 94 0 0; } | report)"
ok  "a non-critical module may sit at 80 %" \
  "$( { file app/pipeline/_impl.py 100 80 0 0; } | report)"
ok  "file without statements is ignored" \
  "$( { file app/pipeline/__init__.py 0 0 0 0; } | report)"
bad "empty report is an error, not a pass" '{"files": {}}'
bad "garbage input" 'not json'

[[ $fails -eq 0 ]] && echo "test-check-coverage: all passed" || { echo "$fails failed"; exit 1; }
