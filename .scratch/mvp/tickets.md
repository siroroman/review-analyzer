# Tickets: Review Analyzer MVP (draft)

> Draft for review. Parent: the spec in `.scratch/mvp/spec.md`. IDs `T01`..`T28` are draft IDs; on publish they become GitHub issues, with blocking edges as native dependencies. Mode: **AFK** = `ready-for-agent`, **HITL** = `ready-for-human`. Every ticket also carries: tests through the public interface, error paths, PR template filled, `Closes #N`.

## Dependency overview

```
T01 ─ T02 ─┬─ T03 ─ T04(HITL)
           └─ T05 ─┬─ T06 metrics ───────────────┐
                   ├─ T07 sanitize ─┐            │
                   ├─ T08 budget ─ T09 llm ─┬─ T10 taxonomy ─ T11 classification ─┤
                   │                        └─ T12 insights (needs T06) ──────────┤
                   ├─ T13 storage ───────────────────────────────────────────────┤
T14 research Firmy (HITL) ─┬─ T16 sources/Google ─ T17 sources/Firmy              ├─ T19 pipeline ─ T20 api ─ T21 worker
T15 research Jev (HITL) ───┴─ T18 places ───────────────────────────────────────┘        │
                       T22 LLM adapters ◄─ T09, T15                                      T23 ─ T24 ─ T25 (web)
                       T26 deploy (HITL) ◄─ T21, T22        T27 eval ◄─ T11, T16, T22     T28 demo ◄─ T25, T26
```

---

## T01: Agentic scaffolding (HITL)

**What to build:** The repo works the way `docs/agentic-development.md` describes: an agent opening it finds a signpost, rules, agents and the labels, and the hooks that stop it from damaging the repo.

**Blocked by:** None (can start immediately)

- [ ] `CLAUDE.md` under 3 kB with the `## Agent skills` block (issue tracker, triage labels, domain docs)
- [ ] `docs/agents/` has testing, critical-paths (glob patterns) and rules-enforcement (the enforcement table, including provider spending limits)
- [ ] First ADRs: Python and FastAPI, `domain` types package, Jev with Haiku fallback, ports and module boundaries, caching and budgeting
- [ ] Agents `implementer`, `code-reviewer`, `researcher` and skills `start-task`, `tdd` in `.claude/`, descriptions under 700 characters
- [ ] Stop hook and format-after-edit hook in `.claude/settings.json`; `deny`/`allow` lists
- [ ] The five triage labels (plus `bug`, `enhancement` already exist) created on GitHub

## T02: Python skeleton with quality gates in CI

**What to build:** A trivial module goes through the whole pipeline (lint, types, tests, coverage, boundaries), so the process is proven before real code arrives.

**Blocked by:** T01

- [ ] `pyproject`, `app/` package, `make lint`, `make test`, `make coverage` work locally
- [ ] `ruff`, `mypy --strict`, `import-linter` (direction of dependencies, no internals imported, no network library in pure modules), a lint ban on `datetime.now`, `time.sleep`, `random` in `app/`
- [ ] GitHub Actions runs them, plus `pytest --cov` (90/80/95 thresholds) and `diff-cover` at 90 %
- [ ] A deliberately failing branch (boundary violation, low coverage) is shown to be rejected, evidence in the PR

## T03: CI guard checks

**What to build:** The CI checks that keep agents honest: a PR without a review, with an unnamed critical path or untouched-but-changed guardrail file cannot be merged.

**Blocked by:** T02

- [ ] `review-posted`, critical paths, guardrail paths, PR body, context size, gitleaks checks exist as `scripts/check-*.sh`
- [ ] Every check has its `test-check-*.sh` that runs in CI (`make test-scripts`)
- [ ] Each check has a passing and a failing case shown in tests

## T04: GitHub repository settings (HITL)

**What to build:** The settings that are not in the diff are on and recorded. Suggested to run as a `wizard` script.

**Blocked by:** T03

- [ ] Merge commits only, branches deleted after merge, secret scanning and push protection on
- [ ] Ruleset on `main` with required checks and up-to-date branch
- [ ] The checklist in `docs/agents/git.md` is ticked and the enforcement table updated

## T05: Domain types and Clock port

**What to build:** The shared vocabulary exists in code, so every later module builds on the same Review, Place, Topic and so on, and time never comes from `datetime.now()`.

**Blocked by:** T02

- [ ] Types for Company, Place, RawReview, Review (with `external_id`), Taxonomy, Topic, ReviewTopic, TrendPoint, Metrics, Insight, Run status
- [ ] `Clock` port with a fake; Run status transitions allow forward only
- [ ] Types serialize to and from JSON; invalid values (rating outside 1..5, empty text where forbidden) are rejected

## T06: `metrics`

**What to build:** Given Reviews and ReviewTopics, the module returns every number the dashboard needs, including drops and rises with their main Topic.

**Blocked by:** T05

- [ ] Overall and per-Source averages and counts; TrendPoint per Source per month; Topic shares; per-Place comparison
- [ ] Drop and rise detection with named threshold and minimum count; a month with too few Reviews never yields a drop
- [ ] Month-precision dates land in the right period; empty input, one Review and a single month are handled
- [ ] Pure functions, no mocks, property-based tests for averages and counts

## T07: `sanitize`

**What to build:** Raw Reviews become safe, anonymous, deduplicated clean Reviews, and instructions aimed at a model are flagged and counted.

**Blocked by:** T05

- [ ] HTML and hidden characters removed, length trimmed, author and profile data dropped, emails and phone numbers masked
- [ ] Deduplication by (source, external ID) and by text hash
- [ ] Injection detector behind a port; a Review it flags goes to `flagged`; a detector error also goes to `flagged` (fail closed)
- [ ] Tests include a Review with "ignore previous instructions", zero-width characters and a very long text

## T08: `budget`

**What to build:** No call is made that would break the per-Run or monthly cap, and the real cost is recorded.

**Blocked by:** T05

- [ ] `reserve`, `record`, `BudgetExceeded`; estimate from tokens and a price table
- [ ] Per-Run cap and monthly cap (30 USD) from configuration; the monthly total comes from a repository port
- [ ] Reserve at exactly the cap, a cost above the estimate, and a negative or zero estimate are tested

## T09: `llm`

**What to build:** One entry point that routes a task to the right model, retries, falls back, validates the output against a schema, respects the Budget and traces the call.

**Blocked by:** T05, T08

- [ ] `complete(task, prompt, schema)` routes by task; routing table is configuration
- [ ] Timeout and 5xx retried with backoff; fallback model used after retries; invalid JSON gets one repair retry, then an error
- [ ] `budget.reserve` runs before every call, `record` after; `BudgetExceeded` is not retried
- [ ] Prompt caching flag for system prompts; a `Tracer` port receives task, tokens, cost, latency
- [ ] All with fake providers; the 95 % threshold holds

## T10: `taxonomy`

**What to build:** For a new industry, a frozen list of Topics appears once and is reused by every later Run.

**Blocked by:** T09

- [ ] `get_taxonomy(industry)` returns a stored Taxonomy or generates one from a sample, validates 8 to 15 Topics plus `unclassified`, stores it as an immutable version
- [ ] A second call never calls the model; invalid model output and a too-small sample are handled

## T11: `classification`

**What to build:** Clean Reviews get Topics, sentiment and confidence, cheaply and robustly.

**Blocked by:** T07, T09, T10

- [ ] Batching; 1 to 3 Topics per Review; sentiment and confidence validated
- [ ] Fast model first, fallback model on error, timeout or invalid output (not on low confidence), `unclassified` plus a counter when both fail
- [ ] Topic keys are English; Czech labels live only in the UI
- [ ] Only Reviews without a ReviewTopic for the current Taxonomy version are classified
- [ ] A model response with an unknown Topic key or a missing Review is handled

## T12: `insights`

**What to build:** A summary, explanations of drops and suggestions that cite real Reviews and contain no personal data.

**Blocked by:** T06, T09

- [ ] Input is Metrics plus bounded samples, never the full set
- [ ] Grounding check drops any Insight with a non-existent Review ID and counts it; all dropped gives a deterministic fallback summary from Metrics
- [ ] Content check removes personal data and insults
- [ ] Review text inside the prompt is delimited as data with IDs

## T13: `storage`

**What to build:** Runs, Reviews and results survive between requests, and the cache and monthly totals work.

**Blocked by:** T05

- [ ] Migrations and PostgreSQL repositories; in-memory implementations passing the same contract test suite
- [ ] Unique (source, external_id); reviewer data has no column; Taxonomy versions immutable
- [ ] Cache lookup with TTL through `Clock`; monthly cost total query
- [ ] Integration tests on PostgreSQL via testcontainers

## T14: Research: Firmy.cz, branch discovery and recorded Apify outputs (HITL)

**What to build:** A written answer to whether Firmy.cz can be a Source, and real recorded outputs to build adapters on.

**Blocked by:** None (can start immediately)

- [ ] `docs/research/` note: jupri/firmy and oodoow/mapy-com-ppe tested for review date, review ID, more than 3 Reviews; terms of use read and a go/no-go stated
- [ ] Older dates from compass checked against Google Maps
- [ ] Branch discovery for a Company tested (Google Places text search by name, ARES establishments, user confirmation); the working method and its precision on 3 real companies stated
- [ ] Real outputs recorded as anonymized fixtures for both Sources
- [ ] Spending limit set in Apify before the run; the spec's Source list updated by the outcome

## T15: Research: Jev on Czech and the OpenRouter Decisions API (HITL)

**What to build:** A written answer whether Jev can classify Czech Reviews and injection, and how to call it.

**Blocked by:** None (can start immediately)

- [ ] Note with request and response shape of the Decisions API
- [ ] Sample: 50 real Google Maps Reviews from 2 to 3 industries, labelled by a model and corrected by the user; reused by T27
- [ ] About 15 synthetic Czech injection attacks (direct, hidden, disguised) added to the sample
- [ ] Jev run against the labels; accuracy and failure types stated. Go for Jev only if sentiment agreement is at least 80 %, Topic agreement at least 70 % and injection detection has no false negatives; otherwise Haiku-only
- [ ] Topic keys sent as English keys; a Czech-key variant is compared once
- [ ] Test run uses a separate OpenRouter key with a 5 USD limit (part of the 30 USD monthly Budget)
- [ ] Real responses (including errors) recorded as anonymized fixtures for T22
- [ ] The routing and fallback decision recorded in an ADR

## T16: `sources`: Google Maps adapter

**What to build:** Given a Google Place, the module returns RawReviews with exact dates, incrementally.

**Blocked by:** T05, T14

- [ ] `fetch_reviews(place, since, limit)` over a `ScraperClient` port; Apify adapter maps fields and ISO dates
- [ ] Contract tests on the recorded fixtures; pagination, empty result, partial result and a schema change are tested
- [ ] The spend estimate is exposed so `budget` can reserve before the run

## T17: `sources`: Firmy.cz adapter

**What to build:** The second Source, in the same interface, if the research said go.

**Blocked by:** T14, T16

- [ ] Same interface; date precision (day or month) carried into RawReview
- [ ] Contract tests on recorded fixtures
- [ ] If T14 said no-go, this ticket is closed `wontfix` and the Source list stays Google Maps only

## T18: `places`

**What to build:** Autocomplete, company verification and matching a branch on the other Source.

**Blocked by:** T05, T14

- [ ] `suggest` (Places and Companies), `resolve`, `branches(company)` by the method T14 chose, `match_other_sources` over fake HTTP clients; Google Places (New) and ARES adapters
- [ ] Contract tests on recorded responses; company ID mismatch, no result and ARES outage are tested
- [ ] The Google key is only read server side from configuration

## T19: `pipeline`

**What to build:** `run(run_id)` executes the whole flow on fakes and ends with a result, a Partial result or a clear failure.

**Blocked by:** T06, T07, T08, T10, T11, T12, T13, T16, T18

- [ ] State machine with forward-only transitions; resumable, idempotent steps
- [ ] End-to-end tests with every port faked: happy path, Budget exceeded gives Partial result, one step failing past retry, redelivered Run
- [ ] A Run for a fresh cached target reuses the result; only new Reviews are fetched and classified

## T20: `api`

**What to build:** The HTTP interface the frontend uses, protected by a demo token and limits.

**Blocked by:** T13, T19

- [ ] Endpoints from the spec; OpenAPI generated; input validation (length, characters)
- [ ] Missing or wrong token gives 401; per-IP rate limit; daily Run limit per token
- [ ] `POST /runs` returns an existing fresh Run instead of a duplicate
- [ ] No business logic in the layer; tested over a faked `pipeline`

## T21: `worker` and queue

**What to build:** A Run started through the API is executed in the background and survives a retry.

**Blocked by:** T19, T20

- [ ] `Queue` port with an in-process fake and a Cloud Tasks adapter; the worker only calls `pipeline.run`
- [ ] Redelivery of the same message does not double the cost or the Reviews (tested)

## T22: LLM adapters: OpenRouter, Anthropic, Langfuse

**What to build:** The real providers and the tracer behind the `llm` ports.

**Blocked by:** T09, T15

- [ ] Decisions API client (not OpenAI compatible) and Anthropic client; contract tests on responses recorded in T15
- [ ] Fallback to Haiku only on error, timeout or invalid output, not on low confidence; if the injection detector fails on both, the Review is marked Flagged
- [ ] Langfuse `Tracer` records tokens and price of every call; Jev is priced on input tokens only (output is free)
- [ ] Keys read from configuration only; no key in logs

## T23: Web: search and progress

**What to build:** A user can find a company, start a Run and watch its steps and cost.

**Blocked by:** T20

- [ ] Vite and React skeleton typed from the OpenAPI schema
- [ ] Search with debounced autocomplete, choosing exactly one Place or one Company; for a Company a step that shows the found branches and lets the user remove false ones
- [ ] Progress screen polling every 2 s with steps and running cost; reopening the link resumes it
- [ ] Vitest and Testing Library, 80 % threshold in CI

## T24: Web: result dashboard

**What to build:** The overall rating, rating per Source and the timeline with marked drops and rises.

**Blocked by:** T23

- [ ] Rating and counts per Source; timeline with drop and rise markers and the main Topic label
- [ ] Partial-result banner; empty and single-month states

## T25: Web: topics, insights, branches, cost

**What to build:** Topic shares with the actual Reviews on click, suggestions with links, branch comparison and the cost of the Run.

**Blocked by:** T24

- [ ] Topic shares open the cited Reviews in a side panel
- [ ] Insights and suggestions link to Reviews; branch comparison; cost and excluded-Reviews count

## T26: Deploy to Cloud Run (HITL)

**What to build:** The system runs in the cloud with secrets and spending limits in place.

**Blocked by:** T21, T22

- [ ] Docker image for `api` and `worker`; Cloud Run, Cloud Tasks, Neon, Secret Manager
- [ ] Deploy workflow in GitHub Actions; migrations run on deploy
- [ ] Spending limits in Apify and model keys set and recorded; a smoke Run against the deployed system

## T27: Evaluation set and harness

**What to build:** A repeatable accuracy report for classification.

**Blocked by:** T11, T16, T22 (labelling is HITL)

- [ ] 100 to 200 real Reviews hand-labelled, anonymized, stored as data (starts from the 50 Reviews labelled in T15)
- [ ] A manual or nightly command that prints accuracy per Topic and sentiment and compares with the last report
- [ ] It does not run in the normal CI and does not count toward coverage

## T28: Demo: precomputed company and token links

**What to build:** A link with a token opens a finished analysis of a chosen company, and the viewer can try another within the limits.

**Blocked by:** T25, T26

- [ ] A Run for the chosen company is precomputed and cached beyond the normal TTL
- [ ] Token issue and revoke documented; limits verified on the deployed system
