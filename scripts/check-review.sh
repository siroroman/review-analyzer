#!/usr/bin/env bash
# Fails when a pull request that is not a draft has not passed review (rules: docs/agents/git.md, Enforcement).
# The `code-reviewer` agent posts a review that names the skills it used on a line `Skills: <list>` and ends with the
# last line `<!-- code-reviewer: <full sha> blocking=<n> -->`: the commit it reviewed and the number of blocking findings
# still open at that commit. The check looks at the LAST such review of a commit of the PR and passes only when it has
# `blocking=0`. So a review with findings keeps the check red until the fixes are pushed and the reviewer, in a fresh
# session, has verified them and reported `blocking=0`. A review of an earlier commit of the PR still counts when it is
# clean, so a push after a clean review needs no second round (the owner reads `git diff <sha>..HEAD`).
# What it cannot prove: that the session was fresh, that the named skills were really used, that the commits after the
# last review were reviewed. A dismissed or pending review does not count, and neither does one by a user who is not the
# owner, a member or a collaborator (the repo is public, anyone can post a comment review).
#   scripts/check-review.sh <head sha> <draft: true|false> <base sha>
# Reads the JSON list of reviews on stdin (gh api repos/<owner>/<repo>/pulls/<number>/reviews --paginate --slurp,
# flattened with `jq add`, because --paginate alone prints one list per page). Runs in a checkout with the full history
# (fetch-depth: 0): the marker commit must be found in it. Needs jq.
set -euo pipefail

sha=${1:-}
draft=${2:-}
base=${3:-}

[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo "check-review: '$sha' is not a full commit sha" >&2; exit 1; }
[[ "$base" =~ ^[0-9a-f]{40}$ ]] || { echo "check-review: '$base' is not a full base commit sha" >&2; exit 1; }
[[ "$draft" == "true" || "$draft" == "false" ]] || { echo "check-review: draft must be true or false, got '$draft'" >&2; exit 1; }

raw=$(cat)
# Always parsed, so a broken input fails on a draft too.
# One line per valid review, in the order GitHub lists them: "<sha> <blocking> <skills: yes|no>".
reviews=$(jq -r '
  if type != "array" then error("expected a list of reviews") else . end
  | .[]
  | select(type == "object"
      and (.state | IN("COMMENTED", "APPROVED", "CHANGES_REQUESTED"))
      and (.author_association | IN("OWNER", "MEMBER", "COLLABORATOR")))
  | (.body // "" | gsub("\r"; "") | sub("\\s+$"; "") | split("\n")) as $lines
  # Only the last line is the marker, so a review that quotes one in its text does not name a commit by accident.
  | ($lines[-1] // "" | sub("^\\s+"; "") | sub("\\s+$"; "")
      | capture("^<!--\\s*code-reviewer:\\s*(?<sha>[0-9a-f]{40})\\s+blocking=(?<n>[0-9]+)\\s*-->$")?) as $m
  | select($m != null)
  | "\($m.sha) \($m.n) \(if any($lines[]; test("^Skills: *[^ ]")) then "yes" else "no" end)"
' <<<"$raw") || { echo "check-review: the reviews are not a valid JSON list" >&2; exit 1; }

if [[ "$draft" == "true" ]]; then
  echo "Draft pull request, no review needed yet."
  exit 0
fi

last=""
while read -r reviewed blocking skills; do
  [[ -n "$reviewed" ]] || continue
  # An unknown commit makes git fail, which counts as not in the PR. A commit that the base branch has is not the PR's.
  if git merge-base --is-ancestor "$reviewed" "$sha" 2>/dev/null && ! git merge-base --is-ancestor "$reviewed" "$base" 2>/dev/null; then
    last="$reviewed $blocking $skills"
  fi
done <<<"$reviews"

if [[ -z "$last" ]]; then
  {
    echo "No code-reviewer review of a commit of this pull request (head ${sha:0:7})."
    echo
    echo "  Run the \`code-reviewer\` agent on this pull request in a fresh session. It posts a review with a"
    echo "  \`Skills:\` line that ends with <!-- code-reviewer: <the commit it reviewed> blocking=<n> -->."
    echo "  A check that ran before the review is run again from the Actions tab. Rules: docs/agents/git.md."
  } >&2
  exit 1
fi

read -r reviewed blocking skills <<<"$last"
if [[ "$skills" != "yes" ]]; then
  echo "The review of ${reviewed:0:7} has no \`Skills: <list>\` line: say which skills the reviewer used for each part of the diff (docs/agents/skills.md)." >&2
  exit 1
fi
if [[ "$blocking" != "0" ]]; then
  {
    echo "The last review (${reviewed:0:7}) still has $blocking blocking finding(s) open."
    echo
    echo "  Fix them, push, then run the \`code-reviewer\` agent again in a fresh session. It checks each finding and"
    echo "  reports blocking=0 when all are resolved. Rules: docs/agents/git.md."
  } >&2
  exit 1
fi
echo "Review passed: the code-reviewer reported no open blocking findings at ${reviewed:0:7} (head ${sha:0:7})."
