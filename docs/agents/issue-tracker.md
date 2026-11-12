# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues in `siroroman/review-analyzer`. Use the `gh` CLI for all operations (installed: 2.87, so no `--add-sub-issue`; use the API forms below).

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --json number,title,body,labels,comments`.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with `--label` and `--state` filters.
- **Make an issue a sub-issue of a parent**: `gh api --method POST repos/siroroman/review-analyzer/issues/<parent>/sub_issues -F sub_issue_id=<child-db-id>` (database id: `gh api repos/siroroman/review-analyzer/issues/<n> --jq .id`). Fallback: `Part of #<parent>` at the top of the child body.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."` (agents do not close issues; the owner merges the PR with `Closes #N`).

## Blocking

Native issue dependencies: `gh api --method POST repos/siroroman/review-analyzer/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`. Fallback: a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is closed.

## Pull requests as a triage surface

**PRs as a request surface: no.**

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Read it as in **Read an issue** above.

## Project rules that sit on top

- One ticket = one session = one worktree = one branch = one PR ([git conventions](git.md), [agentic development](../agentic-development.md)).
- A ticket without acceptance criteria gets `needs-info`. Out of scope = a new issue with `needs-triage`.
