# Google Maps Reviews: open-source scrapers and the official API as alternatives to Apify

Researched 2026-11-17. Status of every number is marked **V** (verified, with source) or **E** (estimate).

## 1. Question

Is there an existing open-source scraper (or the official Places API) that could replace, or sit beside, the paid Apify actor `compass~google-maps-reviews-scraper` as a Source behind the Gateway? The project needs per Review: placeId, reviewId, stars, text, publishedAtDate, language; per Place: overall rating (totalScore) and total Review count (reviewsCount); up to 100 newest Reviews per Place per Run; Czech (`cs`) must work.

Feeds: ADR [0005](../adr/0005-caching-and-budgeting.md) (budget and caps), ADR [0006](../adr/0006-gateway-for-paid-services.md) (every paid service is a `ServiceClient` in `app/gateway/`), and the Source choice in `docs/specification.md`. No ticket number was given.

## 2. Answer

- No open-source option I found is a drop-in replacement. All self-hosted scrapers drive a browser or an undocumented Google endpoint, and Google has been tightening signed-out access in 2026 (Apify's own actor lost reviews beyond the first 5 until a fix on 2026-10-29; a second scraper documents a 5-review cap for signed-out browsers; gosom reports 403 on its review RPC).
- The official Places API (New) cannot do the job: it returns at most 5 Reviews, sorted by relevance, and Google's terms forbid storing Reviews outside the service.
- Apify is cheap at the project's volume: list price 0.30 USD per 1,000 Reviews (V), so 100 Reviews is 0.03 USD. The code placeholder 0.0006 USD per Review is twice that, so the Budget estimate is conservative.
- Recommendation: keep Apify as the only Source for now; do not build a second scraper Source. If a fallback is ever wanted, `gosom/google-maps-scraper` (MIT, active) is the first candidate, behind the same port, as an experiment only.

## 3. Evidence

### 3.1 Current Apify actor (what the code expects)

- Price: pay per event, from 0.30 USD per 1,000 scraped reviews; Free plan includes 5 USD of credit; Starter 19 USD per month. Page read 2026-11-17: https://apify.com/compass/google-maps-reviews-scraper (V). Compare placeholder in `app/budget/_estimate.py`: 0.0006 USD (placeholder, 2x list). Whether a per-run start fee exists was not visible (see section 4).
- Output fields `totalScore`, `reviewsCount`, `stars`; sort `newest`; `reviewsStartDate` works only with newest sort; `maxReviews` per place (same page, V).
- Changelog (https://apify.com/compass/google-maps-reviews-scraper/changelog, read 2026-11-17, V): 2026-10-29 fix, reviews had stopped after the first 5 per place; `reviewsFilterString` is ignored; 2026-08-10 place IDs not starting with `ChIJ`/`GhIJ` (27 chars) are skipped and a run with none fails; 2026-05-29 `forceEng` removed in favour of `language`; 2026-10-14 Google hides some details from non-logged-in users.
- Relevant to `app/gateway/_apify.py`: it already sends `placeIds`, `maxReviews`, `reviewsSort=newest`, `language=cs`, `reviewsStartDate`. A place ID that is not `ChIJ`/`GhIJ` would now yield an empty or failed run; worth a validation at the Place boundary (not verified in code, I only read `_apify.py`).

### 3.2 Candidate repositories

Stars, license, language and push date from the GitHub search API (https://api.github.com/search/repositories?q=google+maps+reviews+scraper&sort=stars, read 2026-11-17), plus README pages read the same day. "Last push" is the `pushed_at` of the default branch.

| # | Repo | License | Stars | Language | Last push | Maintained |
|---|------|---------|-------|----------|-----------|------------|
| 1 | https://github.com/gosom/google-maps-scraper | MIT | 8,192 | Go | 2026-11-15 | Yes, 67 open issues |
| 2 | https://github.com/georgekhananaev/google-reviews-scraper-pro | MIT | 351 | Python | 2026-11-12 | Yes (v1.4.0, Nov 2026) |
| 3 | https://github.com/YasogaN/google-maps-review-scraper | MIT | 127 | TypeScript (npm) | 2026-11-06 | Yes (v3.1.0 on 2026-10-04) |
| 4 | https://github.com/gaspa93/googlemaps-scraper | GPL-3.0 | 537 | Python | 2026-11-02 | Dependency bumps only; scraper PRs stale since 2025 |
| 5 | https://github.com/omkarcloud/google-maps-reviews-scraper | MIT | 193 | n/a (desktop app, Botasaurus) | 2026-11-10 | Yes, but a product with a paid tier |
| 6 | https://github.com/noworneverev/google-maps-scraper | MIT | 13 | Python | 2026-03-09 | Low; README documents no review text |
| 7 | https://github.com/Anonym0usWork1221/GMapsScraper | MIT | 86 | Python | 2026-09-30 | Not examined beyond the search listing |
| 8 | https://github.com/outscraper/google-maps-reviews-python | MIT | not read | Python | not read | SDK of the paid hosted Outscraper API, not a scraper (search listing only) |

Excluded: `ScrapingBee/google-reviews-scraper` and `luminati-io/Google-Maps-Scraper` are clients of commercial APIs (listing descriptions only). `MajideND/scraping-reviews-from-googlemaps` last push 2024-08-26 (abandoned).

### 3.3 How each gets Reviews

Items marked "not stated" were not in the README I read; I did not run any of them.

**1. gosom (Go, Playwright headless browser).** README (read 2026-11-17): reviews included; `-extra-reviews` collects more without sign-in, but the README says Google may expose only a small sample, and reports a `review_collection` status complete, limited or partial. Rating and count: `review_rating`, `review_count`, `reviews_per_rating`. Proxies: socks5/http(s) supported. Heavy CPU and memory. Sort and since-date: not stated. Czech: not stated. Issues (GitHub API, read 2026-11-17): #327 (2026-09-01, open) `-extra-reviews` returns about 10 reviews, internal RPC `listugcposts` returns 403 even from 4 US residential proxy exits (reporter: places with 435 to 2,076 reviews got 2 extended entries); #234 `user_reviews` only `[]` (2026-02); #338 all jobs fail "target closed" (2026-10); #322 "unexpected page type"; #277 EU consent redirect fix. Only the first 100,000 characters of the issue list were read.

**2. georgekhananaev/google-reviews-scraper-pro (Python, SeleniumBase undetected Chrome).** Sort newest/highest/lowest/relevance; `date_filter` with early stop only with newest; incremental modes `new_only`/`update`/`full`; 25+ languages claimed. Rating per Review yes; total Review count appears only in a warning example, not documented as a field. Limits: signed-out browsers see only the first 5 reviews; signed-in mode needs a Chrome profile (a Google account, which this project must not use, see section 5). Feb 2026: direct place URLs gave a "limited view", so it navigates via search. CAPTCHA and `/sorry/` pages handled with a 60 s cooldown. Its FAQ states scraping violates Google's ToS. Relative dates ("2 weeks ago") are converted to approximate dates, which is weaker than Apify's `publishedAtDate`.

**3. YasogaN/google-maps-review-scraper (TypeScript, internal `GetLocalBoqProxy` endpoint, no browser).** Sort relevant/newest/highest/lowest; about 10 Reviews per page, `pages` option; optional HTTP proxy. Rating and total count: not stated. Language: not stated. README calls it educational, "based on my research, so errors could be present". Issues and PRs through 2026-10 are about validation and CI, not about Google blocking (only the first 100,000 characters read). Cheapest to run (no browser) but reverse-engineered and unofficial.

**4. gaspa93/googlemaps-scraper (Python, ChromeDriver browser automation, per README).** `--sort_by newest` default; `--N` count (default 100); since-date only in `monitor.py` (`--from-date`) which needs MongoDB. Rating/total count, language, proxy: not covered in README. Open issues (GitHub API, read 2026-11-17) include a broken CSS selector (#61, 2024), relative date and rating not parsed (#49), hotel layout failures (#64); no maintainer fixes visible since 2025. GPL-3.0 would also impose copyleft if we link it.

**5. omkarcloud (desktop app, Botasaurus, Chrome).** Review sorts newest/relevant/highest/lowest; max reviews per place; `rating`, `reviews`, `reviews_per_rating`; per-review `original_language`. A GUI product, free tier 200 searches per month, Pro 28 USD one-time; not a library to embed. No proxy documentation.

**6. noworneverev (Python, Playwright Firefox).** Gives `rating` and `review_count` per place and `--lang`, but the README documents no Review text or sorting. Useful at most for the per-Place rating and count, not for Reviews.

**7 and 8.** Not evaluated in depth (see table).

### 3.4 Official Places API (New)

- Reviews: `reviews[]`, at most 5, "sorted by relevance". `rating` and `userRatingCount` are provided; each Review has `name` (id), `publishTime`, `rating`, `text`, `originalText`; language only as a BCP-47 code inside the text objects. Source: https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places (V, read 2026-11-17).
- SKU mapping: `rating` and `userRatingCount` trigger Place Details Enterprise; `reviews` triggers Place Details Enterprise + Atmosphere. https://developers.google.com/maps/documentation/places/web-service/data-fields and .../place-details (V, 2026-11-17).
- Price per 1,000 calls, first tier: Enterprise 20 USD (1,000 free per month); Enterprise + Atmosphere 25 USD (1,000 free per month). https://developers.google.com/maps/billing-and-pricing/pricing (V, 2026-11-17). One Place per Run with reviews: about 0.025 USD, and only 5 Reviews, so 100 Reviews is not reachable through this API.
- Storage: Places policies say Google Maps Content including user reviews may be cached or stored only as the Service Specific Terms expressly permit; only place IDs (indefinitely) and lat/lng (30 days) are exempt; no exception for reviews or ratings is given. https://developers.google.com/maps/documentation/places/web-service/policies (V, 2026-11-17). Our database stores Review text, so even the 5-Review path conflicts.
- The project's price table already lists `google_places` units (details 0.017, text search 0.032, autocomplete 0.00283 USD per request). These are placeholders and I did not reconcile them with the page; the Enterprise Place Details price I read is 0.020 USD, not 0.017 (see section 4).

### 3.5 Terms of service and legal risk

- Google Maps Platform Terms, section 3.2.3(a) "No Scraping": customer may not export, extract or otherwise scrape Google Maps Content for use outside the Services, with examples including copying user reviews; (b) caching only where the Service Specific Terms allow. Found via search result summary of https://cloud.google.com/maps-platform/terms (the page itself was truncated for my fetcher, so I did not read the clause text directly; the EEA variant https://cloud.google.com/terms/maps-platform/eea has the same rule under 3.3.2). Partly verified.
- Consumer Google Maps/Earth terms (https://www.google.com/help/terms_maps/, V, 2026-11-17): bans mass download or bulk feeds of content (2.3) and building business-listing datasets for a substitute service (2.4). Scraping is not named explicitly.
- Scraping is therefore against Google's terms in any variant, whether we run the scraper or Apify does. Using Apify does not remove the exposure to the project; it only moves the technical operation to a vendor. Practical risk observed: technical blocking and breakage (3.2, 3.3), not known lawsuits. I did not research case law, GDPR treatment of reviewer names, or EU database rights; they need a lawyer, not this note.
- Each README I read carries a disclaimer too (georgekhananaev: violates ToS; YasogaN: educational, non-commercial).

## 4. Cost and effort at 100 Reviews per Place

| Item | Apify actor | Self-hosted scraper (gosom or similar) | Places API |
|------|-------------|----------------------------------------|-----------|
| Per Review / per Place | 0.30 USD per 1,000 Reviews, so 0.03 USD per Place of 100 (V) | no per-Review fee | 0.020 + 0.025 USD per Place for rating/count plus 5 Reviews (V list prices) |
| Placeholder in code | 0.0006 per Review, so 0.06 per Place (2x list) | n/a | 0.017 details (below the 0.020 list price) |
| Proxy | included in the actor price (E, not stated on page) | residential proxy: Apify list 8 USD per GB on Free/Starter (V, https://apify.com/pricing); pages per Place of 100 Reviews perhaps 2 to 5 MB, so about 0.02 to 0.04 USD (E, page size not measured) | none |
| Hosting | none | Cloud Run or a VM with a headless browser; Cloud Run price per vCPU-second not verified because the page was truncated; I would guess a few cents per month at this volume (E) | none |
| Free tier | 5 USD credit on Free plan (V) | none | 1,000 free calls per month per SKU (V) |
| Maintenance | vendor fixes breakage (fixed the 5-review regression 2026-10-29, V) | we absorb every Google change; gosom has 3 breakage issues in the last 3 months (V) | none |
| Engineering to build | done (`_apify.py`) | new adapter, language/date normalisation, proxy, anti-bot, monitoring (E: several days plus ongoing) | n/a, does not meet the need |

Volume check against the 30 USD monthly cap (ADR 0005): Apify cost of 100 Reviews for 100 Places is about 3 USD per full refresh at list price (E, arithmetic from V price). Savings from a self-hosted scraper are cents per month, well below the engineering and maintenance cost.

Also note: an Apify Starter plan or higher may carry a store discount; the actual price per Review at the project's plan was not checked.

## 5. Not verified

- Terms text of section 3.2.3 was not read from Google's page directly (my fetcher got a truncated page); the content is from a search summary plus the Places policies page, which I did read.
- No scraper was run. All behaviour (sorting, date filter, Czech text, rating and count fields) is from READMEs and issues, not tests. Czech support is not documented for gosom, YasogaN, gaspa93. For georgekhananaev and noworneverev it is claimed generically for many languages or locales.
- Whether Apify charges an actor-start fee or what the actual rate is on this project's Apify plan.
- Cloud Run price figures (page truncated), proxy bandwidth per Place, hosting hours: estimates only.
- Issue lists for gosom and YasogaN were truncated at 100,000 characters; older or later items may be missing. I did not read issue comments beyond #327's summary.
- Candidates 7 and 8 were not examined; no search of GitLab, Codeberg or other non-GitHub hosts.
- Legal: EU/Czech law, database rights, GDPR for reviewer names, enforceability of Google's terms. Not researched.
- Source-page instructions: none of the pages read contained instructions aimed at me.

## 6. Recommendation

Keep Apify as the single Source for Google Reviews and do not add a second scraper Source now: self-hosting saves only a few cents per Place against several days of build and ongoing breakage handling, while Google's 2026 tightening (5-Review cap, 403 on the review RPC, limited view) hits self-hosted and Apify scrapers alike, and Apify at least fixes it for us. The Places API is not a replacement, because of the 5-Review cap and the no-storage rule; it remains fine for Place discovery and, where displayed live, for rating and count only. Small follow-ups worth separate tickets: (1) re-check `("apify","review")` placeholder 0.0006 against the real plan price (list is 0.0003); (2) validate that place IDs start with `ChIJ`/`GhIJ` before calling the actor; (3) have the `ScrapedReview` check detect "fewer than 6 Reviews for a Place with reviewsCount well above that" as a suspected silent cap (the 2026-10 regression) and report a Partial result; (4) record the ToS exposure in an ADR if the owner has not already accepted it. If a fallback is ever required, prototype `gosom/google-maps-scraper` behind the existing port as a separate ticket. This would change no ADR now; a second Source would add a `ServiceClient` and allow-list entry per ADR 0006 and a note in ADR 0005 if its cost model differs.

## Sources (all accessed 2026-11-17)

- https://apify.com/compass/google-maps-reviews-scraper
- https://apify.com/compass/google-maps-reviews-scraper/changelog
- https://apify.com/pricing
- https://developers.google.com/maps/billing-and-pricing/pricing
- https://developers.google.com/maps/documentation/places/web-service/place-details
- https://developers.google.com/maps/documentation/places/web-service/data-fields
- https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places
- https://developers.google.com/maps/documentation/places/web-service/policies
- https://cloud.google.com/maps-platform/terms
- https://cloud.google.com/terms/maps-platform/eea (via search result)
- https://www.google.com/help/terms_maps/
- https://cloud.google.com/run/pricing (page truncated, not relied on)
- https://api.github.com/search/repositories?q=google+maps+reviews+scraper&sort=stars&per_page=20
- https://api.github.com/repos/gosom/google-maps-scraper (and /issues), https://github.com/gosom/google-maps-scraper, https://github.com/gosom/google-maps-scraper/issues/327
- https://github.com/georgekhananaev/google-reviews-scraper-pro
- https://github.com/YasogaN/google-maps-review-scraper (and API /issues)
- https://github.com/gaspa93/googlemaps-scraper (and API /issues)
- https://github.com/omkarcloud/google-maps-reviews-scraper
- https://github.com/noworneverev/google-maps-scraper
- Project files: app/gateway/_apify.py, app/budget/_estimate.py, docs/adr/0005-caching-and-budgeting.md, docs/adr/0006-gateway-for-paid-services.md
