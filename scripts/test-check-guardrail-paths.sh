#!/usr/bin/env bash
# Tests of scripts/check-guardrail-paths.sh. Run: scripts/test-check-guardrail-paths.sh
set -uo pipefail
script="$(cd "$(dirname "$0")" && pwd)/check-guardrail-paths.sh"
fails=0
dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT

cat > "$dir/cp.md" <<'DOC'
## Critical paths

```
not/a/guardrail/**
```

## Guardrail paths

```
.claude/**
.github/**
scripts/**
Makefile
CLAUDE.md
```
DOC
body() { printf '## Summary\n\nx\n\n## Guardrails touched\n\n<!-- hint -->\n%s\n' "$1" > "$dir/body.md"; }
ok()  { printf '%s\n' "$2" | "$script" "$dir/body.md" "$dir/cp.md" >/dev/null 2>&1 || { echo "FAIL (should pass): $1"; fails=$((fails + 1)); }; }
bad() { printf '%s\n' "$2" | "$script" "$dir/body.md" "$dir/cp.md" >/dev/null 2>&1 && { echo "FAIL (should be rejected): $1"; fails=$((fails + 1)); }; }

body "Stricter: new check. Looser: nothing."
ok  "guardrail changed and declared"      '.github/workflows/guards.yml'
ok  "declared, several files"             $'scripts/check-x.sh\nMakefile\nCLAUDE.md'
body "none"
ok  "no guardrail changed, says none"     $'app/metrics/a.py\ndocs/x.md'
bad "workflow changed, says none"         '.github/workflows/guards.yml'
bad "script changed, says none"           'scripts/check-x.sh'
bad "Makefile changed, says none"         'Makefile'
bad "nested claude file, says none"       '.claude/agents/code-reviewer.md'
bad "guardrail among other files"         $'docs/x.md\nCLAUDE.md'
body "None."
bad "none with a full stop"               'CLAUDE.md'
body ""
bad "section empty"                       'CLAUDE.md'
ok  "section empty, no guardrail"         'docs/x.md'
printf '## Summary\n\nx\n' > "$dir/body.md"
bad "section missing"                     'CLAUDE.md'
ok  "no paths at all"                     ''

# Broken inputs fail instead of passing silently
printf 'nothing\n' > "$dir/empty.md"
echo 'CLAUDE.md' | "$script" "$dir/body.md" "$dir/empty.md" >/dev/null 2>&1 && { echo "FAIL (no globs)"; fails=$((fails + 1)); }
body "x"
echo 'x' | "$script" "$dir/body.md" "$dir/missing.md" >/dev/null 2>&1 && { echo "FAIL (no doc)"; fails=$((fails + 1)); }
# The real list parses and covers this script
body "none"
echo 'scripts/check-guardrail-paths.sh' | "$script" "$dir/body.md" >/dev/null 2>&1 && { echo "FAIL (real list misses scripts/**)"; fails=$((fails + 1)); }

if [[ $fails -eq 0 ]]; then echo "test-check-guardrail-paths: all passed"; else echo "$fails failed"; exit 1; fi
