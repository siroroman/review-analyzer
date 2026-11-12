#!/usr/bin/env bash
# Tests of scripts/check-branch-name.sh. Run: scripts/test-check-branch-name.sh
set -uo pipefail
cd "$(dirname "$0")" || exit 1
fails=0
ok()  { ./check-branch-name.sh "$1" 2>/dev/null || { echo "FAIL (should pass): $1"; fails=$((fails+1)); }; }
bad() { ./check-branch-name.sh "$1" 2>/dev/null && { echo "FAIL (should be rejected): $1"; fails=$((fails+1)); }; }

ok  feat/12-trend-points
ok  fix/31-duplicate-reviews
ok  docs/git-conventions
ok  dependabot/pip/ruff-0.9
bad main
bad feature/12-x
bad feat/Trend-Points
bad feat/12_trend_points
bad feat/
bad feat/12--x
bad research/llm-eval

if [[ $fails -eq 0 ]]; then echo "test-check-branch-name: all passed"; else echo "$fails failed"; exit 1; fi
