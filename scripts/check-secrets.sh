#!/usr/bin/env bash
# No secret in the commits of a PR (gitleaks, default rules plus .gitleaks.toml if there is one).
# Usage: check-secrets.sh <base> <head>   scans the commits of base..head in the current repository
# gitleaks missing = failure, never a silent pass.
set -euo pipefail
[[ $# -eq 2 ]] || { echo "usage: check-secrets.sh <base> <head>" >&2; exit 2; }
command -v gitleaks >/dev/null || { echo "check-secrets: gitleaks is not installed (brew install gitleaks)" >&2; exit 1; }
gitleaks git --redact --verbose --no-banner --log-level warn --log-opts="$1..$2" .
echo "check-secrets: ok"
