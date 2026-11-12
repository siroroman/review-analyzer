#!/usr/bin/env bash
# A change of a critical path comes with a change of its tests, and the PR names it (docs/agents/critical-paths.md).
# Usage: <changed paths> | check-critical-paths.sh <body-file> [<critical-paths.md>]
# For every row of the table whose source glob matches a changed path: some test glob of that row must match a changed
# path, and `## Critical paths touched` must name something other than "none".
# Exception: the PR body starts with `> **Warning:**` and a reason (only the missing tests are excused, not the naming).
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/pr-body-lib.sh
source "$here/pr-body-lib.sh"

[[ $# -ge 1 && $# -le 2 && -f "$1" ]] || { echo "usage: check-critical-paths.sh <body-file> [<critical-paths.md>] < paths" >&2; exit 2; }
body=$1
doc=${2:-$here/../docs/agents/critical-paths.md}
[[ -f "$doc" ]] || { echo "check-critical-paths: $doc not found" >&2; exit 2; }

changed=()
while IFS= read -r line || [[ -n "$line" ]]; do changed+=("$line"); done   # no mapfile: macOS ships bash 3.2

# globs <cell>: the backticked globs of one table cell, one per line
# shellcheck disable=SC2016  # backticks are the literal delimiters of a glob in the table
globs() { grep -o '`[^`]*`' <<<"$1" | tr -d '`'; }
matches_any() { # matches_any <cell>: a changed path matches one of the globs
  local g p
  while IFS= read -r g; do
    for p in ${changed[@]+"${changed[@]}"}; do
      # shellcheck disable=SC2053  # the glob on the right is meant as a pattern
      [[ -n "$p" && "$p" == $g ]] && return 0
    done
  done < <(globs "$1")
  return 1
}

rows=0
touched=()
unprotected=()
while IFS='|' read -r _ area src tests _; do
  src=${src# }; tests=${tests# }
  [[ "$src" == *'`'* && "$tests" == *'`'* ]] || continue   # only rows with both columns of globs
  rows=$((rows + 1))
  if matches_any "$src"; then
    touched+=("$area")
    matches_any "$tests" || unprotected+=("$area")
  fi
done < <(sed -n '/^| Area |/,/^$/p' "$doc")
[[ $rows -gt 0 ]] || { echo "check-critical-paths: no table rows found in $doc" >&2; exit 2; }

fail=0
if [[ ${#touched[@]} -gt 0 ]] && ! pr_section_declares "$body" "Critical paths touched"; then
  echo "check-critical-paths: the PR changes a critical path (${touched[*]}) but '## Critical paths touched' does not name it" >&2
  fail=1
fi
if [[ ${#unprotected[@]} -gt 0 ]] && ! pr_body_has_warning "$body"; then
  echo "check-critical-paths: no changed test for: ${unprotected[*]} (or start the PR body with '> **Warning:**' and a reason)" >&2
  fail=1
fi
[[ $fail -eq 0 ]] && echo "check-critical-paths: ok" || exit 1
