#!/usr/bin/env bash
# Tests of scripts/check-script-tests.sh. Run: scripts/test-check-script-tests.sh
set -uo pipefail
script="$(cd "$(dirname "$0")" && pwd)/check-script-tests.sh"
fails=0
dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT

fresh() { # a repo with check-a.sh and a test that the Makefile runs
  rm -rf "$dir/r"; mkdir -p "$dir/r/scripts"
  touch "$dir/r/scripts/check-a.sh" "$dir/r/scripts/test-check-a.sh"
  chmod +x "$dir/r/scripts/test-check-a.sh"
  printf 'test-scripts:\n\tscripts/test-check-a.sh\n' > "$dir/r/Makefile"
}
ok()  { "$script" "$dir/r" >/dev/null 2>&1 || { echo "FAIL (should pass): $1"; fails=$((fails + 1)); }; }
bad() { "$script" "$dir/r" >/dev/null 2>&1 && { echo "FAIL (should be rejected): $1"; fails=$((fails + 1)); }; }

fresh;                                         ok  "check with test, run by make"
touch "$dir/r/scripts/check-b.sh";             bad "second check without a test"
touch "$dir/r/scripts/test-check-b.sh"; chmod +x "$dir/r/scripts/test-check-b.sh"
bad "test not in the Makefile"
printf '\tscripts/test-check-b.sh\n' >> "$dir/r/Makefile"; ok "test added to the Makefile"
chmod -x "$dir/r/scripts/test-check-b.sh";     bad "test not executable"
fresh; printf '# scripts/test-check-a.sh\n' > "$dir/r/Makefile"; bad "test only named in a comment"
fresh; printf '\tscripts/test-check-a.sh.bak\n' > "$dir/r/Makefile"; bad "Makefile names a different file"
fresh; rm "$dir/r/Makefile";                   bad "no Makefile"
fresh; rm "$dir/r/scripts/check-a.sh";         bad "no checks at all"
fresh; rm "$dir/r/scripts/test-check-a.sh";    bad "test missing"
# This repository passes
"$script" >/dev/null 2>&1 || { echo "FAIL (this repository)"; fails=$((fails + 1)); }

if [[ $fails -eq 0 ]]; then echo "test-check-script-tests: all passed"; else echo "$fails failed"; exit 1; fi
