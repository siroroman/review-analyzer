#!/usr/bin/env bash
# Tests of scripts/check-test-scope.sh. Run: scripts/test-check-test-scope.sh
set -uo pipefail
cd "$(dirname "$0")"
fails=0
# expect <"backend frontend" as true/false> <changed paths, newline separated>
expect() {
  local want="backend=$1 frontend=$2" got
  got=$(printf '%s' "$3" | ./check-test-scope.sh | tr '\n' ' ' | sed 's/ $//')
  [[ "$got" == "$want" ]] || { echo "FAIL: [$3] wanted '$want', got '$got'"; fails=$((fails+1)); }
}

expect false false ""
expect false false $'README.md\ndocs/specification.md\ndocs/adr/0001-x.md\nGLOSSARY.md'
expect false false $'CLAUDE.md\n.claude/skills/start-task/SKILL.md\n.github/pull_request_template.md'
expect false false $'scripts/check-review.sh\nMakefile'
expect true  false 'app/metrics/__init__.py'
expect true  false 'tests/metrics/test_average.py'
expect true  false 'pyproject.toml'
expect true  false 'importlinter.ini'
expect true  false '.coveragerc'
expect true  false 'uv.lock'
expect false true  'web/src/App.tsx'
expect false true  'web/package.json'
expect false false 'frontend/src/App.tsx'
expect false false '.github/workflows/tests.yml'
expect true  true  $'docs/a.md\napp/budget/_impl.py\nweb/src/a.tsx'
expect true  false $'docs/a.md\napp/budget/_impl.py'
# a markdown file inside code still is not under tests
expect false false 'app/README.md'
expect false false 'web/README.md'

# The real `git diff` step: base and head given as arguments, in a throwaway repository.
repo=$(mktemp -d); trap 'rm -rf "$repo"' EXIT
script=$PWD/check-test-scope.sh
git_in() { git -C "$repo" -c user.name=t -c user.email=t@t -c commit.gpgsign=false "$@"; }
git_in init -q -b main
mkdir -p "$repo/app/metrics" "$repo/docs" "$repo/web/src"
echo 'x = 1' > "$repo/app/metrics/_impl.py"; echo a > "$repo/docs/a.md"; echo b > "$repo/web/src/a.tsx"
git_in add -A; git_in commit -q -m base
base=$(git_in rev-parse HEAD)
# expect_range <backend> <frontend> <description>: scope of base..HEAD
expect_range() {
  local got; got=$(cd "$repo" && "$script" "$base" HEAD | tr '\n' ' ' | sed 's/ $//')
  [[ "$got" == "backend=$1 frontend=$2" ]] || { echo "FAIL: $3: wanted backend=$1 frontend=$2, got '$got'"; fails=$((fails+1)); }
}
echo changed > "$repo/docs/a.md"; git_in commit -qam docs
expect_range false false "docs-only commit"
# A moved file must count under its OLD path too (rename detection would list only the new one).
mkdir -p "$repo/attic"; git_in mv app/metrics/_impl.py attic/_impl.py; git_in commit -qm move
expect_range true false "code moved out of app/"
git_in reset -q --hard "$base"; mkdir -p "$repo/lib"; git_in mv web/src/a.tsx lib/a.tsx; git_in commit -qm move
expect_range false true "code moved out of web/"

# A diff that fails must fail the script: a filter that fails open would skip the tests of a code change.
if out=$(cd "$repo" && "$script" deadbeef cafebabe 2>/dev/null); then
  echo "FAIL: unknown revisions passed with: $out"; fails=$((fails+1))
fi
if out=$("$script" onlyone 2>/dev/null </dev/null); then
  echo "FAIL: one argument passed with: $out"; fails=$((fails+1))
fi

[[ $fails -eq 0 ]] && echo "test-check-test-scope: all passed" || { echo "$fails failed"; exit 1; }
