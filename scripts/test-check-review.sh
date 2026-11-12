#!/usr/bin/env bash
# Tests of scripts/check-review.sh. Run: scripts/test-check-review.sh
set -uo pipefail
script="$(cd "$(dirname "$0")" && pwd)/check-review.sh"
fails=0

# A throwaway repo: base <- other (a commit of main only) and base <- c1 <- c2 (the PR, head = c2).
repo=$(mktemp -d)
trap 'rm -rf "$repo"' EXIT
cd "$repo" || exit 1
git init -q -b main
git config user.email t@example.com
git config user.name t
git config commit.gpgsign false
commit() { git commit -q --allow-empty -m "$1"; git rev-parse HEAD; }
base=$(commit base)
git switch -q -c pr
c1=$(commit c1)
head=$(commit c2)
git switch -q main
main_only=$(commit main-only)
unknown=0123456789012345678901234567890123456789

# review <state> <association> <body> prints one review as JSON
review() { jq -n --arg s "$1" --arg a "$2" --arg b "$3" '{state: $s, author_association: $a, body: $b}'; }
# good <sha> <blocking> prints a well-formed body
good() { printf 'Findings.\nSkills: code-review, python-testing-patterns\n<!-- code-reviewer: %s blocking=%s -->' "$1" "$2"; }
# list <review>... prints a JSON list
list() { jq -s '.' <<<"$*"; }

ok()  { # ok <name> <draft> <json>
  "$script" "$head" "$2" "$base" <<<"$3" >/dev/null 2>&1 || { echo "FAIL (should pass): $1"; fails=$((fails + 1)); }
}
bad() { # bad <name> <draft> <json>
  "$script" "$head" "$2" "$base" <<<"$3" >/dev/null 2>&1 && { echo "FAIL (should be rejected): $1"; fails=$((fails + 1)); }
}

empty='[]'
ok  "draft, no review"                 true  "$empty"
bad "ready, no review"                 false "$empty"
ok  "clean review of the head"         false "$(list "$(review COMMENTED OWNER "$(good "$head" 0)")")"
ok  "clean review of an earlier commit" false "$(list "$(review COMMENTED OWNER "$(good "$c1" 0)")")"
ok  "approved state, collaborator"     false "$(list "$(review APPROVED COLLABORATOR "$(good "$head" 0)")")"
bad "blocking findings open"           false "$(list "$(review COMMENTED OWNER "$(good "$head" 2)")")"
ok  "findings, then a clean re-review" false "$(list "$(review COMMENTED OWNER "$(good "$c1" 2)")" "$(review COMMENTED OWNER "$(good "$head" 0)")")"
bad "clean review, then new findings"  false "$(list "$(review COMMENTED OWNER "$(good "$c1" 0)")" "$(review COMMENTED OWNER "$(good "$head" 1)")")"
bad "marker is not the last line"      false "$(list "$(review COMMENTED OWNER "$(good "$head" 0)"$'\nthanks')")"
ok  "marker with CRLF line endings"    false "$(list "$(review COMMENTED OWNER "$(good "$head" 0 | sed 's/$/\r/')")")"
ok  "trailing newline after marker"    false "$(list "$(review COMMENTED OWNER "$(good "$head" 0)"$'\n')")"
bad "no Skills line"                   false "$(list "$(review COMMENTED OWNER "$(printf 'Findings.\n<!-- code-reviewer: %s blocking=0 -->' "$head")")")"
bad "empty Skills line"                false "$(list "$(review COMMENTED OWNER "$(printf 'Skills:\n<!-- code-reviewer: %s blocking=0 -->' "$head")")")"
bad "marker without blocking count"    false "$(list "$(review COMMENTED OWNER "$(printf 'Skills: x\n<!-- code-reviewer: %s -->' "$head")")")"
bad "marker names a commit of main"    false "$(list "$(review COMMENTED OWNER "$(good "$main_only" 0)")")"
bad "marker names the base commit"     false "$(list "$(review COMMENTED OWNER "$(good "$base" 0)")")"
bad "marker names an unknown commit"   false "$(list "$(review COMMENTED OWNER "$(good "$unknown" 0)")")"
bad "reviewer is not a collaborator"   false "$(list "$(review COMMENTED NONE "$(good "$head" 0)")")"
bad "contributor review"               false "$(list "$(review COMMENTED CONTRIBUTOR "$(good "$head" 0)")")"
bad "dismissed review"                 false "$(list "$(review DISMISSED OWNER "$(good "$head" 0)")")"
bad "pending review"                   false "$(list "$(review PENDING OWNER "$(good "$head" 0)")")"
bad "review without a body"            false '[{"state":"COMMENTED","author_association":"OWNER","body":null}]'
bad "invalid JSON"                     false 'not json'
bad "invalid JSON on a draft"          true  'not json'
bad "JSON object, not a list"          false '{"state":"COMMENTED"}'

# Bad arguments
"$script" "abc" false "$base" <<<"$empty" >/dev/null 2>&1 && { echo "FAIL (short sha)"; fails=$((fails + 1)); }
"$script" "$head" maybe "$base" <<<"$empty" >/dev/null 2>&1 && { echo "FAIL (draft value)"; fails=$((fails + 1)); }
"$script" "$head" false "" <<<"$empty" >/dev/null 2>&1 && { echo "FAIL (no base)"; fails=$((fails + 1)); }

if [[ $fails -eq 0 ]]; then echo "test-check-review: all passed"; else echo "$fails failed"; exit 1; fi
