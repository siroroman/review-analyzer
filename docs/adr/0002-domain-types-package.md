# 0002: A shared `domain` types package

Status: accepted, 2026-11-12

## Context

Every module speaks about Review, Place, Topic and so on. If each module defines its own, they drift and need converters. If modules import each other's types, boundaries blur.

## Decision

`app/domain/` holds the shared vocabulary as Pydantic types and small ports that have no external service behind them (`Clock`). It names things exactly as `GLOSSARY.md` does. It has no I/O and imports nothing from other `app/` modules. Every module may import `domain`; `domain` imports no one.

## Consequences

- A rename in the glossary is a rename in `domain` first.
- Types serialize to and from JSON, so they can cross the queue and the database unchanged.
- `domain` must stay small: behaviour that belongs to one module lives in that module, not here.
