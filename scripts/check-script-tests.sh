#!/usr/bin/env bash
# Every scripts/check-*.sh has a test that CI runs (docs/agents/rules-enforcement.md).
# Usage: check-script-tests.sh [<repo-root>]
# Fails when scripts/check-X.sh has no scripts/test-check-X.sh, the test is not executable, or `make test-scripts`
# does not run it (a target line `scripts/test-check-X.sh` in the Makefile).
set -euo pipefail
root=${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
fail=0
shopt -s nullglob
checks=("$root"/scripts/check-*.sh)
[[ ${#checks[@]} -gt 0 ]] || { echo "check-script-tests: no scripts/check-*.sh in $root" >&2; exit 2; }
for c in "${checks[@]}"; do
  name=$(basename "$c")
  t="scripts/test-$name"
  if [[ ! -f "$root/$t" ]]; then
    echo "check-script-tests: $name has no $t" >&2; fail=1
  elif [[ ! -x "$root/$t" ]]; then
    echo "check-script-tests: $t is not executable" >&2; fail=1
  elif ! grep -Eq "^[[:space:]]+${t}[[:space:]]*$" "$root/Makefile" 2>/dev/null; then
    echo "check-script-tests: $t is not run by 'make test-scripts' (add it to the Makefile)" >&2; fail=1
  fi
done
[[ $fail -eq 0 ]] && echo "check-script-tests: ok" || exit 1
