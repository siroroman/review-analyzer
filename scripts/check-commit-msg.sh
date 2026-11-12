#!/usr/bin/env bash
# Validates a commit message against Conventional Commits (rules: docs/agents/git.md).
# Usage: check-commit-msg.sh <message-file | ->   ("-" reads stdin, e.g. a PR title in CI)
set -euo pipefail

src="${1:--}"
if [[ "$src" == "-" ]]; then
  raw=$(cat)
else
  raw=$(cat "$src")
fi

# Git drops comment lines in its default cleanup mode; do the same.
msg=$(printf '%s\n' "$raw" | grep -v '^#' || true)
header=$(printf '%s\n' "$msg" | sed -n '/./{p;q;}')
second=$(printf '%s\n' "$msg" | sed -n '2p')

# Generated messages that never land on main as-is.
if [[ "$header" =~ ^(Merge\ |Revert\ \"|(fixup|squash|amend)!\ ) ]]; then
  exit 0
fi

types='feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert'
# Keep in sync with docs/agents/git.md (Commits, Scope). A new scope is added there in its own pull request.
scopes='places sources sanitize taxonomy classification metrics insights llm budget storage pipeline api worker web infra spec agents guardrails process'
pattern="^(${types})(\\(([a-z0-9]+(-[a-z0-9]+)*)\\))?!?: .+"

fail() {
  {
    echo "Commit message rejected: $1"
    echo
    echo "  Format:   <type>(<scope>)<!>: <description>"
    echo "  Types:    ${types//|/, }"
    echo "  Scopes:   ${scopes// /, } (optional)"
    echo "  Example:  feat(sanitize): strip hidden characters from reviews"
    echo "  Rules:    docs/agents/git.md"
    echo
    echo "  Your header: ${header:-<empty>}"
  } >&2
  exit 1
}

[[ -n "$header" ]] || fail "message is empty"
[[ "$header" =~ $pattern ]] || fail "header must match <type>(<scope>)<!>: <description>"
scope=${BASH_REMATCH[3]}
if [[ -n "$scope" ]]; then
  case " $scopes " in
    *" $scope "*) ;;
    *) fail "unknown scope '$scope'" ;;
  esac
fi
(( ${#header} <= 72 )) || fail "header is ${#header} characters, the limit is 72"
[[ "$header" != *. ]] || fail "description must not end with a period"
[[ -z "$second" ]] || fail "leave a blank line between the header and the body"
