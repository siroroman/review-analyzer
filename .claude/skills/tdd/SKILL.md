---
name: tdd
description: Test-first workflow for this project's Python modules. Use when implementing or changing anything in app/, fixing a bug, or when asked for red-green. Tests go through a module's public interface with fake ports, one failing test per slice, one commit per slice.
---

# TDD for Review Analyzer

Read `docs/agents/testing.md` first, and `GLOSSARY.md` for names.

## Loop

1. **Seam.** Name the public interface under test (`app/<module>/__init__.py`) and what it should do. If it does not exist, write the types and Protocol first.
2. **Red.** One test for one behaviour through that interface. Run it, see it fail for the right reason.
3. **Green.** The minimum code to pass. No speculative features.
4. **Commit** the slice (`feat(<module>): ...`, `Refs #N`). Lint and tests pass.
5. Repeat with the next behaviour. Error paths are slices too: timeout, invalid model output, exceeded Budget, empty input, Flagged review, unknown Review ID.

## Rules

- Never write all tests first and all code after; vertical slices only.
- Never test internals or mock a module's own collaborators. Use the public fakes of ports (`Clock`, LLM port, repositories).
- Expected values from the spec or a literal, never recomputed with the code's formula.
- Never weaken a test to pass. A bug fix starts with a test that reproduces it.
- A path in `docs/agents/critical-paths.md` needs its test in the same PR.
- Narrowest test first (`pytest tests/<module> -k <name>`), the full run once at the end.
