#!/usr/bin/env bash
# PreToolUse hook for Bash: blocks destructive git commands, hook bypasses and merges (rules: docs/agents/git.md).
# Pushing a feature branch stays allowed so agents can open pull requests.
# It matches the command text, so a commit message or PR body that quotes a blocked command is blocked too.
# Tests: scripts/test-block-dangerous-git.sh
# No `set -e`: grep exits 1 when nothing matches.
set -uo pipefail

block() {
  echo "BLOCKED: '$COMMAND' $1. The user has prevented you from doing this." >&2
  exit 2
}

# Fail closed: without jq the command cannot be inspected.
if ! command -v jq >/dev/null; then
  echo "BLOCKED: jq is required by .claude/hooks/block-dangerous-git.sh (brew install jq)." >&2
  exit 2
fi
COMMAND=$(jq -r '.tool_input.command // empty') || {
  echo "BLOCKED: .claude/hooks/block-dangerous-git.sh got input that is not valid JSON." >&2
  exit 2
}
[ -n "$COMMAND" ] || exit 0

# Drop options between `git` and the subcommand, so `git -C dir push -f` is seen as `git push -f`.
ARG="(\"[^\"]*\"|'[^']*'|[^ ]+)"
GIT=$COMMAND
while :; do
  NEXT=$(printf '%s' "$GIT" | sed -E \
    -e "s/git +(-C|-c) +$ARG/git/" \
    -e "s/git +--(git-dir|work-tree|namespace)(=| +)$ARG/git/" \
    -e 's/git +(--no-pager|-P|--no-optional-locks)( |$)/git\2/')
  [ "$NEXT" = "$GIT" ] && break
  GIT=$NEXT
done

check() { # reason, regex (on the command without options before the subcommand)
  if printf '%s' "$GIT" | grep -qE "$2"; then block "$1"; fi
}
check_raw() { # reason, regex (on the command as written, case-insensitive)
  if printf '%s' "$COMMAND" | grep -qiE "$2"; then block "$1"; fi
}

FORCE='(-[a-zA-Z]*f[a-zA-Z]*|--force[a-z-]*)' # -f, -fu, -uf, --force, --force-with-lease
DELETE='(-[a-zA-Z]*d[a-zA-Z]*|--del[a-z]*)'   # -d, -df, --del, --delete
END='( |$)'
SEG='[^;&|]*' # stay inside one command of a && / ; / | chain

# push: force, delete, whole-repo, and anything that lands on main or master.
check "force-pushes" "git push$SEG $FORCE$END"
check "deletes remote branches" "git push$SEG ($DELETE|--prune)$END"
check "pushes every ref" "git push$SEG --(all|mirror)$END"
check "force-pushes a refspec (+src)" "git push$SEG [\"']?\\+[^ ]"
check "deletes a remote branch (:dst)" "git push$SEG [\"']?:[^ ]"
check "pushes to main" "git push$SEG [\"']?([^ :]*:)?(refs/heads/)?(main|master)[\"']?$END"

# A push without a branch (or with HEAD) pushes the current branch: refuse it on main.
if printf '%s' "$GIT" | grep -qE "git push$END"; then
  BRANCH=$(git -C "${CLAUDE_PROJECT_DIR:-.}" branch --show-current 2>/dev/null)
  if [ "$BRANCH" = main ] || [ "$BRANCH" = master ]; then
    ARGS=$(printf '%s' "$GIT" | sed -E 's/.*git push//; s/[;&|].*//' | tr ' ' '\n' | grep -v -e '^-' -e '^$')
    if [ "$(printf '%s\n' "$ARGS" | grep -c .)" -lt 2 ] || printf '%s\n' "$ARGS" | grep -qx HEAD; then
      block "would push $BRANCH"
    fi
  fi
fi

# Hooks are the guardrail: no skipping them. -n is --no-verify on commit; on push it is --dry-run, blocked as well.
check "skips the git hooks" "git (commit|push)$SEG (-[a-zA-Z]*n[a-zA-Z]*|--no-v[a-z-]*)$END"
# `git -c core.hooksPath=...` is removed from $GIT above, so look at the command as written.
check_raw "overrides core.hooksPath" "git +($SEG )?(-c|--config-env)[= ]*[\"']?core\\.hookspath"

# Merging and deleting on GitHub is the user's. Opening and viewing pull requests stays allowed.
GH='(^|[^A-Za-z0-9_-])gh +([^;&|]* )?'
check_raw "merges a pull request, the user does that" "${GH}pr +merge$END"
check_raw "deletes a repository" "${GH}repo +delete$END"
check_raw "deletes an issue" "${GH}issue +delete$END"
check_raw "deletes a release" "${GH}release +delete$END"

# Everything else that destroys work.
check "hard-resets" "git reset$SEG --hard"
check "force-cleans" "git clean$SEG $FORCE$END"
check "force-deletes a branch" "git branch$SEG (-[a-zA-Z]*D[a-zA-Z]*|-[a-zA-Z]*(d[a-zA-Z]*f|f[a-zA-Z]*d)[a-zA-Z]*)$END"
check "force-deletes a branch" "git branch$SEG $DELETE$SEG $FORCE$END"
check "force-deletes a branch" "git branch$SEG $FORCE$SEG $DELETE$END"
check "discards all changes" "git (checkout|restore)$SEG \\.$END"

exit 0
