# Rules and their enforcement

Every rule has an enforcer or is explicitly a process rule. Whoever adds a rule adds a row here and in [agentic development](../agentic-development.md#enforcement-table). Git rules have their own table in [git.md](git.md#enforcement).

Status: **live** exists today, **planned** arrives with the named ticket.

| Rule | Enforcer | Status |
| --- | --- | --- |
| No commit on `main` | `pre-commit` hook | live |
| No secret in the repository | gitleaks in `pre-commit`; CI job | live / planned (T03) |
| Conventional Commits, branch name, PR title | `commit-msg` hook, `pr-title.yml` | live |
| No force push, push to `main`, merge or deletion by an agent | `.claude/hooks/block-dangerous-git.sh`, `deny` in `.claude/settings.json` | live |
| No reading of `.env`, keys, `~/.ssh` | `deny` in `.claude/settings.json` | live |
| Lint and tests green at the end of a session | Stop hook | planned (T01, needs T02 targets) |
| Format after edit | PostToolUse hook, `ruff format` | planned (T01, needs T02) |
| Shell scripts, hooks and workflows pass static analysis; a missing linter is an error, not a skip | `make lint` (`shellcheck`, `actionlint`) in `lint.yml` and in `make setup`; not yet a required check until the owner adds it to the ruleset (T04) | live |
| Module boundaries, no network library in pure modules | import-linter in CI | planned (T02) |
| No `datetime.now`, `time.sleep`, `random` in `app/` | ruff rule in CI | planned (T02) |
| Tests run only when a tested path changes (not for docs); failing tests and coverage thresholds fail the PR | `tests-passed` in CI (`tests.yml`, `scripts/check-test-scope.sh`, `scripts/check-coverage.sh`); the jobs start working with the Python and frontend skeletons; not yet required until the owner adds `tests-passed` to the ruleset (T04) | live (filter, coverage script) / planned (T02, jobs) |
| Review before ready, findings resolved (`blocking=0`), `Skills:` line | `review-passed` in CI (`scripts/check-review.sh`); not yet a required check until the owner adds it to the ruleset (T04) | live |
| Critical paths have tests, guardrail changes are declared | CI checks | planned (T03) |
| PR body complete | CI check | planned (T03) |
| `CLAUDE.md` under 3 kB, skill and agent descriptions under 700 characters | CI context-size check | planned (T03) |
| Every `check-*.sh` has a test | `make test-scripts` in CI | planned (T03) |
| Branch protection, merge commits only, required checks | GitHub ruleset | planned (T04) |
| Review runs in a fresh session | process rule; the only evidence is the SHA marker | process |
| Reviewer really used the skills it names | process rule; CI only requires the `Skills:` line | process |
| Commits after the last review | process rule; owner reads `git diff <sha>..HEAD` | process |
| Out of scope becomes a new issue | process rule; the reviewer checks the diff | process |
| Reviews are untrusted data inside prompts | tests of `sanitize` and `insights`; reviewer checklist | process + tests |

## Spending limits outside the repository

These cap cost if our code is wrong (see [ADR-0005](../adr/0005-caching-and-budgeting.md)). They are set by the owner in each provider's dashboard and ticked here once done. A change is recorded here.

- [ ] Apify: monthly spending limit set (part of the 30 USD total)
- [ ] OpenRouter: key credit limit set (Jev and Haiku)
- [ ] Anthropic: workspace spending limit set (Sonnet)
- [ ] Google Cloud: budget alert on the project (Places, Cloud Run, Tasks)
- [ ] Langfuse: free tier, no payment method attached
