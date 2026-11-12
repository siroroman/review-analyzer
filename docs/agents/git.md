# Git conventions and rules

GitHub flow with Conventional Commits. Read this before creating a branch, a commit or a pull request.

## Flow

- `main` is always deployable and only changes through a merged pull request. Never commit to `main` directly.
- One ticket = one branch = one pull request. When sessions run in parallel, work in a worktree per ticket.
- A branch is short-lived and starts from the latest `main`. When `main` has moved, merge it into the branch (or rebase the branch before the first push).
- Delete the branch after the merge.

## Branches

`<type>/<issue-number>-<slug>`, with the commit types below. Omit the number when no issue exists. Slug: lowercase letters and digits joined by single hyphens.

- `feat/12-trend-points`
- `fix/31-duplicate-reviews-in-cache`
- `docs/git-conventions`

## Commits

```
<type>(<scope>)<!>: <description>

<body, optional>

<footer, optional>
```

- **Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
- **Scope** is optional and is one of these (lowercase, kebab-case):
  - code modules from the [specification](../specification.md#code-structure-deep-modules): `places`, `sources`, `sanitize`, `taxonomy`, `classification`, `metrics`, `insights`, `llm`, `budget`, `storage`, `pipeline`;
  - layers: `api`, `worker`, `web`, `infra` (Docker, Cloud Run, Terraform);
  - areas of the repository: `spec`, `agents`, `guardrails`, `process`.

  The type already says what kind of change it is, so `test`, `ci` and `build` are not scopes. A new scope is added here and to `scripts/check-commit-msg.sh` in its own PR.
- **Description:** imperative mood, no trailing period. The whole header is at most 72 characters.
- **Body:** explains why, not what. Separated from the header by a blank line.
- **Breaking change:** `!` after the type or scope, or a `BREAKING CHANGE:` footer.
- **Issue links:** `Refs #12` in commits, `Closes #12` in the PR body.
- **Trailers:** keep the `Co-Authored-By:` line that the tooling adds.
- Commit in small steps along the red-green slices (TDD). Every commit passes lint and tests.

## Pull requests

- The title is a valid Conventional Commit header. The merge commit on `main` takes it as its title.
- The body follows the template `.github/pull_request_template.md`: summary, acceptance criteria with evidence, tests, critical paths touched, guardrails touched, reviewer notes and `Closes #<issue>` at the end.
- A PR is opened as a **draft**. The owner marks it ready only after the `code-reviewer` agent has reviewed it in a fresh session and the checks are green ([agentic development](../agentic-development.md#agents-claudeagents)). One review round: fix the findings and push, no further review is needed.
- Merge with a **merge commit**, never squash or rebase. Every commit of the branch reaches `main`, so each one is a valid Conventional Commit (the `commit-msg` hook checks it). History on `main` is not linear.

## Keeping a PR branch up to date

The ruleset requires a branch to be up to date with `main` before merging (strict required status checks). A PR that is behind cannot be merged until the owner presses **Update branch**; the checks then run again on the result. An agent in the worktree runs `git pull` (never a force push) before its next push. GitHub does not resolve a conflict: merge `main` into the branch locally, fix it and push.

## Rules for agents

- Push only your own feature branch: `git push -u origin <branch>`. Never force-push and never push `main`.
- Never bypass the hooks with `--no-verify` or `-n` and never override `core.hooksPath`. If a message is rejected, fix the message. If a commit on `main` is refused, `git switch -c <branch>` and commit there.
- Never rewrite history that is already pushed.
- Do not merge a PR unless the owner asked for it. `gh pr merge`, `gh repo delete`, `gh issue delete` and `gh release delete` are blocked; `gh pr create` and `gh pr view` are not.
- Never put secrets in the repository: keys (Apify, OpenRouter, Anthropic, Langfuse, Google) go into `.env` (in `.gitignore`) and, in the cloud, into Secret Manager.

## Enforcement

| Rule | Where it is checked |
| --- | --- |
| Commit message format and scope | `commit-msg` hook (`.githooks/commit-msg` calls `scripts/check-commit-msg.sh`), tests `scripts/test-check-commit-msg.sh` |
| PR title format | CI `.github/workflows/pr-title.yml` calls `scripts/check-commit-msg.sh -` |
| Branch name `<type>/<issue>-<slug>` | CI `pr-title.yml` calls `scripts/check-branch-name.sh`, tests `scripts/test-check-branch-name.sh`; `dependabot/*` passes |
| No commit on `main` or `master` | `pre-commit` hook, the message says `git switch -c`; a detached HEAD (rebase) passes |
| No push to `main` or `master` from this machine | `pre-push` hook; before a push `make lint` and `make test` run when these targets exist; deleting a branch is not tried |
| A secret in the staged changes | `pre-commit` hook runs `gitleaks git --staged`, the value is redacted in the output; without an installed `gitleaks` nothing is committed (`brew install gitleaks`); a false positive goes to `.gitleaksignore` with the fingerprint |
| Destructive commands (force push including `-fu` and `--force-with-lease`, deleting or mirroring remote refs, push to `main`, `reset --hard`, `clean -f`, `branch -D`, `checkout .`), bypassing hooks (`--no-verify`, `-n`, `-c core.hooksPath`) and `gh pr merge`, `gh repo delete`, `gh issue delete`, `gh release delete` | Claude Code hook `.claude/hooks/block-dangerous-git.sh` in `.claude/settings.json`, tests `scripts/test-block-dangerous-git.sh`; needs `jq`, without it everything is blocked; it matches the command text, so a commit message quoting a blocked command is blocked too (reword it) |
| Merge commit, PR title as the merge commit title | repository setting (see below) |
| Branch protection on `main`, required checks, up-to-date branch | GitHub ruleset (see below) |
| Review before ready, critical paths, guardrail paths, PR body | CI checks described in [agentic development](../agentic-development.md#ci-checks); they arrive with the ticket "Agentic scaffolding" |

Turn the hooks on once per clone with `make setup` (it sets `git config core.hooksPath .githooks`, a relative path, so a worktree never runs hooks from another checkout, and checks `jq`, `gitleaks` and `gh`). The Claude Code hook needs no setup, it is in `.claude/settings.json`. Tests of all scripts: `make test-scripts`.

## Setup on GitHub (done by the owner)

It is not in the diff, so it is recorded here once set:

- [ ] Only **merge commits** allowed (squash and rebase off), the merge commit title = PR title, message = PR body, branches deleted after the merge.
- [ ] Ruleset for `main`: no direct commits or force pushes, deletion forbidden, required checks (`check-title`, later also tests, coverage and `review-posted`), **Require branches to be up to date before merging**. "Require linear history" stays off.
- [ ] Secret scanning and push protection on.
- [ ] A new check from a workflow is not required until the owner adds it to the ruleset.
