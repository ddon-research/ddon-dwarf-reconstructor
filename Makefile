# Makefile for DDON DWARF Reconstructor
# 
# Common development tasks for testing, linting, and CI/CD

.PHONY: help install test test-unit test-integration test-all coverage lint format type-check clean ci

# Default target
help:
	@echo "Available targets:"
	@echo "  install        - Install dependencies"
	@echo "  test           - Run unit tests (fast)"
	@echo "  test-unit      - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-all       - Run all tests"
	@echo "  coverage       - Run tests with HTML coverage report"
	@echo "  lint           - Run ruff linter"
	@echo "  format         - Format code with ruff"
	@echo "  type-check     - Run mypy type checking"
	@echo "  clean          - Clean test artifacts"
	@echo "  ci             - Run full CI pipeline locally"

# Development setup
install:
	uv pip install -e ".[dev]"

# Testing commands
test: test-unit

test-unit:
	uv run pytest -m "unit"

test-integration:
	uv run pytest -m "integration"

test-all:
	uv run pytest

coverage:
	uv run pytest -m "unit" --cov-report=html
	@echo "Coverage report available at: htmlcov/index.html"

# Code quality commands
lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

type-check:
	uv run mypy src/

# Cleanup
clean:
	rm -rf htmlcov/
	rm -f coverage.xml test-results.xml .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# CI simulation (run what GitHub Actions runs)
ci: lint type-check test-unit
	@echo "✓ All CI checks passed!"