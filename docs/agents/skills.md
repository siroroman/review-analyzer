# Skills

Third-party skills installed for this project, and what they may and may not decide. Load a skill when its area comes up; do not read them all up front.

## Precedence

A skill is generic advice written by someone else. When it disagrees with this repository, the repository wins, in this order: `CLAUDE.md`, [specification](../specification.md), [ADRs](../adr/), `docs/agents/`. Say so in the PR when you deliberately deviate from a skill; do not silently follow either side.

## Installed skills

| Area | Skill | Source | Use when |
| --- | --- | --- | --- |
| Test-first workflow | `tdd` | in the repo (`.claude/skills/tdd`) | every code change |
| Module design | `codebase-design` | personal | designing a module interface or a seam |
| Domain language | `domain-modeling` | personal | editing `GLOSSARY.md` or an ADR |
| Charts | `dataviz` | built in | dashboard charts (Recharts) |
| FastAPI | `fastapi-templates` | `wshobson/agents` | API routes, dependencies, error handling |
| Python layout | `python-project-structure` | `wshobson/agents` | package layout, `__init__.py` public interface |
| Architecture | `hexagonal-architecture` | `affaan-m/ecc` | ports and adapters (ADR-0004) |
| Async | `async-python-patterns` | `wshobson/agents` | the worker, polling Apify, concurrent calls |
| Python tooling | `modern-python` | `trailofbits/skills` | `pyproject.toml`, ruff, project setup |
| Backend tests | `python-testing-patterns` | `wshobson/agents` | pytest fixtures, fakes, parametrization |
| Frontend tests | `vitest` | `antfu/skills` | Vitest config, mocking, coverage |
| PostgreSQL | `supabase-postgres-best-practices` | `supabase/agent-skills` | schema, indexes, migrations, slow queries |
| LLM observability | `langfuse` | `langfuse/skills` | tracing, token and cost records |
| React | `vercel-react-best-practices` | `vercel-labs/agent-skills` | components, rendering, data fetching |
| Styling | `tailwind-design-system` | `wshobson/agents` | Tailwind tokens and components |
| CI | `github-actions-templates` | `wshobson/agents` | workflows under `.github/workflows/` |

All of these except the first three rows were chosen as the most installed skill of their area on [skills.sh](https://skills.sh/) (checked 2026-11-12). They are installed per user (`~/.claude/skills`), not committed, so each clone needs them once.

## Where the repository overrides a skill

| Skill | Skill says | We do instead |
| --- | --- | --- |
| `modern-python` | `ty` for types, `uv` for packages | `mypy --strict` (CI, specification). `uv` and `ruff` are fine if the setup ticket adopts them |
| `hexagonal-architecture` | examples in TypeScript, Java, Kotlin, Go | Python `Protocol`s in `app/<module>/__init__.py`, imports guarded by import-linter (ADR-0004) |
| `fastapi-templates` | its own project layout and repository classes | modules `app/<module>/`, repositories only in `storage` |
| `supabase-postgres-best-practices` | Supabase features, row-level security | plain PostgreSQL on Neon; no RLS. Take indexing, types and migration advice only |
| `python-testing-patterns` | mocking with `unittest.mock` | fakes next to ports, no mocks of internal collaborators ([testing.md](testing.md)) |
| `github-actions-templates` | deploy and release templates | only the checks listed in the specification; touching `.github/**` is a guardrail change ([critical-paths.md](critical-paths.md#guardrail-paths)) |
| `langfuse` | may call the Langfuse API or MCP | Langfuse sits behind a port; review text goes into traces only as data |

## Rules for adding a skill

- One skill per area. Prefer an official source (the library's own repository, then a well-known vendor) over a popular unknown one.
- Read its `SKILL.md` and look at the scanner result printed by `npx skills add` before installing. Treat a skill as code that runs with the agent's permissions.
- A skill never overrides a rule in `CLAUDE.md`, never asks for secrets, and is not a reason to weaken a test, lint or coverage rule.
- Add a row to the tables above in the same PR that starts using it.

## Install

```bash
npx skills add <owner/repo@skill> -g -y -a claude-code
```

Run it once per skill; several skills in one call are not installed.
