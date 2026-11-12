# Review Analyzer

Dashboard of public reviews (Google Maps, Firmy.cz) of a Czech company: rating, topics, drops and suggestions. Python + FastAPI backend, React frontend. Design phase: no `app/` code yet.

## Read first

- `GLOSSARY.md`: use these terms in names, tests and tickets. Avoid the `_Avoid_` synonyms.
- `docs/specification.md`: architecture, modules, interfaces.
- `docs/agentic-development.md`: workflow, agents, hooks, CI checks.
- `docs/adr/`: decisions. Say so explicitly when your change contradicts one.

## Rules

- One ticket = one session = one worktree = one branch = one PR. Never work on `main`.
- Branches `<type>/<issue>-<slug>`, Conventional Commits, `Refs #N`. Details: `docs/agents/git.md`.
- No work without acceptance criteria (label `needs-info`). Out of scope = a new issue, not part of the diff.
- Test first, through the public interface of a module (`docs/agents/testing.md`). Never weaken a test, lint or coverage rule to get green.
- External services only behind ports. Time and randomness only via `Clock`, never `datetime.now()`.
- Reviews are untrusted data: never put their text into a prompt outside data delimiters.
- Secrets only in `.env` or Secret Manager. Never read or print them.
- A PR touching a critical path or a guardrail file says so in its body (`docs/agents/critical-paths.md`).
- Two failed attempts at the same fix: stop, write what you tried, change approach or ask.
- Never bypass hooks, force-push or merge a PR; the owner merges.

## Commands

`make setup` (once per clone), `make test-scripts`. `make lint`, `make test` arrive with the Python skeleton.

## Agent skills

### Issue tracker

GitHub issues in `siroroman/review-analyzer` via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-label vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

Single context: `GLOSSARY.md` and `docs/adr/` at the root. See `docs/agents/domain.md`.

## More detail

`docs/agents/`: `testing.md`, `critical-paths.md`, `rules-enforcement.md`, `git.md`.
