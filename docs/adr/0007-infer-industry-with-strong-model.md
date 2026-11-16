# 0007: The industry of a Run is inferred, not entered

Status: accepted, 2026-11-16. Changes the decision "Topic taxonomy: generated per industry" in the specification: the industry is still the key of a Taxonomy, but the user no longer enters it.

## Context

The Dashboard design has no "Obor" (industry) field: the user only picks a Place. `POST /runs` required `industry` and the Taxonomy is generated once and frozen per industry, so something has to name the industry. The owner tested the local run on 2026-11-16 and decided how.

## Decision

- The strong model (Sonnet, task `industry`) infers the industry from a bounded sample of the downloaded Reviews and returns a short label. It runs in the pipeline after the download and before the Taxonomy step.
- The sample holds at most 100 Reviews, each cut to 300 characters, Flagged Reviews left out, and goes between `<reviews>` delimiters as a JSON array of strings. Review text is data, never instructions.
- The label is validated by a Pydantic schema (lowercase key, at most 40 characters). An invalid answer is repaired once by `llm`, then rejected.
- The call goes through `llm` and the `gateway`: it counts in the Run's cost and the Budget and is logged in the Call log like any other model call.
- The label only selects a Taxonomy: an industry that already has a frozen Taxonomy reuses it, a new one generates it as before. Topics may differ between Companies of the same real industry; no exact match is needed.
- Failure (model error, invalid output, fewer than `MIN_SAMPLE` usable Reviews) does not fail the Run. It continues with the generic industry key `general` and a generic Taxonomy, and the result carries the note `industry_fallback`. A generic industry is inferred again by a later Run. An exceeded Budget or a denied call ends the Run as `partial`, as for any step.
- The Run records the industry it used, so its notes and Topics stay the same when a later Run infers a real industry for the Company (migration `0005`).
- A Company is stored without an industry (`industry` is nullable) and gets it when inferred. The same set of Places is still the same Company. `POST /runs` takes `place_ids` only; the Company is named after its first Place.

Rejected: the industry from the Google Places type, one generic Taxonomy for everyone, topics per Company without an industry.

## Consequences

- One more Sonnet call per new Company, on at most 100 short texts: a small fraction of the Run cap. A Company with a real industry is never inferred again.
- The industry labels of two Companies in one real industry can differ ("cafe" and "coffee-shop") and then get separate Taxonomies. This is accepted.
- The generic Taxonomy is generated once from the Reviews of the first Company that falls back, then frozen for every later fallback. With fewer than `MIN_SAMPLE` Reviews and no generic Taxonomy yet, the Run ends as `partial`.
- A Company stored with an industry before this change keeps it and is never inferred again.
- `RunResult` and `GET /runs/{id}/result` gain `notes`. The Dashboard says when the generic Taxonomy was used.
- Touches critical paths: `llm` and `gateway` (a new paid task), `api`, `storage` (migrations `0004`, `0005`).

## Contradictions with earlier ADRs

None. [0003](0003-jev-fast-model-with-haiku-fallback.md) allows the strong model on bounded samples; this is one. [0005](0005-caching-and-budgeting.md) caps stay unchanged.
