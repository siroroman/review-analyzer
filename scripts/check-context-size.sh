#!/usr/bin/env bash
# Keeps the context of every session small (docs/agentic-development.md, Context and token management).
# Usage: check-context-size.sh [<repo-root>]
# Fails when CLAUDE.md is 3 kB (3000 bytes) or more, or the description of a skill (.claude/skills/*/SKILL.md) or
# an agent (.claude/agents/*.md) is 700 characters or more, or a description is missing.
set -euo pipefail
root=${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
fail=0
problem() { echo "check-context-size: $1" >&2; fail=1; }

if [[ -f "$root/CLAUDE.md" ]]; then
  size=$(wc -c < "$root/CLAUDE.md" | tr -d ' ')
  [[ $size -lt 3000 ]] || problem "CLAUDE.md is $size bytes, the limit is under 3000"
else
  problem "CLAUDE.md not found"
fi

# description <file>: the description of the front matter. Indented lines after it continue it, whether it is a
# folded or literal block (`>` / `|`), a plain scalar or a quoted one; they are joined with spaces.
description() {
  awk '
    NR == 1 { if ($0 != "---") exit; next }
    /^---[[:space:]]*$/ { exit }
    /^description:/ { sub(/^description:[[:space:]]*/, ""); inside = 1; found = 1; if ($0 !~ /^[>|][-+]?$/) d = $0; next }
    inside && /^[[:space:]]+[^[:space:]]/ { sub(/^[[:space:]]+/, ""); d = d (d == "" ? "" : " ") $0; next }
    { inside = 0 }
    END { if (found) printf "%s", d }
  ' "$1" | tr -d '\r'
}

shopt -s nullglob
for f in "$root"/.claude/skills/*/SKILL.md "$root"/.claude/agents/*.md; do
  d=$(description "$f")
  rel=${f#"$root"/}
  if [[ -z "$d" ]]; then
    problem "$rel has no description in its front matter"
  elif [[ ${#d} -ge 700 ]]; then
    problem "$rel: the description is ${#d} characters, the limit is under 700"
  fi
done

[[ $fail -eq 0 ]] && echo "check-context-size: ok" || exit 1
