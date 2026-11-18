# 0009: Every model call goes through OpenRouter, no Anthropic model

Status: accepted, 2026-11-18. Supersedes the Haiku fallback and the strong model of [0003](0003-jev-fast-model-with-haiku-fallback.md) and the choice of Sonnet for the industry in [0007](0007-infer-industry-with-strong-model.md).

## Context

The Taxonomy, the industry and the insights were made by Claude Sonnet and Haiku through the Anthropic API, Jev's assignment fell back to Haiku, and OpenRouter served only Jev. The owner wants every model call through OpenRouter and no Anthropic model at all (#134).

## Decision

- **Topics, industry and insights**: DeepSeek V4.1 Flash (`deepseek/deepseek-v4.1-flash`) through the OpenRouter chat completions API, service `openrouter_chat`, operation `complete`. The answer is JSON for the schema of the task, validated by `llm` (one repair, then rejected). The grounding check of `insights` is unchanged.
- **Assignment of Topics**: Jev (`typesafe/jev-1.14`) through the OpenRouter Decisions API, service `openrouter`, for every Review with text of the Run. There is no fallback: when a call fails, the Review is `unclassified`.
- **Jev takes one Review per call.** The Decisions API answers typed questions, not a list, so the schema of a Review asks a score (0 to 1) and a sentiment for every Topic of the Taxonomy. A Topic with a score from 0.5 up is assigned, the best three at most; the score is the confidence. This replaces the batch of 20 Reviews of the earlier design, which Jev could not answer.
- **Sample of the Taxonomy and of the industry**: at most 200 random Reviews with text, never Flagged. The randomness comes from an injected `RandomSource` (a seeded one in tests), so a fixed seed gives the same sample. Reviews without text stay in the Run for rating, counts and TrendPoints; only the sample is restricted.
- **Topics**: at most 9, in Czech (`name` and `description`), `key` an English slug. The Topic `unclassified`, added by code, is named "Nezařazeno".
- **The industry** is inferred by DeepSeek on the same kind of sample (Sonnet before). Its label stays a short lowercase English key.
- One API key, `OPENROUTER_API_KEY`, for both services. `ANTHROPIC_API_KEY`, the Anthropic adapter and its price rows are gone.
- `llm` keeps its generic `Route.fallback`, but no route of the product uses it.

## Consequences

- Money: the price of DeepSeek V4.1 Flash on OpenRouter varies by provider (about $0.05 to $3 per million input tokens). The table in `app/budget/_estimate.py` holds a mid placeholder ($0.30 in, $1.20 out) to be checked before the first paid Run. Jev costs a call per Review, a few cents per 1000 Reviews.
- Quality: Jev is now the only model for the assignment, so the check on real Czech Reviews that ADR 0003 asks for decides on it with no model to fall back to. Review-level latency grows, because the calls are sequential.
- Existing frozen Taxonomies (English names, made by Sonnet) are kept until a new industry appears; they are not regenerated.
- The DeepSeek adapter has hand-written fixtures, not a recording; it needs a real recording once a key is at hand.
- Touches critical paths: `llm`, `gateway`, `budget`, the taxonomy and classification prompts, `insights` (prompt injection and grounding).

## Contradictions with earlier ADRs

[0003](0003-jev-fast-model-with-haiku-fallback.md): the fallback to Haiku and the strong model Sonnet are replaced; Jev stays the fast model. [0007](0007-infer-industry-with-strong-model.md): the industry is inferred by DeepSeek, not Sonnet; everything else in it stands.
