#!/usr/bin/env bash
# Tests of scripts/ca-bundle.sh. Run: scripts/test-ca-bundle.sh
set -uo pipefail
script="$(cd "$(dirname "$0")" && pwd)/ca-bundle.sh"
fails=0
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
touch "$tmp/system.pem" "$tmp/own.pem" "$tmp/certifi.pem"

expect() { # <name> <expected output> <env assignments...>
  local name=$1 want=$2 got
  shift 2
  got=$(env -i PATH="$PATH" "$@" "$script" 2>/dev/null)
  [[ "$got" == "$want" ]] || { echo "FAIL ($name): wanted '$want', got '$got'"; fails=$((fails + 1)); }
}

expect "macOS uses the system bundle" "$tmp/system.pem" CA_BUNDLE_OS=Darwin CA_BUNDLE_SYSTEM="$tmp/system.pem"
expect "a bundle already set wins" "$tmp/own.pem" CA_BUNDLE_OS=Darwin CA_BUNDLE_SYSTEM="$tmp/system.pem" SSL_CERT_FILE="$tmp/own.pem"
expect "other systems change nothing" "" CA_BUNDLE_OS=Linux CA_BUNDLE_SYSTEM="$tmp/system.pem"
expect "a missing system bundle falls back to certifi" "$tmp/certifi.pem" CA_BUNDLE_OS=Darwin CA_BUNDLE_SYSTEM="$tmp/none.pem" CA_BUNDLE_CERTIFI="$tmp/certifi.pem"
expect "nothing found prints nothing" "" CA_BUNDLE_OS=Darwin CA_BUNDLE_SYSTEM="$tmp/none.pem" CA_BUNDLE_CERTIFI=""

[[ $fails -eq 0 ]] && echo "test-ca-bundle: ok" || exit 1
