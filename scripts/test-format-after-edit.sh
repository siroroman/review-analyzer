#!/usr/bin/env bash
# Tests of .claude/hooks/format-after-edit.sh. Run: scripts/test-format-after-edit.sh
set -uo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
hook="$root/.claude/hooks/format-after-edit.sh"
command -v jq >/dev/null || { echo "jq is required"; exit 1; }
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/bin"
# A fake uv that records its arguments; FAKE_UV_EXIT sets its exit code.
cat >"$tmp/bin/uv" <<'EOF'
#!/usr/bin/env bash
echo "$*" >>"$FAKE_UV_LOG"
exit "${FAKE_UV_EXIT:-0}"
EOF
chmod +x "$tmp/bin/uv"
fails=0

run() { # file_path, uv exit code; prints the hook's exit code
  : >"$tmp/uv.log"
  jq -n --arg f "$1" '{tool_input:{file_path:$f}}' |
    PATH="$tmp/bin:$PATH" FAKE_UV_LOG="$tmp/uv.log" FAKE_UV_EXIT="${2:-0}" CLAUDE_PROJECT_DIR="$tmp" "$hook" >/dev/null 2>&1
  echo $?
}
check() { # description, then the command that must succeed
  local desc=$1
  shift
  if ! "$@"; then echo "FAIL: $desc"; fails=$((fails + 1)); fi
}

code=$(run "$tmp/app/x.py")
check "python file: exit 0" [ "$code" = 0 ]
check "python file is formatted with ruff" grep -qx "run --frozen ruff format $tmp/app/x.py" "$tmp/uv.log"

code=$(run "$tmp/README.md")
check "non-python file: exit 0" [ "$code" = 0 ]
check "non-python file is left alone" [ ! -s "$tmp/uv.log" ]

code=$(run "$tmp/app/x.py" 1)
check "a failing formatter never blocks" [ "$code" = 0 ]

code=$(echo 'not json' | PATH="$tmp/bin:$PATH" FAKE_UV_LOG="$tmp/uv.log" CLAUDE_PROJECT_DIR="$tmp" "$hook" >/dev/null 2>&1; echo $?)
check "invalid input never blocks" [ "$code" = 0 ]

code=$(echo '{"tool_input":{}}' | PATH="$tmp/bin:$PATH" FAKE_UV_LOG="$tmp/uv.log" CLAUDE_PROJECT_DIR="$tmp" "$hook" >/dev/null 2>&1; echo $?)
check "no file path never blocks" [ "$code" = 0 ]

if [[ $fails -eq 0 ]]; then echo "test-format-after-edit: all passed"; else echo "$fails failed"; exit 1; fi
