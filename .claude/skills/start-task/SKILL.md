---
name: start-task
description: "Opens every session that asks for a change in the repository: finds or creates the GitHub issue, names the commit type and branch, shows a short title and description, offers a plan in plan mode, then implements, offers the pull request and starts the code-reviewer agent on the draft. Use at the start of a session when the user asks to add, fix, change, refactor, document or configure anything in the repo (\"pridaj\", \"oprav\", \"zmen\", \"implement\", \"add\", \"fix\", \"let's build\"). Do NOT use for questions, explanations, code reading, reviews, or when the session already works on a ticket and branch."
metadata:
  version: 1.0.0
---

# Start task

Takes a request that changes the repo from a sentence to a ticket, a branch, a plan, a draft pull request and its review. Follow [git](../../../docs/agents/git.md), [issue tracker](../../../docs/agents/issue-tracker.md) and [agentic development](../../../docs/agentic-development.md); this skill only sequences them.

Talk to the user in their language. Issue titles, bodies, branches and commits are English, like the rest of the repo.

## Critical

- Read the first user message before acting. When the skill is called as `/start-task <text>`, the text after the command is the request. If it asks for no change to the repo (question, explanation, review, reading), stop here and answer normally.
- Never edit files, create a branch or commit before the user has approved the plan (Step 5).
- Never create a second issue for work that already has one. Never guess in a doubtful match: ask.
- Never commit on `main`. Never merge the PR or mark it ready. Never force-push or bypass hooks.
- No acceptance criteria, no work: label the issue `needs-info` and stop.

## Step 1: Find or create the issue

1. Search open and closed issues for the same work: `gh issue list --state all --search "<2-3 keywords>" --json number,title,state,url --limit 10`. Try a second query with other keywords when the first finds nothing.
2. Decide:
   - **One clear match**: use it. Say: "Issue #N (open/closed): title, link". Read it with `gh issue view N --json number,title,body,labels,comments`.
   - **No match**: create it with `gh issue create --title "<title>" --body "<body>"`. The body is a short description plus acceptance criteria as a checklist (the workflow does not start without them). Say "Created #N: title, link".
   - **Unclear** (several close matches, a closed issue that may be a regression, a request that spans several issues): show the candidates with links and ask which one to use, or whether to create a new one.
3. If the request is too vague to write acceptance criteria, ask the user before creating the issue.

Already on a feature branch whose name carries an issue number? Read that issue and reuse it instead of searching.

## Step 2: Show the card

Show these four lines and nothing more:

- **Issue**: #N, link
- **Type**: one of `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`, with a few words why
- **Branch**: `<type>/<issue-number>-<slug>`, the slug in 2-5 words
- **Title**: the issue title. **Description**: 1-3 plain sentences on the problem.

## Step 3: Offer a plan

Ask one question: "Do you want to plan the implementation?" Wait for the answer.

- **Yes** → Step 4.
- **No** → ask whether to start straight away; on yes go to Step 5 with the plan being the issue's acceptance criteria.

## Step 4: Plan

Enter plan mode (load `EnterPlanMode` through ToolSearch if it is deferred) and plan the work against the issue, `GLOSSARY.md`, the ADRs of the area, [critical paths](../../../docs/agents/critical-paths.md) and [testing](../../../docs/agents/testing.md). Name the modules, critical paths and guardrail files you will touch. Exit plan mode with `ExitPlanMode`.

After exit, put a summary in the chat before asking for approval:

- 3-6 bullets, plain words, no file-level detail, what changes and what is tested
- a link to the plan file, using the path plan mode wrote to
- one question: approve the plan or change it

## Step 5: Implement

After approval:

1. `git fetch`, then branch from the latest main in a worktree: `git switch -c <branch> origin/main`. Skip if the session is already on that branch.
2. Implement in red-green slices with the `tdd` skill, one commit per slice, Conventional Commits with `Refs #N` ([git](../../../docs/agents/git.md)). Out of scope goes to a new issue (`needs-triage`), not into the diff. Keep a list of unclear points for the PR's Reviewer notes.
3. Run the checks that exist: `make test-scripts`, and `make lint test` once the Python skeleton has them. Never weaken a test, lint or coverage rule to get green.

## Step 6: Wrap up

Summarize in short bullets, plain words:

- **Done**: what changed, as results, not files
- **Checks**: what passed and what was not run
- **Before the PR**: what is still open (a failing check, a decision), or "nothing"

Before pushing run the checks again and read them to the last line; a draft PR is opened only when they are clean. If nothing blocks the PR, ask: "Create the pull request?" On yes push the branch (`git push -u origin <branch>`) and open a **draft** PR from `.github/pull_request_template.md` with the `pr` skill: evidence per acceptance criterion, a statement when a critical path or guardrail file is touched, and `Closes #N` at the end. Check that the title is a valid Conventional Commit header.

## Step 7: Review

Right after the draft PR is open, start the `code-reviewer` agent with the Agent tool (`subagent_type: "code-reviewer"`). Give it the PR number and the issue number, nothing else: it starts with an empty context, so the review is fresh ([agentic development](../../../docs/agentic-development.md#agents-claudeagents)). It posts the review with a `<!-- code-reviewer: <sha> -->` marker for the commit it reviewed.

- Put its findings in the chat as short bullets, **Blocking** first, then the **Notes**, and which acceptance criteria are not met or not shown.
- One review round only. Do not fix findings or mark the PR ready without the user. After the user agrees, fix only the **Blocking** findings, each with its evidence (a test that was red and is green, a command output), and push. The **Notes** are not fixed in this PR: offer them to the user as issues. Do not start the agent again unless the user asks for it.
- After the push, show the user what came after the review: `git diff <reviewed sha>..HEAD` (the sha is in the marker of the review), as a short list of files and what changed. That diff is what no agent has reviewed.
- Marking the PR ready and merging are the user's.

## Examples

**New request, no issue**
User says: "Add a trend point for each month to the metrics module."
Actions: search finds nothing → create issue with acceptance criteria → card (`feat`, `feat/12-monthly-trend-points`) → ask about planning → user says yes → plan mode → bullets + plan link → approval → branch, implement, checks → summary → ask about the PR → draft PR → `code-reviewer` subagent.
Result: draft PR that closes the issue, reviewed by the `code-reviewer` agent, with its findings in the chat.

**Request already has an issue**
User says: "Fix the duplicate reviews."
Actions: search finds open #31 "Duplicate reviews in cache" → "Issue #31 (open): link" → card with `fix/31-duplicate-reviews-in-cache` → continue as above.

**Pure question**
User says: "How does the sanitize module work?"
Actions: none from this skill, answer normally.

## Troubleshooting

- **`gh issue list` or `gh issue create` asks for permission**: they are not in the allow list of `.claude/settings.json`. The user approves each call, or adds them.
- **Commit refused on `main`**: the hook wants a branch. `git switch -c <branch>` and commit there.
- **Commit message rejected**: fix the header (type, 72 characters, imperative). Never use `--no-verify`.
- **The skill started in the middle of a ticket**: the session already has a branch and an issue. Skip to the step that matches where the work is.
