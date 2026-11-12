#!/usr/bin/env bash
# Tests of scripts/check-secrets.sh. Run: scripts/test-check-secrets.sh (needs gitleaks, like the pre-commit hook)
set -uo pipefail
script="$(cd "$(dirname "$0")" && pwd)/check-secrets.sh"
fails=0
command -v gitleaks >/dev/null || { echo "test-check-secrets: gitleaks is not installed (brew install gitleaks)"; exit 1; }

repo=$(mktemp -d)
trap 'rm -rf "$repo"' EXIT
cd "$repo" || exit 1
git init -q -b main
git config user.email t@example.com
git config user.name t
git config commit.gpgsign false
echo "hello" > a.txt; git add a.txt; git commit -q -m base
base=$(git rev-parse HEAD)

# A GitHub token shaped value, built here so that this file holds no secret
token="ghp_$(printf 'aB3dE5gH7jK9mN1pQ3rS5tU7vW9xY1zA3bC5' )"
echo "clean change" > b.txt; git add b.txt; git commit -q -m clean
clean=$(git rev-parse HEAD)
echo "GITHUB_TOKEN=$token" > leak.env; git add leak.env; git commit -q -m leak
leaked=$(git rev-parse HEAD)
git rm -q leak.env; git commit -q -m "remove the leak"
removed=$(git rev-parse HEAD)

"$script" "$base" "$clean"   >/dev/null 2>&1 || { echo "FAIL (clean commits should pass)"; fails=$((fails + 1)); }
"$script" "$base" "$leaked"  >/dev/null 2>&1 && { echo "FAIL (a secret in a commit should fail)"; fails=$((fails + 1)); }
"$script" "$base" "$removed" >/dev/null 2>&1 && { echo "FAIL (a secret removed again is still in history)"; fails=$((fails + 1)); }
"$script" "$leaked" "$removed" >/dev/null 2>&1 || { echo "FAIL (range after the leak commit is clean)"; fails=$((fails + 1)); }
"$script" "$base" >/dev/null 2>&1 && { echo "FAIL (one argument)"; fails=$((fails + 1)); }
PATH=/usr/bin:/bin "$script" "$base" "$clean" >/dev/null 2>&1 && { echo "FAIL (no gitleaks must fail)"; fails=$((fails + 1)); }

if [[ $fails -eq 0 ]]; then echo "test-check-secrets: all passed"; else echo "$fails failed"; exit 1; fi
