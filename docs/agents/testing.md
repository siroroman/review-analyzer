# Testing

Tests are part of every module. Read this before writing code. Coverage thresholds and CI steps are in the [specification](../specification.md#ci-coverage-check).

## Order

Interface and types, then a test of the interface, then implementation. A module without tests of its interface is not done. Work in red-green slices: one failing test for one behaviour, the minimum code to pass, one commit per slice.

## What to test

- Call only the public interface in `app/<module>/__init__.py`. Never import `_impl` or test private functions. A test that breaks on a refactor with unchanged behaviour is wrong.
- Expected values come from an independent source (a literal, a worked example, the spec), never from recomputing the code's own formula.
- Cover error paths, not only the happy path: timeout, invalid JSON from a model, exceeded Budget, empty input, a Flagged review, a model response citing a non-existent Review ID.
- Pure modules (`metrics`, `budget`, parts of `sanitize`): no mocks; use property-based tests (Hypothesis) for averages, counts and deduplication.

## Layers

| Layer | Where | Rule |
| --- | --- | --- |
| Unit, per module | `tests/<module>/` | fast, no network, ports replaced by fakes |
| Contract, per adapter | `tests/adapters/` | recorded responses (fixtures), never a live call |
| Integration | `tests/storage/` | real PostgreSQL via testcontainers |
| End to end | `tests/pipeline/` | 1 or 2 whole Runs with fake ports |
| Frontend | next to components | Vitest and Testing Library, API layer mocked |

## Fakes

- A fake lives next to its port and is public, so every module's tests reuse it. Do not mock internal collaborators.
- `Clock` is faked; tests never sleep and never read the real time. Retries and cache TTL are tested by advancing the fake.
- Fakes of the LLM port return scripted responses, including invalid ones.

## Test scope

Which part of the repository is under which tests. CI decides from this table (`scripts/check-test-scope.sh`, workflow `tests.yml`): a job runs only when a changed path matches its row, so a documentation-only PR runs no tests. Whoever adds a code area adds its row and the glob in the script in the same PR.

| Area | Paths | Tests | Tool | Coverage | CI job |
| --- | --- | --- | --- | --- | --- |
| Backend modules | `app/**` | unit, `tests/<module>/` | pytest, Hypothesis, fakes | 90 % overall, 80 % per file, 95 % for `metrics`, `sanitize`, `budget`, `llm`, 90 % of changed lines | `backend` |
| Adapters | `app/**` (adapters) | contract, `tests/adapters/` | pytest, recorded fixtures | as above | `backend` |
| Storage | `app/storage/**` | integration, `tests/storage/` | pytest, testcontainers | as above | `backend` |
| Pipeline | `app/pipeline/**` | end to end, `tests/pipeline/` | pytest, fake ports | as above | `backend` |
| Backend config | `pyproject.toml`, `uv.lock`, `importlinter.ini`, `.coveragerc` | all backend tests | pytest | as above | `backend` |
| Frontend | `web/**` | next to components | Vitest, Testing Library | 80 % | `frontend` |
| Repo scripts and hooks | `scripts/**`, `.githooks/**` | `scripts/test-*.sh` | bash | none | `make test-scripts` (always) |
| Not under tests | `*.md`, `docs/**`, `.claude/**`, `.github/**` | none | | none | none (a change to `tests.yml` still runs `changes` and `tests-passed`) |

Rules:

- A `*.md` file never triggers tests, even inside `app/` or `web/`.
- A path that matches a row but has no project behind it (no `pyproject.toml`, no `web/package.json`) fails the job; it is never silently skipped.
- `tests-passed` is the one check required in the ruleset. It is green when the jobs that had to run passed or were skipped, and red when any failed or was cancelled.
- Per-file and critical-module thresholds are checked by `scripts/check-coverage.sh`, the overall one by `pytest --cov-fail-under`, changed lines by `diff-cover`, the frontend by `coverage.thresholds` in the Vitest config.

## Not in CI

Live contract tests and the evaluation on 100 to 200 hand-labelled Reviews run manually or nightly and do not count toward coverage. CI never calls Apify or a model.

## Coverage

90 % overall (lines and branches), 80 % per file, 95 % for `metrics`, `sanitize`, `budget`, `llm`; diff coverage 90 %. Below the threshold means a path no test runs: write the test, never lower the threshold. Exclusions (tests, migrations, `__main__`) are explicit in the config with a reason.
