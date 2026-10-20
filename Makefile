.PHONY: help lint format check test pre-commit-install

help:
	@echo "Available make commands:"
	@echo "  make lint               - Run Ruff linter"
	@echo "  make format             - Auto-format code and fix lint issues with Ruff"
	@echo "  make check              - Check linting and formatting without making changes"
	@echo "  make test               - Run test suite with pytest"
	@echo "  make pre-commit-install - Install pre-commit git hooks"

lint:
	uv run ruff check .

format:
	uv run ruff check --fix .
	uv run ruff format .

check:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest -v

pre-commit-install:
	uv run pre-commit install
