#!/usr/bin/env bash
# Tests of scripts/check-pr-body.sh. Run: scripts/test-check-pr-body.sh
set -uo pipefail
script="$(cd "$(dirname "$0")" && pwd)/check-pr-body.sh"
fails=0
dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT

# body <variant>: a complete body, with one thing broken per variant
body() {
  local drop=${1:-} s
  for s in "Summary:Adds the check." "Acceptance criteria:- [x] checks exist: scripts/check-pr-body.sh" "Tests:test-check-pr-body.sh" \
           "Critical paths touched:none" "Guardrails touched:Stricter: PR body is checked." "Reviewer notes:none"; do
    [[ "${s%%:*}" == "$drop" ]] && continue
    printf '## %s\n\n<!-- a hint -->\n\n%s\n\n' "${s%%:*}" "${s#*:}"
  done
  [[ "$drop" == closes ]] || printf 'Closes #5\n'
}
ok()  { "$script" "$2" >/dev/null 2>&1 || { echo "FAIL (should pass): $1"; fails=$((fails + 1)); }; }
bad() { "$script" "$2" >/dev/null 2>&1 && { echo "FAIL (should be rejected): $1"; fails=$((fails + 1)); }; }
file() { body "${1:-}" > "$dir/b.md"; echo "$dir/b.md"; }

ok  "complete body"                  "$(file)"
printf 'Refs #5\n' > "$dir/refs.md"; body closes > "$dir/r.md"; cat "$dir/refs.md" >> "$dir/r.md"
ok  "Refs instead of Closes"         "$dir/r.md"
body | sed 's/$/\r/' > "$dir/crlf.md"
ok  "CRLF line endings"              "$dir/crlf.md"
for s in "Summary" "Acceptance criteria" "Tests" "Critical paths touched" "Guardrails touched" "Reviewer notes"; do
  bad "missing section $s"           "$(file "$s")"
done
bad "no Closes line"                 "$(file closes)"
{ body; } | sed 's/^## Tests$/## Tests/; s/^test-check-pr-body.sh$//' > "$dir/empty.md"
bad "section with only a hint"       "$dir/empty.md"
body | sed 's/^- \[x\] .*/- [ ] criterion: evidence/' > "$dir/ph.md"
bad "template placeholder"           "$dir/ph.md"
body | sed 's/^- \[x\] .*/- [x] checks exist/' > "$dir/noev.md"
bad "criterion without evidence"     "$dir/noev.md"
body | sed 's/^- \[x\] .*/just prose/' > "$dir/nolist.md"
bad "no checklist item"              "$dir/nolist.md"
: > "$dir/blank.md"
bad "empty body"                     "$dir/blank.md"
bad "missing file"                   "$dir/nope.md"

if [[ $fails -eq 0 ]]; then echo "test-check-pr-body: all passed"; else echo "$fails failed"; exit 1; fi
