# One command per check. More targets (lint, test, coverage) arrive with the first code.
SHELL := /bin/bash

.PHONY: setup test-scripts

setup: ## Once per clone: turn on the git hooks, check the tools
	@scripts/setup.sh

test-scripts: ## Tests of the repo scripts and hooks
	scripts/test-check-commit-msg.sh
	scripts/test-check-branch-name.sh
	scripts/test-block-dangerous-git.sh
	scripts/test-check-review.sh
	scripts/test-check-test-scope.sh
	scripts/test-check-coverage.sh
