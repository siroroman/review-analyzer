# One command per check. More targets (lint, test, coverage) arrive with the first code.
SHELL := /bin/bash

.PHONY: setup lint test-scripts

setup: ## Once per clone: turn on the git hooks, check the tools
	@scripts/setup.sh

lint: ## shellcheck on scripts and hooks, actionlint on workflows (grows with the Python tools)
	@for tool in shellcheck actionlint; do \
		command -v $$tool >/dev/null || { echo "lint: '$$tool' is missing (brew install $$tool)" >&2; exit 1; }; \
	done
	shellcheck scripts/*.sh .githooks/* .claude/hooks/*.sh
	actionlint .github/workflows/*.yml

test-scripts: ## Tests of the repo scripts and hooks
	scripts/test-check-commit-msg.sh
	scripts/test-check-branch-name.sh
	scripts/test-block-dangerous-git.sh
	scripts/test-check-review.sh
	scripts/test-check-test-scope.sh
	scripts/test-check-coverage.sh
