# 0004: Deep modules, ports and enforced boundaries

Status: accepted, 2026-11-12

## Context

Agents write most of the code. Without enforced boundaries, internals leak, tests couple to implementation and a model provider ends up hard-coded in business logic.

## Decision

- Each module is a package `app/<module>/` whose public interface (Protocols and Pydantic types) is in `__init__.py`. Everything else is internal and must not be imported from outside.
- Dependencies go one way: `api`/`worker` -> `pipeline` -> domain modules -> ports. No cycles.
- Apify, OpenRouter, Anthropic, Google Places, ARES, Langfuse and the database are reached only through ports. Adapters are thin; tests use fakes.
- Numbers and trends are pure functions. I/O stays at the edge.
- `import-linter` enforces this in CI. Time and randomness come from ports; lint bans `datetime.now`, `time.sleep` and `random` in `app/`.

## Consequences

- A module is tested through its interface only, so its implementation can be rewritten without touching tests.
- A new external service means a new port and an adapter, never a direct import.
- The boundary config is a guardrail path: changing it needs a **Guardrails touched** line.
