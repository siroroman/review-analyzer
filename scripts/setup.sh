#!/usr/bin/env bash
# Once per clone: turns on the git hooks and checks the tools they need. Running it again changes nothing.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

git config core.hooksPath .githooks # relative, so a worktree never runs hooks from another checkout
chmod +x .githooks/* scripts/*.sh .claude/hooks/*.sh

missing=0
for tool in jq gitleaks gh shellcheck actionlint; do
  if ! command -v "$tool" >/dev/null; then
    echo "setup: '$tool' is missing (brew install $tool)" >&2
    missing=1
  fi
done
[[ $missing -eq 0 ]] || { echo "setup: hooks are on, but install the tools above or commits and agent commands will be refused." >&2; exit 1; }
echo "setup: git hooks on (core.hooksPath=.githooks), tools found."
