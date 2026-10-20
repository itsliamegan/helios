test:
	#!/usr/bin/env bash
	status=0
	for package in packages/*/; do
		(cd "$package" && uv run luna test) || status=1
	done
	exit $status

lint:
	uv run ruff format
	uv run ruff check --fix

check:
	uv run ty check
