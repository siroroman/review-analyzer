# 0001: Python and FastAPI backend on Cloud Run

Status: accepted, 2026-11-12

## Context

The backend scrapes, calls models and validates their output. It needs the best AI ecosystem, typed validation of LLM output, and cheap hosting that scales to zero and is easy to demo. Kotlin with Ktor was considered.

## Decision

Python with FastAPI and Pydantic. API and worker are one Docker image, deployed on Google Cloud Run. Pydantic validates both HTTP input and LLM output.

## Consequences

- `mypy --strict`, `ruff` and `import-linter` carry the quality bar that a compiler would carry in Kotlin.
- One image means API and worker share code and versions; they differ only by entry point.
- Switching language later would mean rewriting every module; the ports (ADR-0004) limit that to adapters only for external services.
