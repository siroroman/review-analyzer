# Jev on Czech and the OpenRouter Decisions API

Date read: 2026-11-12. Ticket: #17 (T15), part of #2. Feeds: ADR 0003 (Jev as the fast model, Haiku as fallback).

## Question

1. What are the request and response shapes of the OpenRouter Decisions API (the `llm` adapter for Jev must speak it)?
2. Can Jev classify Czech Reviews (sentiment, Topics) and detect prompt injection well enough to pass the ADR 0003 go/no-go gate (sentiment at least 80 %, Topics at least 70 %, no injection false negatives)?
3. What routing and fallback should the ADR record?

## Answer

- Part 1 is answered below: `POST https://openrouter.ai/api/alpha/decisions`, bearer key, `state` plus named `questions` (types `choice`, `noul`, `score`, `box`), typed answers with probabilities. It is alpha ("the shape may change") and not OpenAI-compatible.
- Part 2 is NOT answered. No primary source states that Jev supports Czech or any non-English language, and none claims injection robustness. The 50-review test needs an OpenRouter key and spending (limit 5 USD), which this agent must not use. Go/no-go is therefore **undecided**, not a go.
- Until the test is run, the safe default is Haiku-only with Jev behind configuration (a config change, per ADR 0003).
- Part 3 (ADR update) is not done here; it depends on the test result.

## Evidence

All fetched 2026-11-12.

### Decisions API shape ([API reference](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request.md))

- Endpoint `POST https://openrouter.ai/api/alpha/decisions`, `Authorization: Bearer <key>`, JSON. Marked alpha.
- Request: `model` (required, e.g. `typesafe/jev-1.13`), `state` (required: string, object or array; media parts go here), `questions` (required: map of name to question). Optional: `assets`, `provider` (routing preferences), `session_id`, `trace`, `user`.
- Question types by `type`: `noul` (yes/no, optional `criteria` with `true`/`false` guidance), `choice` (required `criteria` map option to guidance), `score` (ordered `criteria` array), `box` (image only, TypeSafe Jev only).
- Response: `model`, `answers` (required), `usage` (required). `answers[name]` is typed: `choice` gives the option plus `confidence` and `probabilities`; `noul` gives a number plus `confidence`; `score` gives a number, probabilities, `legend`; `refusal` means the provider declined that question while other answers may still be present. `usage` has `input_tokens`, `output_tokens`, `cost`.
- Errors: 400, 401, 402, 403, 404, 413, 429, 500, 502, 503, 524, 529; no numeric rate or size limits documented.
- Typed text/number fields go to a different endpoint (`/api/alpha/extractions`), not this one.

### Jev guide ([Jev on OpenRouter](https://openrouter.ai/docs/guides/community/jev.md))

- Returns typed answers and probabilities, no reasoning. "Not a drop-in replacement for a chat model."
- Context 262,144 tokens; text over about 32,000 bytes runs in a slower, less accurate long-context mode (a Review batch should stay well below that).
- Page does not mention Czech or any language, and has no prompt injection section.
- Suggests cascades (cheap model, Jev verifies, stronger model on failure) and human routing for low confidence; switching model changes probabilities, so thresholds need recalibration.

### Classification recipe ([cookbook](https://openrouter.ai/docs/cookbook/evaluate-and-optimize/jev-classification.md))

- One `choice` question for an exclusive category (add an `other` option); one `noul` question per tag for multi-label. This maps to sentiment as `choice` and each Topic as `noul`, or a `choice` over the taxonomy.
- Calibrate per-tag thresholds on 100 to 200 hand-labelled items. Example is English tweets only.
- Retry on 429, 5xx and in-flight-budget 402; honor `Retry-After`; backoff from 1 s doubling to 30 s with jitter; 60 s timeout; do not retry other 402 or 400.
- Price quoted $0.042 per 1M input tokens, output free; about $0.026 per 1,000 items at about 610 input tokens each. Matches ADR 0003. Cost of the 50-review test would be a fraction of a cent, well inside the 5 USD cap.

### Vendor page ([TypeSafe announcement](https://typesafe.ai/blog/introducing-system-one-models-and-jev))

- Does not state language support, training data, public benchmark results, or injection robustness. It mentions detecting jailbreaks as a use case (Jev as a detector), which is not evidence of accuracy.

### Model name discrepancy

Search results list `typesafe/jev-1.13`, `jev-1.14` (dated 20261014) and an alias `~typesafe/jev-latest`. The API page and cookbook examples use `jev-1.13`; the Jev guide says Box needs 1.14. The OpenRouter model page URL for 1.14 returned 404 for me, so I could not read its current price or modalities. ADR 0003 pins 1.14.

## Not verified

- Czech accuracy, failure types, and injection detection: no test run (needs an OpenRouter key and up to 5 USD; owner must provide it). Acceptance criterion 2 is open.
- Whether 1.14 serves `choice`/`noul` exactly like 1.13 and its current price (model page 404).
- Rate limits, payload size limit, and whether the alpha shape has changed since the pages were published.
- Whether `/api/v1/systemone` is a stable alternative to the alpha path.
- No source tells how Jev treats instructions embedded in `state`. Reviews stay in `state` (data), but this must be tested with the synthetic injections.

## Recommendation

Do not mark Jev "go" yet. The owner should supply a test key (limit 5 USD) so a follow-up session can run the ADR 0003 evaluation: 50 real Czech Reviews hand-labelled plus about 15 synthetic injections, using one `choice` for sentiment, `noul` per Topic, and one `noul` for injection, via a thin adapter behind the `llm` port that handles `refusal` answers and the retry rules above. Until then keep Haiku as the working default, with Jev as a configurable route, and pin the model ID in configuration because the API is alpha. Also decide whether to pin `jev-1.14` or `jev-1.13`. Once results exist, ADR 0003 should be updated with the outcome (acceptance criterion 3). This note leaves ADR 0003 unchanged.
