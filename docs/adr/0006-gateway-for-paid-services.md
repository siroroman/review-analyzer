# 0006: One gateway for all paid services

Status: accepted, 2026-11-12

## Context

Paid services (model providers, Apify, Google Places) were each behind their own port, and only `llm` called `budget`. A scraper or a Places call could therefore spend money without a Budget check, traffic limits lived in several places, and there was no single record of what was called and what it cost. The monthly cap is 30 USD, so one uncontrolled loop matters.

## Decision

- A module `app/gateway/` is the only way to reach a paid service. Public interface: `call(service, operation, request) -> response` over one `ServiceClient` port per service. Adapters (OpenRouter, Anthropic, Apify, Google Places) implement the port and are registered in the gateway.
- The gateway hides: the allow-list of services and operations (anything else is denied), rate limit and concurrency per service, `budget.reserve` before and `budget.record` after every call, and a Service call record in the Call log for every call, including denied and failed ones. The record holds no request or response body.
- It is an in-process module, not a separate service. One Cloud Run image, no network hop, fakes in tests. A separate service stays an option if a second consumer appears; the interface does not change then.
- `gateway` is the only caller of `budget`. `budget` stays pure and now covers every paid service. `BudgetExceeded` is never retried.
- `llm` keeps routing, retry, fallback, schema validation and tracing, and sends every provider call through the gateway. `sources` and `places` do the same for Apify and Google Places. Free or non-paid services (ARES, Langfuse, the database) stay behind plain ports.
- An admin part of the dashboard shows spend and the Call log, protected by a secret Admin token (separate from the Demo token). Login stays out of the MVP.

## Contradictions with earlier ADRs

- [0004](0004-ports-and-module-boundaries.md) says paid services are reached "only through ports". That stays true, but it is refined: a paid service is reached only through the gateway, which owns its ports. `import-linter` forbids importing an adapter of a paid service from anywhere but `gateway`.
- [0005](0005-caching-and-budgeting.md) says `budget.reserve` and `budget.record` run around every paid call inside `llm` and for scraping in `sources`. They now run in `gateway` and nowhere else. The caps, the cache and the provider-side limits in 0005 do not change.

Both ADRs carry a note pointing here.

## Consequences

- `gateway` is a critical path with a 95 % coverage threshold, together with `budget` and `llm`.
- A new paid service means a new `ServiceClient` and an allow-list entry, never a direct import.
- The gateway is a single point of failure for paid calls; it is small, pure where possible and tested with fake clients and a fake `Clock`.
- The Call log is a new table (`ServiceCall`) and a new data-retention question; it stores no Review text.
