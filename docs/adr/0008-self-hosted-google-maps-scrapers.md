# 0008: Self-hosted scrapers for Google Maps, Apify only for Firmy.cz

Status: accepted, 2026-11-17. Changes in part [0005](0005-caching-and-budgeting.md) and [0006](0006-gateway-for-paid-services.md).

## Context

Google Maps Reviews came from the Apify actor `compass/google-maps-reviews-scraper`. A comparison on 2026-11-17 ([research note](../research/google-maps-scraper-alternatives.md), plus two live runs) showed:

- [`YasogaN/google-maps-review-scraper`](https://github.com/YasogaN/google-maps-review-scraper) (npm `google-maps-review-scraper@3.1.0`, Node 20, no browser) returned all 2261 Reviews of one Place in 70 s and 1000 of another in 32 s, newest first, with an exact timestamp in milliseconds, without blocking. It returns no total rating, total count or count per star.
- [`gosom/google-maps-scraper`](https://github.com/gosom/google-maps-scraper) (Go, Docker image, Playwright) returns rating, Review count, count per star, category, address, phone, website, Maps link and thumbnail, but only 5 Reviews.

The Apify actor returns few Reviews for signed-out access and costs per Review. The research note recommended keeping Apify because of the engineering cost; the owner decided otherwise, for the 1000-Review depth, exact dates and Place totals.

## Decision

1. **Run.** Two private sidecar services on Cloud Run, one per tool, each with a small HTTP interface; the Python worker calls them over HTTP. The worker image stays light and gosom (CPU and memory) scales on its own. Locally they run with docker compose.
2. **Gateway.** Both sit behind the Gateway as Services with a cost of 0 per call: a `ServiceClient` and an allow-list entry each. Rate limit, concurrency limit and the Call log apply as for any other service. ADR 0006 is not waived.
3. **Budget.** The Budget estimate for Google Maps scraping is 0 USD per call. Hosting is a fixed cost outside the Run Budget, watched with a GCP billing alert. The 30 USD monthly cap covers models and Google Places. If a paid proxy is added (4), its cost is estimated per Place and goes into the Budget.
4. **Proxy.** Start without a proxy (it worked from a home IP). Before the first production Run, one test from Cloud Run. If Google blocks Cloud Run IPs, the fallback is a paid residential proxy set through an environment variable of both services (estimate 0.02 to 0.04 USD per Place); this ADR is then updated. Apify is not kept as a Google Maps fallback.
5. **Terms of use.** Google's terms forbid scraping, whoever runs the scraper (Apify would carry the same exposure). The owner accepts this exposure as a risk of the project, which is a demo without commercial use. No personal data of Review authors is stored. Legal questions (GDPR, database rights) were not researched.
6. **Versions and breakage.** npm pinned to the exact `3.1.0` with a lockfile; the gosom Docker image pinned by digest (the digest is written in the sidecar ticket). Upgrades only through a PR. The owner watches for breakage. A scheduled smoke test of one known Place once a week opens a GitHub issue when it fails (a separate ticket). At runtime an empty first page for a Place that has a count is a source error and gives a Partial result, never 0 Reviews silently. The research note counts 3 gosom breakage issues in 3 months, so breakage is expected.

Roles: YasogaN is the only Source of Google Maps Reviews (at most 1000 newest per Place and Run, exact date); gosom provides Place details and totals only (`-depth 1`, no `-extra-reviews`). Apify stays for Firmy.cz.

## Changes to earlier decisions

- **0006** says the Gateway is the one way to reach a *paid* service. Now the Gateway also covers the self-hosted scrapers, which cost 0 per call but load our own infrastructure and are limited and logged the same way. Adapters in the Gateway: OpenRouter, Anthropic, Apify (Firmy.cz), Google Places, YasogaN, gosom. Nothing else in 0006 changes.
- **0005** says Provider limits and Budget cover every paid call. Now the Budget estimate of a Google Maps scraper call is 0, and the input limit of Reviews per Place for Google Maps is 1000. The cache, the caps and the rest of 0005 do not change.
- **Specification:** the scraper row of the tech stack, the Review dates row and the Budget row of the Decisions table change (see `docs/specification.md`).

## Consequences

- We absorb every Google change; the Apify vendor no longer does it for Google Maps. Breakage shows as a source error and a Partial result.
- Two more services to deploy and monitor (images, IAM between worker and sidecars).
- About half of Google Reviews have no text; they are kept, and the Taxonomy sample takes only Reviews with text (#123).
- Gateway and budget are critical paths: the new Services touch `app/gateway/**`, so their tickets name that in the PR.
- #121 and #122 got a comment matching this decision; #123, #124 and #125 still fit it unchanged. New follow-ups: #128 (sidecar services and deployment) and #129 (weekly canary).
