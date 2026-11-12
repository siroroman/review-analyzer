#!/usr/bin/env bash
# PostToolUse hook for Edit and Write: formats an edited Python file with ruff.
# It never blocks: a missing tool or a failing formatter is ignored, `make lint` is the check.
# Tests: scripts/test-format-after-edit.sh
set -uo pipefail

command -v jq >/dev/null || exit 0
FILE=$(jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
case "$FILE" in
  *.py) ;;
  *) exit 0 ;;
esac

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
uv run --frozen ruff format "$FILE" >/dev/null 2>&1 || true
exit 0
