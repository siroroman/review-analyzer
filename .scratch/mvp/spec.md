# Spec: Review Analyzer MVP

> Draft for review. Not yet published to GitHub. Architecture and rationale stay in `docs/specification.md`; this document is the detailed, ticketable spec. Terms follow `GLOSSARY.md`. Items marked **[CONFIRM]** are decisions I made that you should confirm.

## Problem Statement

An owner or manager of a Czech company with many branches has hundreds of public reviews spread over Google Maps and Firmy.cz. Reading them is slow, the two Sources disagree, and nobody can say why the rating fell last March or what to fix first. Existing tools show stars and word clouds, not the reasons, and they cannot be trusted when reviews contain junk or even instructions aimed at AI.

## Solution

The user types a company name, picks the company or a specific branch from an autocomplete, and within a few minutes gets a dashboard: overall rating and rating per Source, a timeline with explained drops and rises, Topics with positive and negative shares and example Reviews, a comparison of branches, and suggestions for improvement that link to the Reviews they rest on. Every number is computed by code, every statement of the model is grounded in real Review IDs, every Run has a visible cost and a hard Budget.

## User Stories

### Searching and choosing what to analyze

1. As a manager, I want to type a company name and see suggestions with name, address and company ID, so that I pick the right company or branch without guessing.
2. As a manager, I want the suggestions to appear quickly while I type, so that search feels instant.
3. As a manager, I want to choose a single branch, so that I analyze only my own location.
4. As a chain owner, I want to choose the whole company instead of one branch, so that I get one analysis with a comparison of its branches. **Decided: one choice per Run, either one Place or one Company, never a mix.** (Open: how a Company is expanded into its Places, see Further Notes.)
5. As a manager, I want the company verified by its company ID, so that I know the Reviews belong to the right legal entity.
6. As a manager, I want a clear message when no company or no Reviews are found, so that I know what to try next.
7. As a manager, I want an invalid or abusive input (too long, strange characters) to be rejected with an explanation, so that I am not left with a hanging request.

### Running an analysis

8. As a manager, I want to start an analysis with one click, so that I do not configure anything.
9. As a manager, I want to see the steps of the Run (downloading, cleaning, classifying, analyzing) and the cost so far, so that I know it is working and what it costs.
10. As a manager, I want to leave the page and come back to the same Run through its link, so that I do not have to wait on the screen.
11. As a manager, I want a fresh cached result to open immediately instead of a new Run, so that I do not wait or pay twice.
12. As a manager, I want a repeated Run to download only new Reviews, so that it is cheap and fast.
13. As a manager, I want a Run that hits its Budget to show a Partial result with a clear note of what is missing, so that I still get value and no surprise cost.
14. As a manager, I want a failing step retried automatically and then replaced by a fallback or a clear error, so that one hiccup does not lose the Run.

### Reading the result

15. As a manager, I want the overall rating and the rating per Source with the number of Reviews, so that I see where the problem is.
16. As a manager, I want a timeline of average rating and sentiment per month, so that I see development, not just the current value.
17. As a manager, I want drops and rises marked on the timeline with the main Topic ("March: waiting at the checkout"), so that I get the reason, not only the symptom.
18. As a manager, I want to see the share of positive and negative mentions per Topic, so that I know what customers praise and complain about.
19. As a manager, I want to click a Topic and read the actual Reviews, so that I can verify the claim myself.
20. As a chain owner, I want a comparison of branches by rating and main problems, so that I see which branch needs attention.
21. As a manager, I want a short summary and concrete suggestions for improvement, each linking to Reviews, so that I trust and can verify them.
22. As a manager, I want the cost of the Run (scraping and models) and the number of excluded suspicious Reviews, so that I understand what the result is based on.
23. As a manager, I want Reviews with only a month precision (Firmy.cz may show relative dates) to be placed in the right period without a false exact date, so that the timeline is honest.
24. As a manager, I want Reviews in other languages handled or clearly counted as not analyzed, so that numbers are not silently skewed.

### Trust and safety

25. As a manager, I want Reviews that try to instruct the AI to be excluded and counted, so that nobody can manipulate my report.
26. As a manager, I want reviewer names and personal data never stored or shown, so that the tool is GDPR-safe.
27. As a manager, I want every statement to cite existing Reviews, so that nothing is invented.
28. As a manager, I want all numbers computed by code, so that the model cannot get arithmetic or trends wrong.
29. As a manager, I want insulting or personal content filtered from the model's text, so that I can share the report.

### Operating (owner)

30. As the owner, I want a hard per-Run Budget and a monthly cap of 30 USD, so that a bug or a big company cannot cost me a surprise.
31. As the owner, I want a daily limit of Runs per demo token and a rate limit per IP, so that the demo cannot be abused.
32. As the owner, I want every model call traced with tokens and price, so that I can see where the money goes.
33. As the owner, I want a precomputed demo of a selected company behind a link with a token, so that I can show the product without waiting for a Run.
34. As the owner, I want to try another company in the demo within the limits, so that viewers can test it on their own case.
35. As the owner, I want provider spending limits (Apify, model keys) set and documented, so that the cap holds even if my code fails.
36. As the owner, I want API keys never in the browser or the repository, so that nobody can steal them.

### Development process (maintainer)

37. As a maintainer, I want every module tested through its public interface with fake ports, so that the implementation can change without rewriting tests.
38. As a maintainer, I want CI to block a merge below coverage, on a boundary violation or without a review, so that quality does not depend on discipline.
39. As a maintainer, I want an evaluation set of hand-labelled Reviews and a repeatable accuracy report, so that I know whether a model change made classification worse.
40. As a maintainer, I want each AFK ticket to be implementable from its text alone, so that an agent can finish it in a fresh session.

## Implementation Decisions

### Modules and interfaces

Modules, dependency direction and rules are as in `docs/specification.md` (deep modules, ports, one-way dependencies). Decisions on top of it:

- **`domain` (new) [CONFIRM]**: a bottom package with the shared Pydantic types (Company, Place, Review, RawReview, Topic, Taxonomy, ReviewTopic, TrendPoint, Metrics, Insight, Run status) and the `Clock` port. It has no logic and no I/O. Without it, either every module re-declares Review or the domain modules import each other. Needs ADR.
- **`places`**: `suggest(query) -> list[Suggestion]` (each Suggestion is a Place or a Company), `resolve(place_id) -> Company + Place`, `branches(company) -> list[Place]` (expansion of a Company into its Places), `match_other_sources(place) -> list[Place]` (Firmy.cz by name and address). Suggestion carries name, address, company ID when known.
- **`sources`**: `fetch_reviews(place, since, limit) -> list[RawReview]`. One adapter per Source behind one port. `RawReview` has the source's own review ID, rating, text, date, date precision (day or month), language if given. Dedup key is (source, external review ID).
- **`sanitize`**: `prepare(raw) -> PreparedReviews(clean, flagged)`. Steps in fixed order: strip HTML, remove hidden and control characters, trim length, drop author name and any field that identifies a person, mask emails and phone numbers in text, hash for dedup, injection detector (port). A detector failure is treated as `flagged` (fail closed), never as clean.
- **`taxonomy`**: `get_taxonomy(industry) -> Taxonomy`. Generated once per industry from a sample (about 200 Reviews), then frozen and stored; reused by every later Run. Size 8 to 15 Topics. A `unclassified` Topic always exists.
- **`classification`**: `classify(reviews, taxonomy) -> list[ReviewTopic]`. Batches of N Reviews per call, a Review can have 1 to 3 Topics, each with sentiment (positive, neutral, negative) and confidence 0 to 1. Fast model first, fallback model on failure or unparsable output, then retry, then `unclassified` for that batch with a counter.
- **`metrics`**: `compute(reviews, topics, clock) -> Metrics`. Pure. Contents: overall and per-Source average and count, TrendPoint per Source per month, Topic shares (positive, negative, mixed), per-Place comparison, drops and rises. A **drop** is a month whose average falls below the trailing 3-month average by more than a threshold, and which has at least a minimum number of Reviews (the minimum count prevents false drops from tiny months). Threshold and minimum are named constants with tests, set after the first real data. For each drop or rise the main Topic is the one whose negative (or positive) share changed most versus the previous period.
- **`insights`**: `generate(metrics, samples) -> Insights`. Input is aggregated Metrics plus a bounded sample of Reviews per drop, Topic and suggestion (not the full set). Output validated by schema. Grounding check: every cited Review ID must exist in the Run's Reviews, otherwise that Insight is dropped and counted; if nothing survives, a deterministic fallback summary built from Metrics is shown. Content check removes personal data and insults.
- **`llm`**: `complete(task, prompt, schema) -> T`. `task` selects the route (classification to the fast model, taxonomy and insights to the strong model). Handles retry with backoff, fallback model, prompt caching of system prompts, schema validation with a repair retry, tracing through a `Tracer` port, and calls `budget` before every call. Providers sit behind a `LLMProvider` port (OpenRouter Decisions API for Jev, Anthropic).
- **`budget`**: `reserve(estimate)`, `record(cost)`, `BudgetExceeded`. Estimate from input tokens and the price table before a call; `record` stores the real cost after. Per-Run cap and monthly cap (30 USD). The monthly total reads from `storage`. Scraping cost (Apify) is estimated from the review limit before the scraper starts and recorded after.
- **`storage`**: repositories `ReviewRepo`, `RunRepo`, `InsightRepo`, `TrendRepo`, plus `TaxonomyRepo` and `CompanyRepo`. PostgreSQL implementation with migrations, in-memory implementation for tests. Cache TTL read through `Clock`.
- **`pipeline`**: `run(run_id) -> RunResult`. Steps: resolve places, fetch, sanitize, store, classify (only Reviews without a ReviewTopic for the current Taxonomy), compute Metrics, generate Insights, store. Idempotent and resumable: re-running a Run skips finished steps. Budget exceeded at any step produces a Partial result.
- **`api`** and **`worker`**: thin. `api` validates input, enforces tokens and limits, creates a Run, returns status and result. `worker` receives a queue message `{run_id}` and calls `pipeline.run`.

### Data model changes against the high-level spec

- **Review** gets `external_id` (the source's own review ID) with a unique constraint on (source, external_id). The high-level spec dedups by hash only, but the critical-paths section already depends on `external_id`; both are kept (external ID for identity, text hash for cross-Source duplicates).
- **Run** has exactly one target (a Place or a Company), a join to the Places it expanded into (1 to a configured maximum, default 50), and a `partial` flag with a reason.
- **ReviewTopic** is keyed by (review, topic, taxonomy version), so a changed Taxonomy does not corrupt old results.
- **Taxonomy** is versioned per industry and immutable once frozen.
- **Run status**: `queued`, `fetching`, `sanitizing`, `classifying`, `analyzing`, `done`, `partial`, `failed`. Transitions are forward only; `failed` and `partial` are terminal.
- Reviewer names, profile links and photos are never persisted.

### API contract (first version)

- `GET /places/suggest?q=` → suggestions. Rate limited per IP, debounced client side, the Google key stays server side.
- `POST /runs` with `{target: {type: "place" | "company", id}}` → `{run_id}`; returns an existing fresh Run for the same target instead of creating a new one.
- `GET /runs/{id}` → status, current step, cost so far (polled every 2 s; no server push in the MVP **[CONFIRM]**).
- `GET /runs/{id}/result` → rating per Source, TrendPoints, Topic shares with Review IDs, Place comparison, Insights, cost breakdown, excluded count, partial flag.
- `GET /reviews?ids=` → the Review texts cited by a result (for the click-through).
- All endpoints require a demo token; unauthenticated calls get 401. Daily Run limit counted per token.
- The OpenAPI schema is generated from the Pydantic types and is the contract the frontend is typed against.

### Scraping and sources

- Google Maps via Apify `compass/google-maps-reviews-scraper` using the `place_id`, `reviewsStartDate` for incremental runs, dedup by review ID.
- Firmy.cz is conditional on the research ticket: if no actor yields dated Reviews beyond 3 per company, or terms of use forbid it, the MVP ships with Google Maps only and the dashboard hides the Source comparison. The code path is the same, the Source list is configuration **[CONFIRM]**.
- Max Reviews per Source and Place and max review length are configuration; defaults set after the first measurement.

### Language and UI

- Reviews are mostly Czech. Insights are generated in Czech; dashboard UI text in English **[CONFIRM]**. Reviews in other languages are counted as `not analyzed` unless the model handles them, shown in the "based on" line.
- Charts: Recharts; Topics and Insights link to Review text in a side panel.

### Infrastructure

- One Docker image for `api` and `worker`, Cloud Run, Cloud Tasks for the queue, Neon PostgreSQL, Secret Manager, GitHub Actions deploy. Cloud Tasks has retry and a dead-letter behavior; `pipeline` idempotency makes redelivery safe.
- Spending limits in Apify and in both model keys are configured by the owner and recorded in `docs/agents/rules-enforcement.md` (they are guardrails outside the diff).

## Testing Decisions

- **A good test** calls only the public interface of a module and checks external behavior: inputs in, outputs or errors out. No assertions on private helpers or call order of internals.
- **Seams [CONFIRM]**: the highest seam is `pipeline.run(run_id)` with every port faked; it proves the whole flow, the Partial result and idempotency in a handful of tests. Below it, one seam per module interface (its Protocol). `metrics`, `sanitize`, `budget` are pure and tested without mocks, `sanitize` additionally property-based. Adapters are tested by contract tests on recorded responses. `storage` is tested against a real PostgreSQL (testcontainers) and through the same repository contract on the in-memory version, so both pass one shared test suite. `api` is tested with an HTTP test client over a faked `pipeline`. Frontend: Vitest and Testing Library with a mocked API layer.
- **Mandatory error paths** per module: timeout, invalid model JSON, exceeded Budget, empty input, prompt injection in a Review, non-existent Review ID in a model response, detector failure, duplicate Review, partial scraper result.
- **No live services in CI.** Live contract tests and the evaluation set run manually or nightly and do not count toward coverage.
- **Coverage gates** as in the high-level spec: 90 % overall (lines and branches), 80 % per file, 95 % in `metrics`, `sanitize`, `budget`, `llm`, 90 % diff coverage, 80 % frontend. The number follows behavior tests, it is never the goal.
- **Prior art**: none yet; the first module (`metrics`) sets the pattern and its tests are the reference for the others.
- **Evaluation**: 100 to 200 hand-labelled Reviews give classification accuracy per Topic and sentiment; a model or prompt change is accepted only with a report that is not worse.

## Out of Scope

Login and accounts, regular monitoring and notifications, comparison with competitors, further Sources (Heureka, Trustpilot, Mapy.com) in this spec, suggested replies to Reviews, selecting several unrelated Places in one Run, vector search (pgvector), PDF or CSV export, multi-language UI, billing.

## Further Notes

- **Open: expanding a Company into Places.** Neither ARES nor Google Places lists branches by company ID. Candidates to test in research: Google Places text search by company name filtered by name and address match, ARES establishment data, a user-confirmed list. Until decided, a Company target needs a user confirmation step that shows the found branches and lets the user remove false ones. The choice stays one per Run.
- **Open research gates** (also tickets): (a) whether Firmy.cz can be scraped with dates, beyond 3 Reviews and within terms of use; (b) whether Jev handles Czech and how to call the OpenRouter Decisions API (not OpenAI compatible). Outcomes can change the Source list and the fast-model choice; the model routing lives in configuration so that a change does not touch modules.
- **Risks**: Apify actors change their output (contract tests on recordings catch it in the nightly run); Firmy.cz terms; Czech sentiment accuracy of the fast model; Budget estimate accuracy before the first measurement (start with conservative caps).
- **Inconsistencies found in current docs**, to be fixed by the scaffolding ticket: `CLAUDE.md`, `docs/agents/critical-paths.md`, `docs/agents/rules-enforcement.md` and `docs/adr/` are referenced but do not exist; `Review` lacks `external_id`; "daily limit per user" has no users (so per token); "branch comparison" and "analyze the whole chain" need the Place-set decision above.
