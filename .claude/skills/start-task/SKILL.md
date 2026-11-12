---
name: start-task
description: Start of a session that asks to change the repository (feature, fix, docs, config). Finds or creates the GitHub issue, proposes a branch, plans, implements after approval, opens a draft PR and starts the review. Not for questions or reading code.
---

# Start a task

Rules: `docs/agents/git.md`, `docs/agents/issue-tracker.md`, `docs/agentic-development.md`.

1. **Issue.** Find the issue (`gh issue view`) or, if none exists, draft one with acceptance criteria and ask before creating it. No criteria means label `needs-info` and stop.
2. **Branch.** Propose `<type>/<issue>-<slug>`, from the latest `main`, in a worktree. Never work on `main`.
3. **Plan.** Rewrite the criteria as a checklist, name the modules, critical paths and guardrail files you will touch, and show the plan. Wait for approval.
4. **Implement** with the `tdd` skill. Out of scope goes to a new issue (`needs-triage`). Keep a list of unclear points for the PR's Reviewer notes.
5. **PR.** Push the branch, open a **draft** PR from `.github/pull_request_template.md` with evidence per criterion and `Closes #N`.
6. **Review.** Launch the `code-reviewer` agent in a fresh session with only the PR and ticket numbers. Fix the blockers, push, show the owner `git diff <sha>..HEAD`.

The owner marks the PR ready and merges. Never merge, force-push or bypass hooks.
