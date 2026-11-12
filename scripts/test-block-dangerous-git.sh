#!/usr/bin/env bash
# Tests of .claude/hooks/block-dangerous-git.sh. Run: scripts/test-block-dangerous-git.sh
set -uo pipefail
hook="$(cd "$(dirname "$0")/.." && pwd)/.claude/hooks/block-dangerous-git.sh"
command -v jq >/dev/null || { echo "jq is required"; exit 1; }
fails=0
run() { jq -n --arg c "$1" '{tool_input:{command:$c}}' | CLAUDE_PROJECT_DIR=/nonexistent "$hook" >/dev/null 2>&1; }
allow() { run "$1" || { echo "FAIL (should be allowed): $1"; fails=$((fails+1)); }; }
block() { run "$1" && { echo "FAIL (should be blocked): $1"; fails=$((fails+1)); }; }

allow "git status"
allow "git push -u origin feat/12-trend-points"
allow "git commit -m 'feat: x'"
allow "git -C /tmp/x log --oneline"
allow "gh pr create --draft --title 'feat: x'"
allow "gh pr view 3"
block "git push --force origin feat/x"
block "git push -fu origin feat/x"
block "git push --force-with-lease"
block "git push origin main"
block "git push origin HEAD:main"
block "git push origin :feat/x"
block "git push origin +feat/x"
block "git push --all"
block "git -C dir push -f"
block "git commit --no-verify -m x"
block "git commit -n -m x"
block "git push -n"
block "git -c core.hooksPath=/dev/null commit -m x"
block "git reset --hard HEAD~1"
block "git clean -fd"
block "git branch -D feat/x"
block "git checkout ."
block "gh pr merge 3"
block "gh -R example-org/review-analyzer pr merge 3"
block "gh repo delete x"
block "gh issue delete 3"
block "gh release delete v1"

if [[ $fails -eq 0 ]]; then echo "test-block-dangerous-git: all passed"; else echo "$fails failed"; exit 1; fi
