# Firmy.cz, branch discovery and recorded Apify outputs

Date read: 2026-11-13. Ticket: #16 (T14). Feeds: the Source list in `docs/specification.md` (Firmy.cz row and the "Review dates" row), and the `sources` and `places` modules.

Desk research from primary sources, then a real run by the owner on 2026-11-13 (see Run results). What is still open is listed under Not verified.

## Question

1. Do [jupri/firmy](https://apify.com/jupri/firmy) and [oodoow/mapy-com-ppe](https://apify.com/oodoow/mapy-com-ppe) return a Review date, a review ID and more than 3 Reviews per Place? Do the Firmy.cz terms of use allow it (go/no-go)?
2. Do older dates from compass/google-maps-reviews-scraper match Google Maps?
3. Which method finds the branches of a Company (Google Places text search by name, user confirmation), and how precise is it on 3 real companies?
4. Anonymized fixtures of real outputs for both Sources.
5. Apify spending limit (the owner already set it) and the spec's Source list.

## Answer

- Firmy.cz actors: the actor pages document no review record (date, ID). The real run shows that oodoow/mapy-com-ppe returns the Firmy.cz profiles (same Place id) with all Reviews and an ISO date, but no review ID and a 0-100 rating. jupri/firmy was not run. Whether Firmy.cz may be a Source stays **open** (terms not read).
- Terms of use: I could not read the operative Czech terms ("Podmínky využívání služby Firmy.cz"; the URL I guessed returned 404). The English terms page I could read has no scraping clause, and `robots.txt` on firmy.cz disallows everything for unlisted crawlers (including ours). Go/no-go therefore stays **open for the owner**; until it is read, treat Firmy.cz as "not cleared".
- Google Maps side is well documented: compass returns `publishedAtDate` (ISO), `reviewId` always, and filter `reviewsStartDate`. The real run did not prove the exactness of old dates (see Run results).
- Branch discovery: Places (New) Text Search is documented (up to 20 per page, 60 in total, field mask required). Measured on 3 real companies in the run (see Run results).
- Fixtures and precision numbers are recorded under Run results; recall and old-date exactness are not measured.

## Run results (owner runs, 2026-11-13)

Three Places: Globus Hypermarket Praha-Čakovice (Firmy.cz 193554), Camp Velo Vratěnín (13502193), U Bílého Anděla Nový Jičín (13337502). Raw outputs are kept outside the repo (personal data); only anonymized fixtures are committed.

- **oodoow/mapy-com-ppe**: the Place `id` equals the Firmy.cz detail ID in all three URLs, so Mapy.com serves the Firmy.cz profiles and Reviews. It returns **all** Reviews, not 3 (329, 241 and 165; `reviewCount` equals the number returned). Each Review has `date` (ISO, day precision, always `+01:00` offset, also for summer dates), `rating`, `text`, `reviewer`, `originalLanguage`. Dates reach back at least to 2024. **No Review ID.** One run returns the same Place up to 3 times (Globus: 3 times an unrelated e-shop `Globusonline.cz`; U Bílého Anděla: 3 times the same Place), so deduplicate by Place `id`.
- **jupri/firmy**: not run. The Actor requires full access to the Apify account; the owner declined to approve it on the main account. Not needed, since Mapy.com returns the same profiles.
- **compass/google-maps-reviews-scraper**: 20 Reviews per Place requested, 20 returned each. `reviewId` present and unique in all 60, `publishedAtDate` ISO with milliseconds, `publishAt` relative Czech text, `placeId`, `stars`, `text`, `language`. Empty `text`: 18 of 20 (Globus), 2 (Camp Velo), 4 (U Bílého Anděla). The run reached back only to July 2026, and `publishedAtDate` carries milliseconds (for example `...09:46:30.439Z`), so it is probably computed from the relative text: **exactness of old dates is still unproven**.
- **Text Search** (`textQuery` = name, `regionCode` CZ, `languageCode` cs): Globus returned 15 results, of which 5 are Globus hypermarkets (4 in Prague, 1 in Trmice); the rest are Globus Fresh, restaurants and petrol stations of the same chain, or unrelated Places. Precision for hypermarkets is about 5/15, so user confirmation is required. Camp Velo and U Bílého Anděla returned exactly 1 correct Place each. Recall for Globus was not measured (no official branch list compared).

Mapping to `RawReview` (`app/domain/_reviews.py`): Google Maps gives every field. Mapy.com differs in two fields: it has no `external_id` (the adapter derives it as a hash of `date`, `reviewer` and `text`; the reviewer name is used only for the hash and never reaches `Review`), and its `rating` is on a **0-100 scale** (the fixture has 100, 90 and 40; the Place rating is 4.9). `Rating` accepts only whole numbers 1 to 5, so the adapter must convert, for example `round(rating / 20)` clamped to 1..5; the rule needs a test in #19 or its successor.

Fixtures: `tests/fixtures/sources/google_maps/2026-11-13-camp-velo.json` (20 Reviews, 2 empty), `tests/fixtures/sources/mapy_com/2026-11-13-camp-velo.json` (12 Reviews, 1 empty), `tests/fixtures/places/2026-11-13-text-search-globus.json` (15 Places, business data only). Reviewer names and texts are replaced by placeholders.

## Evidence

### jupri/firmy ([actor page](https://apify.com/jupri/firmy), [API tab](https://apify.com/jupri/firmy/api)), read 2026-11-13

- Output is a business record (`title`, `address`, `phone`, `url`, `stars`, `review_count`, `average_review_percentage`, GPS, hours, images). The sample shows no review-level entries.
- Inputs include `query` (term, URL or listing ID), `review_num` ("number of reviews to fetch"), `review_sort`, `limit`, `include_detail`. The README mentions a `/reviews` query format. No maximum for `review_num` and no cap of 3 stated.
- Pay per usage, no per-result price on the page.
- Review date and review ID: **not documented**.

### oodoow/mapy-com-ppe ([actor page](https://apify.com/oodoow/mapy-com-ppe), [API tab](https://apify.com/oodoow/mapy-com-ppe/api)), read 2026-11-13

- Searches `query` plus `city` (both required) on Mapy.com. `scrapeReviews` (default true) scrapes reviews for each place; `translateReviews` (default true, set it to false for Czech text); `maxResults`.
- Pay per event from $1.50 per 1,000 points of interest.
- Review date and review ID: **not documented**; the output schema only says "ratings, and reviews". The spec dropped Mapy.com only as an autocomplete source. The pages do not say the Reviews come from Firmy.cz profiles; the real run shows they do (same Place id).
- The place is found by query and city, not by Firmy.cz ID, so matching a branch needs a name plus address match.

### Firmy.cz terms of use, read 2026-11-13

- [English terms page](https://napoveda.firmy.cz/en-terms-of-service/): six unnumbered paragraphs about profile content; nothing on automated access, copying or database rights. Its menu points to "Podmínky využívání služby Firmy.cz" and "Smluvní podmínky" (archived version "valid until 15. 7. 2025"), which I could not open by URL.
- [Rules for reviews](https://napoveda.firmy.cz/evaluation-of-firms/): moderation, and the rating algorithm uses the age of each review; no statement on reuse of review text or on how many reviews a visitor sees.
- [robots.txt](https://www.firmy.cz/robots.txt): the catch-all `User-agent: *` is `Disallow: /`; the named AI crawlers (including ClaudeBot) have partial blocks. This is not a licence either way, but a scraper that ignores it is a risk to flag to the owner.
- [Seznam legal information](https://o-seznam.cz/pravni-informace/) lists no Firmy.cz terms. The [Seznam AI Assistant terms](https://o-seznam.cz/napoveda/seznam-ai/podminky-pro-pouzivani-seznam-ai/) forbid automated data collection, but that applies to that service only (as reported by search, not read in full by me).
- Conclusion: the clause that would decide go/no-go was not found. I do not state "allowed".

### Google Maps side ([compass actor page](https://apify.com/compass/google-maps-reviews-scraper)), read 2026-11-13

- `publishedAtDate` ISO timestamp; `publishAt` is relative text; `reviewId` always present; `reviewsStartDate` accepts absolute or relative dates and needs sorting "Newest", otherwise the actor may stop early. Inputs `placeIds` (`ChIJ...`) and `startUrls`. From $0.30 per 1,000 reviews. This matches the spec.
- Whether older dates are exact (for example a review "3 years ago" shown by Google Maps) is not stated on the page.

### Google Places (New) Text Search ([docs](https://developers.google.com/maps/documentation/places/web-service/text-search)), read 2026-11-13

- `POST https://places.googleapis.com/v1/places:searchText`, field mask required (`X-Goog-FieldMask`).
- `places.id` alone is the cheapest SKU (Essentials ID Only); `displayName`, `formattedAddress`, `location` are Pro; `rating` and `userRatingCount` are Enterprise.
- `pageSize` 1 to 20, at most 60 results over pages via `nextPageToken` (other parameters must be identical).
- Implication for branches: a chain with more than 60 branches in a country cannot be listed by one query; use `locationBias`/`locationRestriction` or several queries. The docs do not say how to rank exact-name matches.

## Still needs a human run

1. **Terms**: read "Podmínky využívání služby Firmy.cz" and "Smluvní podmínky" (version in force) in the Firmy.cz footer, search for "automat", "robot", "databáze", "kopírov", note the clause numbers and state go/no-go here.
2. **Compass dates**: for a Place with many Reviews run compass with newest sorting and `maxReviews` 300; compare 10 Reviews older than 2 years with Google Maps (reviewer and text) and record how many `publishedAtDate` values match the relative age.
3. **Branch discovery recall**: compare the Globus Text Search result with the official branch list; add 2 more chains (for example a pharmacy chain and a bank) and a table (company, returned, correct, precision, recall).

## Not verified

- Operative Firmy.cz terms (Czech page not reachable) and so the go/no-go. **Still open for the owner.**
- jupri/firmy (full-account permission, not run).
- Compass date exactness for old Reviews (the run reached back only to July 2026).
- Recall of branch discovery for Globus (no official branch list compared); precision measured on one chain only.
- Apify spending limit (account setting).

## Recommendation

Do not mark Firmy.cz as a decided Source yet. In the spec, keep Firmy.cz as "candidate, blocked by the terms of use" (technically feasible through oodoow/mapy-com-ppe), and make Google Maps (compass, documented `publishedAtDate` and `reviewId`) the only committed Source for the first release; the `sources` port should keep Source-specific field mapping so a second Source can be added later. After the owner reads the Firmy.cz terms, decide: if the terms forbid automated access, drop Firmy.cz (or ask Seznam about permission) and update the Source list and the "Firmy.cz" and "Review dates" decision rows in `docs/specification.md`. Branch discovery should be implemented as text search with the minimal field mask plus user confirmation (which the `places` module in #20 already assumes), and its recall measured (step 3 above) before it is called reliable. No ADR is changed yet; an ADR would be needed only if Firmy.cz is dropped as a Source.
