#!/usr/bin/env bash
# Prints the CA bundle `make run-api` should give Python as SSL_CERT_FILE, or nothing when none is needed.
# The Python from uv (python.org build) has no root certificates on macOS, so TLS to places.googleapis.com
# fails with CERTIFICATE_VERIFY_FAILED. Order: SSL_CERT_FILE already set, the system bundle, certifi.
# Test hooks: CA_BUNDLE_OS, CA_BUNDLE_SYSTEM, CA_BUNDLE_CERTIFI (set, even empty, replaces the lookup).
set -euo pipefail
if [[ -n "${SSL_CERT_FILE:-}" && -f "$SSL_CERT_FILE" ]]; then
  echo "$SSL_CERT_FILE"; exit 0
fi
[[ "${CA_BUNDLE_OS:-$(uname -s)}" == "Darwin" ]] || exit 0
system=${CA_BUNDLE_SYSTEM:-/etc/ssl/cert.pem}
if [[ -f "$system" ]]; then
  echo "$system"; exit 0
fi
if [[ -n "${CA_BUNDLE_CERTIFI+set}" ]]; then
  certifi=$CA_BUNDLE_CERTIFI
else
  certifi=$(uv run --frozen python -c 'import certifi; print(certifi.where())' 2>/dev/null || true)
fi
[[ -n "$certifi" && -f "$certifi" ]] && echo "$certifi"
exit 0
