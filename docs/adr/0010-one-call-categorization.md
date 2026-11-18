# 0010: Topics and their assignment in one DeepSeek call

Status: accepted, 2026-11-18. Supersedes the assignment of Topics by Jev (one call per Review) in [0003](0003-jev-fast-model-with-haiku-fallback.md) and [0009](0009-openrouter-for-every-model-call.md), and the sample of the Taxonomy in [0009](0009-openrouter-for-every-model-call.md). Keeps [0005](0005-caching-and-budgeting.md) (only Reviews without a ReviewTopic are classified) and [0007](0007-infer-industry-with-strong-model.md) (one frozen Taxonomy per industry).

## Context

Assigning Topics with Jev took one sequential call per Review and stalled after about 200 Reviews (#137). The Taxonomy came from a sample of 200 Reviews, so it never saw the rest.

## Decision

- The `Categorizer` (module `classification`, task `categorization`, DeepSeek V4.1 Flash through `openrouter_chat`) sorts the Reviews with text of a Company in one call, numbered, between `<reviews>` delimiters.
- **First Run of an industry** (no Taxonomy stored): the model finds at most 9 Topics with Czech names and puts each Review into one of them. The Topics are stored as version 1 of the industry's Taxonomy and frozen.
- **Later Runs, and other Companies of the industry**: the stored Topics go into the prompt (inside `<topics>` delimiters) and the model only assigns. Only Reviews without a ReviewTopic are sent, so a redelivered Run calls nothing and no Company changes the Topics of another.
- A Review is in one Topic or `unclassified`. Unknown numbers and unknown keys are dropped. The sentiment comes from the star rating (4-5 positive, 3 neutral, 1-2 negative) and the confidence is 1 (0 for `unclassified`); the model does not rate sentiment.
- At most 2000 of the newest Reviews go in one call, each text cut to 600 characters; the rest wait for the next Run.
- DeepSeek reasoning is off (`reasoning.enabled = false`): with it on, a live Run on 674 Reviews spent all 16384 output tokens thinking and returned no answer. The client's output limit is 12288 tokens and its timeout 300 s; the Budget reserves the output limit before every call.
- Jev and the per-Review `Classifier` stay in the code as the path used when no `Categorizer` is wired; the product wires the `Categorizer`.

## Consequences

- Speed and money: a live Run of 674 Reviews took about 27 s for two DeepSeek calls (categorization 0.016 USD).
- Quality: the Topics of the first Company define the industry's Topics; a skewed first sample skews later Companies. A live Run gave two Topics holding 95 % of the Reviews; prompt tuning is a separate ticket.
- One Topic per Review, sentiment from the rating: coarser than Jev's scores per Topic. The evaluation harness (`make evaluate`) still measures the Jev `Classifier`, not the `Categorizer`; evaluating the `Categorizer` is a separate ticket.
- Touches critical paths: `llm`, `gateway`, `classification` prompts (prompt injection: Review text and Topic text only inside delimiters).
