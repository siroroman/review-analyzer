#!/usr/bin/env bash
# Tests of scripts/check-critical-paths.sh. Run: scripts/test-check-critical-paths.sh
set -uo pipefail
script="$(cd "$(dirname "$0")" && pwd)/check-critical-paths.sh"
fails=0
dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT

cat > "$dir/cp.md" <<'DOC'
| Area | Source globs | Test globs | What goes wrong |
| --- | --- | --- | --- |
| Metrics | `app/metrics/**` | `tests/metrics/**` | wrong average |
| Budget | `app/budget/**`, `app/llm/**` | `tests/budget/**`, `tests/llm/**` | over the cap |

## Guardrail paths
DOC
body() { # body <critical-paths-section> [first line]
  printf '%s\n## Summary\n\nx\n\n## Critical paths touched\n\n<!-- hint -->\n%s\n\n## Guardrails touched\n\nnone\n' "${2:-}" "$1" > "$dir/body.md"
}
ok()  { # ok <name> <paths>
  printf '%s\n' "$2" | "$script" "$dir/body.md" "$dir/cp.md" >/dev/null 2>&1 || { echo "FAIL (should pass): $1"; fails=$((fails + 1)); }
}
bad() {
  printf '%s\n' "$2" | "$script" "$dir/body.md" "$dir/cp.md" >/dev/null 2>&1 && { echo "FAIL (should be rejected): $1"; fails=$((fails + 1)); }
}

body "Metrics: test_average covers the new case"
ok  "source and test changed, area named"     $'app/metrics/average.py\ntests/metrics/test_average.py'
ok  "no critical path changed"                $'docs/x.md\nREADME.md'
ok  "only tests changed"                      'tests/metrics/test_average.py'
bad "source changed without tests"            'app/metrics/average.py'
bad "test of another area does not count"     $'app/metrics/average.py\ntests/budget/test_x.py'
body "Budget: reserve is tested"
ok  "second source glob of a row, its test"   $'app/llm/client.py\ntests/budget/test_reserve.py'
bad "second source glob, no test"             'app/llm/client.py'
body "none"
bad "area not named (none)"                   $'app/metrics/a.py\ntests/metrics/t.py'
body ""
bad "area not named (empty section)"          $'app/metrics/a.py\ntests/metrics/t.py'
body "Metrics: no new tests, only a comment" '> **Warning:** comment-only change, no behaviour'
ok  "warning excuses missing tests"           'app/metrics/a.py'
body "none" '> **Warning:** comment-only change'
bad "warning does not excuse a missing name"  'app/metrics/a.py'
body "Metrics: x" '> **Warning:**'
bad "warning without a reason"                'app/metrics/a.py'
ok  "no paths at all"                         ''

# Broken inputs fail instead of passing silently
printf 'no table here\n' > "$dir/empty.md"
echo 'app/metrics/a.py' | "$script" "$dir/body.md" "$dir/empty.md" >/dev/null 2>&1 && { echo "FAIL (no table)"; fails=$((fails + 1)); }
echo 'x' | "$script" "$dir/missing.md" "$dir/cp.md" >/dev/null 2>&1 && { echo "FAIL (no body file)"; fails=$((fails + 1)); }
# The real table parses
echo 'docs/x.md' | "$script" "$dir/body.md" >/dev/null 2>&1 || { echo "FAIL (real critical-paths.md)"; fails=$((fails + 1)); }

if [[ $fails -eq 0 ]]; then echo "test-check-critical-paths: all passed"; else echo "$fails failed"; exit 1; fi
