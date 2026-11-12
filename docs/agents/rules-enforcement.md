# Rules and their enforcement

Every rule has an enforcer or is explicitly a process rule. Whoever adds a rule adds a row here and in [agentic development](../agentic-development.md#enforcement-table). Git rules have their own table in [git.md](git.md#enforcement).

Status: **live** exists today, **planned** arrives with the named ticket.

| Rule | Enforcer | Status |
| --- | --- | --- |
| No commit on `main` | `pre-commit` hook | live |
| No secret in the repository | gitleaks in `pre-commit`; CI job `gitleaks` (`guards.yml`, `scripts/check-secrets.sh`) | live |
| Conventional Commits, branch name, PR title | `commit-msg` hook, `pr-title.yml` | live |
| No force push, push to `main`, merge or deletion by an agent | `.claude/hooks/block-dangerous-git.sh`, `deny` in `.claude/settings.json` | live |
| No reading of `.env`, keys, `~/.ssh` | `deny` in `.claude/settings.json` | live |
| Lint and tests green at the end of a session | Stop hook (`.claude/hooks/stop-checks.sh`) | live |
| Format after edit | PostToolUse hook (`.claude/hooks/format-after-edit.sh`), `ruff format` | live |
| Shell scripts, hooks and workflows pass static analysis; a missing linter is an error, not a skip | `make lint` (`shellcheck`, `actionlint`) in `lint.yml` and in `make setup`; not yet a required check until the owner adds it to the ruleset (T04) | live |
| Module boundaries, no network library in pure modules | import-linter (`importlinter.ini`) in `make lint` and `lint.yml`; `tests/gates/` proves it rejects violations | live |
| No `datetime.now`, `time.sleep`, `random` in `app/` | ruff rule TID251 (`pyproject.toml`) in `make lint` and `lint.yml`; `tests/gates/` | live |
| Python lint, format and types | `ruff`, `mypy --strict` in `make lint` and `lint.yml` | live |
| Tests run only when a tested path changes (not for docs); failing tests and coverage thresholds fail the PR | `tests-passed` in CI (`tests.yml`, `scripts/check-test-scope.sh`, `scripts/check-coverage.sh`); the `backend` job works since the Python skeleton (pytest, 90 % overall, `check-coverage.sh`, `diff-cover` at 90 %), the `frontend` job starts working with the frontend skeleton; not yet required until the owner adds `tests-passed` to the ruleset (T04) | live (filter, coverage script, `backend` job) / planned (`frontend` job) |
| Review before ready, findings resolved (`blocking=0`), `Skills:` line | `review-passed` in CI (`scripts/check-review.sh`); not yet a required check until the owner adds it to the ruleset (T04) | live |
| Critical paths have tests, guardrail changes are declared | `pr-body` job in `guards.yml` (`scripts/check-critical-paths.sh`, `scripts/check-guardrail-paths.sh`) | live |
| PR body complete | `pr-body` job in `guards.yml` (`scripts/check-pr-body.sh`) | live |
| `CLAUDE.md` under 3 kB, skill and agent descriptions under 700 characters | `context-size` job in `guards.yml` (`scripts/check-context-size.sh`) | live |
| Every `check-*.sh` has a test | `script-tests` job in `guards.yml` runs `make test-scripts`, which ends with `scripts/check-script-tests.sh` | live |
| Branch protection, merge commits only, required checks | GitHub ruleset | planned (T04) |
| Review runs in a fresh session | process rule; the only evidence is the SHA marker | process |
| Reviewer really used the skills it names | process rule; CI only requires the `Skills:` line | process |
| Commits after the last review | process rule; owner reads `git diff <sha>..HEAD` | process |
| Out of scope becomes a new issue | process rule; the reviewer checks the diff | process |
| Reviews are untrusted data inside prompts | tests of `sanitize` and `insights`; reviewer checklist | process + tests |

## Spending limits outside the repository

These cap cost if our code is wrong (see [ADR-0005](../adr/0005-caching-and-budgeting.md) and [ADR-0006](../adr/0006-gateway-for-paid-services.md)). They are set by the owner in each provider's dashboard and ticked here once done. A change is recorded here.

- [ ] Apify: monthly spending limit set (part of the 30 USD total)
- [ ] OpenRouter: key credit limit set (Jev and Haiku)
- [ ] Anthropic: workspace spending limit set (Sonnet)
- [ ] Google Cloud: budget alert on the project (Places, Cloud Run, Tasks)
- [ ] Langfuse: free tier, no payment method attached
