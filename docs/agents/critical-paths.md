# Critical paths

Places where a mistake costs the most. A PR that changes a path below has a **Critical paths touched** section naming the area and the evidence. CI fails when a source glob changes without a change under its test glob (exception: the PR body starts with `> **Warning:**` and a reason).

Whoever adds a module in one of these areas adds or fixes the glob in the same PR. Patterns are shell globs on repository paths.

| Area | Source globs | Test globs | What goes wrong |
| --- | --- | --- | --- |
| Prompt injection and PII | `app/sanitize/**`, `app/insights/**` | `tests/sanitize/**`, `tests/insights/**` | a Review steers the model, personal data is stored or shown |
| Budget | `app/budget/**`, `app/llm/**` | `tests/budget/**`, `tests/llm/**` | a Run or the 30 USD monthly cap is exceeded |
| Grounding | `app/insights/**` | `tests/insights/**` | an Insight cites a non-existent Review ID |
| Numbers and trends | `app/metrics/**` | `tests/metrics/**` | wrong average or Topic share, a false drop |
| Data identity | `app/storage/**`, `app/sources/**` | `tests/storage/**`, `tests/sources/**` | duplicate Reviews, broken cache, a changed `external_id` |

Modules with a 95 % coverage threshold: `metrics`, `sanitize`, `budget`, `llm`.

## Guardrail paths

Files that check or limit agents and PRs. A PR that changes one has a **Guardrails touched** line saying what got stricter and what looser.

```
.claude/**
.githooks/**
.github/**
scripts/**
Makefile
pyproject.toml
importlinter.ini
.coveragerc
CLAUDE.md
docs/agents/critical-paths.md
docs/agents/rules-enforcement.md
```

Repository settings on GitHub (ruleset, secret scanning) are guardrails too but are not in the diff: record a change in [rules-enforcement.md](rules-enforcement.md).
