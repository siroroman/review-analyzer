#!/usr/bin/env bash
# Tests of scripts/check-context-size.sh. Run: scripts/test-check-context-size.sh
set -uo pipefail
script="$(cd "$(dirname "$0")" && pwd)/check-context-size.sh"
fails=0
dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT

fresh() { rm -rf "$dir/r"; mkdir -p "$dir/r/.claude/skills/s" "$dir/r/.claude/agents"; head -c "${1:-100}" /dev/zero | tr '\0' a > "$dir/r/CLAUDE.md"; }
text() { head -c "$1" /dev/zero | tr '\0' d; }
skill() { printf -- '---\nname: s\ndescription: %s\n---\nbody\n' "$1" > "$dir/r/.claude/skills/s/SKILL.md"; }
agent() { printf -- '---\nname: a\ndescription: %s\ntools: Read\n---\nbody\n' "$1" > "$dir/r/.claude/agents/a.md"; }
ok()  { "$script" "$dir/r" >/dev/null 2>&1 || { echo "FAIL (should pass): $1"; fails=$((fails + 1)); }; }
bad() { "$script" "$dir/r" >/dev/null 2>&1 && { echo "FAIL (should be rejected): $1"; fails=$((fails + 1)); }; }

fresh 100; skill "short"; agent "short"
ok  "small context"
fresh 2999
ok  "CLAUDE.md just under 3000 bytes"
fresh 3000
bad "CLAUDE.md at 3000 bytes"
fresh 100; skill "$(text 699)"
ok  "skill description of 699"
skill "$(text 700)"
bad "skill description of 700"
fresh 100; skill "short"; agent "$(text 700)"
bad "agent description of 700"
agent "$(text 699)"
ok  "agent description of 699"
printf -- '---\nname: s\ndescription: >\n  %s\n  %s\n---\n' "$(text 400)" "$(text 400)" > "$dir/r/.claude/skills/s/SKILL.md"
bad "folded description of 801"
printf -- '---\nname: s\ndescription: >\n  %s\n  %s\n---\n' "$(text 100)" "$(text 100)" > "$dir/r/.claude/skills/s/SKILL.md"
ok  "folded description of 201"
printf -- '---\nname: s\n---\nbody\n' > "$dir/r/.claude/skills/s/SKILL.md"
bad "skill without a description"
skill "short"
rm "$dir/r/CLAUDE.md"
bad "CLAUDE.md missing"
# A "description:" in the body is not the front matter's
fresh 100; agent "short"
printf -- '---\nname: s\ndescription: ok\n---\ndescription: %s\n' "$(text 800)" > "$dir/r/.claude/skills/s/SKILL.md"
ok  "description-like line in the body"

if [[ $fails -eq 0 ]]; then echo "test-check-context-size: all passed"; else echo "$fails failed"; exit 1; fi
