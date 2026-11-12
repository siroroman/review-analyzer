# Skills

Third-party skills installed for this project, and what they may and may not decide. Load a skill when its area comes up; do not read them all up front.

## Precedence

A skill is generic advice written by someone else. When it disagrees with this repository, the repository wins, in this order: `CLAUDE.md`, [specification](../specification.md), [ADRs](../adr/), `docs/agents/`. Say so in the PR when you deliberately deviate from a skill; do not silently follow either side.

## Installed skills

| Area | Skill | Source | Use when |
| --- | --- | --- | --- |
| Test-first workflow | `tdd` | in the repo (`.claude/skills/tdd`) | every code change |
| Module design | `codebase-design` | `mattpocock/skills` | designing a module interface or a seam |
| Domain language | `domain-modeling` | `mattpocock/skills` | editing `GLOSSARY.md` or an ADR |
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

All rows from `fastapi-templates` down were chosen as the most installed skill of their area on [skills.sh](https://skills.sh/) (checked 2026-11-12). They are installed per user (`~/.claude/skills`), not committed or pinned, so each clone needs them once and a skill can change under us. Where the repo has its own copy (`tdd`), the repo copy wins over a user-level one of the same name.

Skills are advice. They never grant an agent access to live services: see the `langfuse` row below.

## Skills for a review

The `code-reviewer` agent sorts the changed files by this table, loads every skill whose row matches and judges that part of the diff against it. It names them on the `Skills:` line of its review (CI requires the line). A file that matches no row is judged against the repo docs only. The skills of the install table above apply as written; this table only says which ones a reviewer opens for which paths.

| Changed paths | Skills |
| --- | --- |
| every diff | `code-review` (the Standards and the Spec axes, done by the reviewer itself) |
| `app/<module>/__init__.py`, new modules, ports | `codebase-design`, `hexagonal-architecture` |
| `app/api/**` | `fastapi-templates` |
| `app/worker/**`, `app/pipeline/**`, anything `async` | `async-python-patterns` |
| `app/storage/**`, migrations, SQL | `supabase-postgres-best-practices` |
| `app/llm/**`, `app/insights/**`, tracing code | `langfuse` (documentation only, see the override table) |
| `tests/**` (Python) | `python-testing-patterns`, `tdd` |
| `pyproject.toml`, ruff, mypy, package layout | `modern-python`, `python-project-structure` |
| `web/**` components, hooks, data fetching | `vercel-react-best-practices` |
| `web/**` styles, Tailwind config | `tailwind-design-system` |
| `web/**` tests | `vitest` |
| `.github/workflows/**` | `github-actions-templates` |
| `GLOSSARY.md`, `docs/adr/**` | `domain-modeling` |

Add a row in the same PR that adds a skill or a new area of the code.

## Where the repository overrides a skill

| Skill | Skill says | We do instead |
| --- | --- | --- |
| `modern-python` | `ty` for types, `uv` for packages | `mypy --strict` (CI, specification). `uv` and `ruff` are fine if the setup ticket adopts them |
| `hexagonal-architecture` | examples in TypeScript, Java, Kotlin, Go | Python `Protocol`s in `app/<module>/__init__.py`, imports guarded by import-linter (ADR-0004) |
| `fastapi-templates` | its own project layout and repository classes | modules `app/<module>/`, repositories only in `storage` |
| `supabase-postgres-best-practices` | Supabase features, row-level security | plain PostgreSQL on Neon; no RLS. Take indexing, types and migration advice only |
| `python-testing-patterns` | mocking with `unittest.mock` | fakes next to ports, no mocks of internal collaborators ([testing.md](testing.md)) |
| `github-actions-templates` | deploy and release templates | only the checks listed in the specification; touching `.github/**` is a guardrail change ([critical-paths.md](critical-paths.md#guardrail-paths)) |
| `langfuse` | its header pre-approves `curl *langfuse.com/*`, `npx langfuse-cli api * list/get` and WebFetch, and it says to run even when Langfuse is not configured | use it for documentation and instrumentation advice only. An agent never queries a real Langfuse project: traces hold Review text, which is untrusted and may contain personal data. Langfuse sits behind a port in code |

## Rules for adding a skill

- One skill per area. Prefer an official source (the library's own repository, then a well-known vendor) over a popular unknown one.
- Read its `SKILL.md` and look at the scanner result printed by `npx skills add` before installing. Treat a skill as code that runs with the agent's permissions. Check the frontmatter for `allowed-tools` or hooks: they pre-approve actions without a prompt, and each one needs a row in the override table.
- A skill never overrides a rule in `CLAUDE.md`, never asks for secrets, and is not a reason to weaken a test, lint or coverage rule.
- Add a row to the tables above in the same PR that starts using it.

## Install

```bash
npx skills add <owner/repo@skill> -g -y -a claude-code
```

Run it once per skill. When several skills were passed in one call, only the first was installed in our test (cause not investigated).
