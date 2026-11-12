# Domain Docs

How the engineering skills consume this repo's domain documentation. Layout: **single-context** (one glossary and one ADR folder at the repo root).

## Before exploring, read these

- `GLOSSARY.md` at the repo root.
- `docs/adr/`: ADRs that touch the area you are about to work in.
- The [specification](../specification.md) for architecture and module interfaces.

If a file does not exist yet, proceed silently. `/domain-modeling` (reached via `/grill-with-docs`) creates them lazily.

## Use the glossary's vocabulary

Name domain concepts as `GLOSSARY.md` defines them, in issue titles, tests and code. Do not drift to the synonyms listed under `_Avoid_`.

## Flag ADR conflicts

If your output contradicts an ADR, say so explicitly: "Contradicts ADR-0003 (…), but worth reopening because …".
