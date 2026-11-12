#!/usr/bin/env bash
# Tests of .claude/hooks/stop-checks.sh. Run: scripts/test-stop-checks.sh
set -uo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
hook="$root/.claude/hooks/stop-checks.sh"
command -v jq >/dev/null || { echo "jq is required"; exit 1; }
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/bin"
# A fake make that records its arguments; FAKE_MAKE_EXIT sets its exit code.
cat >"$tmp/bin/make" <<'EOF'
#!/usr/bin/env bash
echo "$*" >>"$FAKE_MAKE_LOG"
echo "fake make output"
exit "${FAKE_MAKE_EXIT:-0}"
EOF
chmod +x "$tmp/bin/make"
fails=0

git init -q --bare -b main "$tmp/origin.git"
git clone -q "$tmp/origin.git" "$tmp/work" 2>/dev/null
cd "$tmp/work" || exit 1
git config user.email t@example.com
git config user.name test
mkdir app
echo "x = 1" >app/a.py
echo "docs" >README.md
git add -A && git commit -q -m init && git push -q origin HEAD:main
git fetch -q origin
reset() { git reset -q --hard origin/main && git clean -qfd; }

run() { # stdin JSON, make exit code; prints the hook's exit code, stderr goes to $tmp/err
  : >"$tmp/make.log"
  local input=${1:-'{}'}
  echo "$input" | PATH="$tmp/bin:$PATH" FAKE_MAKE_LOG="$tmp/make.log" FAKE_MAKE_EXIT="${2:-0}" \
    CLAUDE_PROJECT_DIR="$tmp/work" "$hook" >/dev/null 2>"$tmp/err"
  echo $?
}
check() { # description, then the command that must succeed
  local desc=$1
  shift
  if ! "$@"; then echo "FAIL: $desc"; fails=$((fails + 1)); fi
}

reset
code=$(run)
check "nothing changed: exit 0" [ "$code" = 0 ]
check "nothing changed: no checks" [ ! -s "$tmp/make.log" ]

echo "# docs" >>README.md
code=$(run)
check "only docs changed: exit 0" [ "$code" = 0 ]
check "only docs changed: no checks" [ ! -s "$tmp/make.log" ]

reset
echo "y = 2" >>app/a.py
code=$(run)
check "uncommitted python change: checks pass, exit 0" [ "$code" = 0 ]
check "uncommitted python change runs make lint test test-scripts" grep -qx "lint test test-scripts" "$tmp/make.log"

code=$(run '{}' 1)
check "failing checks: exit 2" [ "$code" = 2 ]
check "failing checks: the agent sees the output" grep -q "fake make output" "$tmp/err"

code=$(run '{"stop_hook_active":true}' 1)
check "second stop does not loop: exit 0" [ "$code" = 0 ]
check "second stop does not run checks again" [ ! -s "$tmp/make.log" ]

reset
echo "z = 3" >>app/a.py
git commit -q -am "feat: z"
code=$(run)
check "committed python change since origin/main: exit 0" [ "$code" = 0 ]
check "committed python change runs make lint test test-scripts" grep -qx "lint test test-scripts" "$tmp/make.log"

reset
echo "# dep" >>pyproject.toml
code=$(run)
check "pyproject.toml change runs checks" grep -qx "lint test test-scripts" "$tmp/make.log"

# make lint also covers shell scripts, git hooks and workflows, and test-scripts covers the scripts.
for changed in scripts/check-x.sh .githooks/pre-commit .claude/hooks/h.sh .github/workflows/ci.yml Makefile; do
  reset
  mkdir -p "$(dirname "$changed")"
  echo "# change" >>"$changed"
  code=$(run '{}' 1)
  check "$changed change runs checks and a failure is fed back" [ "$code" = 2 ]
  check "$changed change runs make lint test test-scripts" grep -qx "lint test test-scripts" "$tmp/make.log"
done

if [[ $fails -eq 0 ]]; then echo "test-stop-checks: all passed"; else echo "$fails failed"; exit 1; fi
