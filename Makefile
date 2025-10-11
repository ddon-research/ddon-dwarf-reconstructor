# Makefile for DDON DWARF Reconstructor
# 
# Common development tasks for testing, linting, and CI/CD

.PHONY: help install sync test test-unit test-integration test-all coverage coverage-open lint format format-check type-check clean clean-all ci run run-full build build-setup

# Default target
help:
	@echo "Available targets:"
	@echo ""
	@echo "Setup:"
	@echo "  install        - Install dependencies (deprecated, use sync)"
	@echo "  sync           - Install/sync dependencies with uv"
	@echo ""
	@echo "Build:"
	@echo "  build-setup    - Install nuitka for native compilation"
	@echo "  build          - Compile to native executable with nuitka"
	@echo ""
	@echo "Testing:"
	@echo "  test           - Run unit tests (fast)"
	@echo "  test-unit      - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-all       - Run all tests"
	@echo "  coverage       - Run tests with HTML coverage report"
	@echo "  coverage-open  - Generate coverage and open in browser"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint           - Run ruff linter"
	@echo "  format         - Format code with ruff"
	@echo "  format-check   - Check code formatting without changes"
	@echo "  type-check     - Run mypy type checking"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean          - Clean test artifacts"
	@echo "  clean-all      - Clean all generated files"
	@echo ""
	@echo "CI/CD:"
	@echo "  ci             - Run full CI pipeline locally"
	@echo ""
	@echo "Run:"
	@echo "  run            - Run example (make run CLASS=MtObject)"
	@echo "  run-full       - Run with full hierarchy (make run-full CLASS=MtPropertyList)"

# Development setup
install:
	@echo "Note: 'install' is deprecated, use 'make sync' instead"
	uv sync

sync:
	uv sync

# Native compilation
build-setup:
	uv add --dev nuitka
	uv sync

build: build-setup
	@echo "Building native executable with nuitka..."
	@echo "This may take several minutes..."
	uv run python -m nuitka --clang --onefile --jobs=16 --lto=yes --static-libpython=auto --remove-output --deployment --output-dir=build main.py
	@echo ""
	@echo "Build complete! Executable: build/main.exe"
	@echo "Usage: build/main.exe --generate ClassName resources/DDOORBIS.elf"
	@echo "       build/main.exe --generate ClassName --full-hierarchy resources/DDOORBIS.elf"

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
	@echo "Coverage report generated at: htmlcov/index.html"

coverage-open:
	uv run pytest -m "unit" --cov-report=html
	@echo "Opening coverage report..."
	@powershell -Command "Start-Process htmlcov/index.html"

# Code quality commands
lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

format-check:
	uv run ruff format --check src/ tests/

type-check:
	uv run mypy src/

# Cleanup
clean:
	@powershell -Command "if (Test-Path htmlcov) { Remove-Item -Recurse -Force htmlcov }"
	@powershell -Command "if (Test-Path coverage.xml) { Remove-Item -Force coverage.xml }"
	@powershell -Command "if (Test-Path test-results.xml) { Remove-Item -Force test-results.xml }"
	@powershell -Command "if (Test-Path .coverage) { Remove-Item -Force .coverage }"
	@powershell -Command "Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force"
	@powershell -Command "Get-ChildItem -Recurse -Filter *.pyc | Remove-Item -Force"
	@echo "Cleaned test artifacts and cache files"

clean-all: clean
	@powershell -Command "if (Test-Path build) { Remove-Item -Recurse -Force build }"
	@powershell -Command "if (Test-Path output) { Remove-Item -Recurse -Force output }"
	@powershell -Command "if (Test-Path logs) { Remove-Item -Recurse -Force logs }"
	@powershell -Command "if (Test-Path .pytest_cache) { Remove-Item -Recurse -Force .pytest_cache }"
	@powershell -Command "if (Test-Path .mypy_cache) { Remove-Item -Recurse -Force .mypy_cache }"
	@powershell -Command "if (Test-Path .ruff_cache) { Remove-Item -Recurse -Force .ruff_cache }"
	@powershell -Command "if (Test-Path main.build) { Remove-Item -Recurse -Force main.build }"
	@powershell -Command "if (Test-Path main.dist) { Remove-Item -Recurse -Force main.dist }"
	@powershell -Command "if (Test-Path main.onefile-build) { Remove-Item -Recurse -Force main.onefile-build }"
	@echo "Cleaned all generated files"

# CI simulation (run what GitHub Actions runs)
ci: lint format-check type-check test-unit
	@echo "All CI checks passed!"

# Run example
run:
	@if not defined CLASS (echo Error: CLASS not set. Usage: make run CLASS=MtObject) else (uv run python main.py resources/DDOORBIS.elf --generate $(CLASS))

run-full:
	@if not defined CLASS (echo Error: CLASS not set. Usage: make run-full CLASS=MtPropertyList) else (uv run python main.py resources/DDOORBIS.elf --generate $(CLASS) --full-hierarchy)