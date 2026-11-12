#!/usr/bin/env bash
# The PR body is complete (docs/agents/git.md, .github/pull_request_template.md).
# Usage: check-pr-body.sh <body-file>
# Fails when a section of the template is missing or empty, an acceptance criterion is still the template's
# placeholder, or there is no `Closes #N` / `Refs #N` line.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/pr-body-lib.sh
source "$here/pr-body-lib.sh"

[[ $# -eq 1 && -f "$1" ]] || { echo "usage: check-pr-body.sh <body-file>" >&2; exit 2; }
body=$1
fail=0
problem() { echo "check-pr-body: $1" >&2; fail=1; }

for section in "Summary" "Acceptance criteria" "Tests" "Critical paths touched" "Guardrails touched" "Reviewer notes"; do
  [[ -n "$(pr_section "$body" "$section")" ]] || problem "the section '## $section' is missing or empty (write \"none\" when nothing applies)"
done

criteria=$(pr_section "$body" "Acceptance criteria")
if [[ -n "$criteria" ]]; then
  grep -Eq '^[[:space:]]*[-*] \[[ xX]\]' <<<"$criteria" || problem "'## Acceptance criteria' has no checklist item"
  grep -Fq 'criterion: evidence' <<<"$criteria" && problem "'## Acceptance criteria' still has the template line 'criterion: evidence'"
  # Every item needs evidence after a colon ("No evidence = not met").
  while IFS= read -r line; do
    [[ "$line" =~ ^[[:space:]]*[-*]\ \[[\ xX]\]\ .+:[[:space:]]*[^[:space:]] ]] || problem "criterion without evidence (write 'criterion: evidence'): $line"
  done < <(grep -E '^[[:space:]]*[-*] \[[ xX]\]' <<<"$criteria")
fi

tr -d '\r' < "$body" | grep -Eiq '^(closes|refs) #[0-9]+[[:space:]]*$' || problem "no line 'Closes #N' or 'Refs #N'"

[[ $fail -eq 0 ]] && echo "check-pr-body: ok" || exit 1
