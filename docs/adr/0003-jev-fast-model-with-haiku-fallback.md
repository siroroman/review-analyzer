# 0003: Jev as the fast model, Claude Haiku as fallback

Status: accepted, 2026-11-12. Jev confirmed by the owner on 2026-11-12 after an orientation test; formal check on real Czech Reviews still to do (see below)

## Context

Classification of every Review into Topics and sentiment is bulk work, and prompt-injection detection runs on every Review. Both need a cheap, fast, typed model. Jev 1.14 (TypeSafe) via OpenRouter costs about $0.042 per 1M input tokens with latency around 0.12 s. An orientation test on synthetic Czech Reviews passed (see `docs/research/jev-czech-and-decisions-api.md`), and its Decisions API is not OpenAI-compatible.

## Decision

- Fast model: Jev through OpenRouter for classification and injection detection. We do not use Jev Router; routing is in our code (`llm`).
- Fallback: Claude Haiku on error, timeout or invalid output, not on low confidence.
- Strong model: Claude Sonnet, only on aggregated Metrics and bounded samples.
- Jev is used. The owner decided this on 2026-11-12 from an outside source and an orientation test on synthetic Reviews (sentiment 98 %, Topics 88 %, 10 of 10 injections flagged). If real data does not meet the thresholds below, Jev is replaced by Haiku.
- Go/no-go gate for Jev, to be checked on real data: on 50 real Czech Reviews plus about 15 synthetic injections, sentiment agreement at least 80 %, Topics at least 70 %, no injection false negatives. Otherwise Haiku only; the routing table is configuration, so that is a config change.

## Consequences

- The Jev client is an adapter behind the `llm` ports and is replaceable.
- An injection detector error fails closed: the Review is flagged.
- This ADR is revisited when Jev is checked on real Czech Reviews. Until then the model version is pinned in configuration (1.13 tested, 1.14 named here) because the Decisions API is alpha.
