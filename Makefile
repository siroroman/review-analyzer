# One command per check. `make lint` and `make test` need uv (brew install uv); `uv sync` runs on first use.
SHELL := /bin/bash

.PHONY: setup lint test coverage test-scripts

setup: ## Once per clone: turn on the git hooks, check the tools
	@scripts/setup.sh

lint: ## shellcheck, actionlint, then ruff, mypy --strict and import-linter on the Python code
	@for tool in shellcheck actionlint; do \
		command -v $$tool >/dev/null || { echo "lint: '$$tool' is missing (brew install $$tool)" >&2; exit 1; }; \
	done
	shellcheck scripts/*.sh .githooks/* .claude/hooks/*.sh
	actionlint .github/workflows/*.yml
	@command -v uv >/dev/null || { echo "lint: 'uv' is missing (brew install uv)" >&2; exit 1; }
	uv run --frozen ruff check .
	uv run --frozen ruff format --check .
	uv run --frozen mypy
	uv run --frozen lint-imports --config importlinter.ini

test: ## Python tests (fast, no network)
	uv run --frozen pytest

coverage: ## Tests with the overall 90 % threshold, then the per-file and critical-module ones
	uv run --frozen pytest --cov=app --cov-branch --cov-fail-under=90 --cov-report=term-missing --cov-report=json
	jq . coverage.json | scripts/check-coverage.sh

test-scripts: ## Tests of the repo scripts and hooks
	scripts/test-check-commit-msg.sh
	scripts/test-check-branch-name.sh
	scripts/test-block-dangerous-git.sh
	scripts/test-check-review.sh
	scripts/test-check-test-scope.sh
	scripts/test-check-coverage.sh
