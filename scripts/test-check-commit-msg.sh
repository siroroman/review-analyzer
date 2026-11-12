#!/usr/bin/env bash
# Tests of scripts/check-commit-msg.sh. Run: scripts/test-check-commit-msg.sh
set -uo pipefail
cd "$(dirname "$0")" || exit 1
fails=0
ok()  { printf '%s' "$1" | ./check-commit-msg.sh - 2>/dev/null || { echo "FAIL (should pass): $1"; fails=$((fails+1)); }; }
bad() { printf '%s' "$1" | ./check-commit-msg.sh - 2>/dev/null && { echo "FAIL (should be rejected): $1"; fails=$((fails+1)); }; }

ok  "feat: add review pipeline"
ok  "feat(sanitize): strip hidden characters"
ok  "fix(llm)!: change the complete() signature"
ok  "docs(spec): describe deep modules"
ok  "chore(guardrails): add commit-msg hook"
ok  $'feat(metrics): add trend points\n\nWhy: dashboard needs monthly points.\n\nRefs #12'
ok  "Merge pull request #3 from example-org/feat/3-x"
ok  'Revert "feat: x"'
bad ""
bad "add review pipeline"
bad "Feat: add x"
bad "feat(Sanitize): add x"
bad "feat(unknown): add x"
bad "feat(ci): ci is a type, not a scope"
bad "feat: add x."
bad "feat:add x"
bad "feat: $(printf 'x%.0s' {1..70})"
bad $'feat: add x\nbody without blank line'

if [[ $fails -eq 0 ]]; then echo "test-check-commit-msg: all passed"; else echo "$fails failed"; exit 1; fi
