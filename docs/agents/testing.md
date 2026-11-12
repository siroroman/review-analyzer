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

## Not in CI

Live contract tests and the evaluation on 100 to 200 hand-labelled Reviews run manually or nightly and do not count toward coverage. CI never calls Apify or a model.

## Coverage

90 % overall (lines and branches), 80 % per file, 95 % for `metrics`, `sanitize`, `budget`, `llm`; diff coverage 90 %. Below the threshold means a path no test runs: write the test, never lower the threshold. Exclusions (tests, migrations, `__main__`) are explicit in the config with a reason.
