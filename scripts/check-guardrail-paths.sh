#!/usr/bin/env bash
# A change of a guardrail file is declared in the PR body (docs/agents/critical-paths.md, Guardrail paths).
# Usage: <changed paths> | check-guardrail-paths.sh <body-file> [<critical-paths.md>]
# Fails when a changed path matches a guardrail glob and `## Guardrails touched` is empty or says "none".
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/pr-body-lib.sh
source "$here/pr-body-lib.sh"

[[ $# -ge 1 && $# -le 2 && -f "$1" ]] || { echo "usage: check-guardrail-paths.sh <body-file> [<critical-paths.md>] < paths" >&2; exit 2; }
body=$1
doc=${2:-$here/../docs/agents/critical-paths.md}
[[ -f "$doc" ]] || { echo "check-guardrail-paths: $doc not found" >&2; exit 2; }

# The globs are the lines of the first fenced block after the heading "## Guardrail paths".
globs=()
while IFS= read -r line; do globs+=("$line"); done < <(awk '/^## Guardrail paths/ { h = 1 } h && /^```/ { if (f) exit; f = 1; next } h && f && NF { print }' "$doc")
[[ ${#globs[@]} -gt 0 ]] || { echo "check-guardrail-paths: no guardrail globs found in $doc" >&2; exit 2; }

hits=()
while IFS= read -r p || [[ -n "$p" ]]; do
  [[ -n "$p" ]] || continue
  for g in "${globs[@]}"; do
    # shellcheck disable=SC2053  # the glob on the right is meant as a pattern
    if [[ "$p" == $g ]]; then hits+=("$p"); break; fi
  done
done

if [[ ${#hits[@]} -gt 0 ]] && ! pr_section_declares "$body" "Guardrails touched"; then
  echo "check-guardrail-paths: the PR changes guardrail files (${hits[*]:0:5}) but '## Guardrails touched' does not say what got stricter and what looser" >&2
  exit 1
fi
echo "check-guardrail-paths: ok"
