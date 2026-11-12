# 0003: Jev as the fast model, Claude Haiku as fallback

Status: accepted, 2026-11-12 (pending the Czech evaluation, see below)

## Context

Classification of every Review into Topics and sentiment is bulk work, and prompt-injection detection runs on every Review. Both need a cheap, fast, typed model. Jev 1.14 (TypeSafe) via OpenRouter costs about $0.042 per 1M input tokens with latency around 0.12 s. Whether it handles Czech is not yet verified, and its Decisions API is not OpenAI-compatible.

## Decision

- Fast model: Jev through OpenRouter for classification and injection detection. We do not use Jev Router; routing is in our code (`llm`).
- Fallback: Claude Haiku on error, timeout or invalid output, not on low confidence.
- Strong model: Claude Sonnet, only on aggregated Metrics and bounded samples.
- Go/no-go for Jev: on 50 real Czech Reviews plus about 15 synthetic injections, sentiment agreement at least 80 %, Topics at least 70 %, no injection false negatives. Otherwise Haiku only; the routing table is configuration, so that is a config change.

## Consequences

- The Jev client is an adapter behind the `llm` ports and is replaceable.
- An injection detector error fails closed: the Review is flagged.
- This ADR is revisited when the evaluation (ticket on Jev research) finishes.
