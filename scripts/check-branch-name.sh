#!/usr/bin/env bash
# Validates a branch name as <type>/<issue-number>-<slug> or <type>/<slug> (rules: docs/agents/git.md, Branches).
# Usage: check-branch-name.sh <branch>     (CI passes the head branch of the pull request)
# Dependabot branches (dependabot/...) are named by GitHub and pass.
set -euo pipefail

branch=${1-}
[[ -n "$branch" ]] || { echo "usage: check-branch-name.sh <branch>" >&2; exit 1; }

[[ "$branch" == dependabot/* ]] && exit 0

types='feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert'
if [[ "$branch" =~ ^(${types})/([0-9]+-)?[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
  exit 0
fi

{
  echo "Branch name rejected: '$branch'"
  echo
  echo "  Format:   <type>/<issue-number>-<slug>   (the number is optional when no issue exists)"
  echo "  Types:    ${types//|/, }"
  echo "  Slug:     lowercase words and digits joined by single hyphens"
  echo "  Example:  fix/31-duplicate-reviews-in-cache"
  echo
  echo "  Rename it with: git branch -m <new-name>   Rules: docs/agents/git.md (Branches)"
} >&2
exit 1
