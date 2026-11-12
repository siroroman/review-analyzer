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
expect false true  'frontend/src/App.tsx'
expect false true  'frontend/package.json'
expect true  true  '.github/workflows/tests.yml'
expect true  true  $'docs/a.md\napp/budget/_impl.py\nfrontend/src/a.tsx'
expect true  false $'docs/a.md\napp/budget/_impl.py'
# a markdown file inside code still is not under tests
expect false false 'app/README.md'
expect false false 'frontend/README.md'

[[ $fails -eq 0 ]] && echo "test-check-test-scope: all passed" || { echo "$fails failed"; exit 1; }
