# 0005: Caching and budgeting of Runs

Status: accepted, 2026-11-12. Changed in part by [0006](0006-gateway-for-paid-services.md): `budget.reserve` and `record` are called by the gateway, not by `llm` or `sources`.

## Context

The project has a hard monthly cost ceiling of 30 USD, and scraping and model calls are both pay-per-use.

## Decision

- Cache: a fresh result for a Company is reused (about 24 h); a new Run downloads only new Reviews and classifies only Reviews without a ReviewTopic for the current Taxonomy version.
- Budget: every Run has a cap, and there is a monthly cap of 30 USD. `budget.reserve(estimate)` runs before every paid call and `budget.record(cost)` after it. `BudgetExceeded` is never retried; the Run ends with a Partial result.
- Input limits: maximum Reviews per Source and Place, maximum Review length.
- Routing: classification in batches on the cheap model; the strong model sees only Metrics and samples. Prompt caching for system prompts.
- Provider-side limits (Apify spending limit, model API key limits, daily Run limit per user) are the backstop if our code is wrong.
- Per-Run caps are set after the first real measurement.

## Consequences

- `budget` and `llm` are critical paths with a 95 % coverage threshold.
- The monthly total comes from a repository port, so it survives restarts.
- Provider limits live outside the repository; they are listed in `docs/agents/rules-enforcement.md`.
