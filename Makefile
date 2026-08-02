# Makefile for DDON DWARF Reconstructor
# 
# Common development tasks for testing, linting, and CI/CD

.PHONY: help install sync test test-unit test-integration test-all coverage coverage-open lint format format-check type-check structure boundaries prospector clean clean-runtime clean-all ci run run-full run-batch run-batch-full build build-setup langfuse-config langfuse-up langfuse-status langfuse-logs langfuse-stop langfuse-down

LANGFUSE_COMPOSE := docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env

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
	@echo "  structure      - Check module/class/function size and complexity budgets"
	@echo "  boundaries     - Check DDD and hexagonal import boundaries"
	@echo "  prospector     - Run focused duplicate/dead-code/complexity diagnostics"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean          - Clean test artifacts"
	@echo "  clean-runtime  - Clean transient build and test caches"
	@echo "  clean-all      - Safe compatibility alias for clean-runtime"
	@echo ""
	@echo "CI/CD:"
	@echo "  ci             - Run full CI pipeline locally"
	@echo ""
	@echo "Run:"
	@echo "  run            - Run example (make run CLASS=MtObject)"
	@echo "                   Supports multiple: make run CLASS='MtObject,MtVector4'"
	@echo "  run-full       - Run with full hierarchy (make run-full CLASS=MtPropertyList)"
	@echo "                   Supports multiple: make run-full CLASS='MtObject,MtVector4'"
	@echo "  run-batch      - Process symbols from file (make run-batch FILE=resources/season2-resources.txt)"
	@echo "  run-batch-full - Process symbols from file with full hierarchy"
	@echo ""
	@echo "Observability:"
	@echo "  langfuse-config - Validate the Langfuse Compose configuration"
	@echo "  langfuse-up     - Start Langfuse containers in the background"
	@echo "  langfuse-status - Show Langfuse container status"
	@echo "  langfuse-logs   - Show the last 200 Langfuse log lines"
	@echo "  langfuse-stop   - Stop Langfuse containers without deleting data"
	@echo "  langfuse-down   - Remove containers and network; preserve volumes"

# Development setup
install:
	@echo "Note: 'install' is deprecated, use 'make sync' instead"
	uv sync --extra dev

sync:
	uv sync --extra dev

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
	uv run pytest -m "not performance" --cov=src/ddon_dwarf_reconstructor --cov-branch --cov-fail-under=80 --cov-report=json --cov-report=term-missing --cov-report=html
	uv run python scripts/quality/check_coverage.py coverage.json
	@echo "Coverage report generated at: htmlcov/index.html"

coverage-open:
	uv run pytest -m "not performance" --cov=src/ddon_dwarf_reconstructor --cov-branch --cov-fail-under=80 --cov-report=json --cov-report=html
	uv run python scripts/quality/check_coverage.py coverage.json
	@echo "Opening coverage report..."
	@powershell -Command "Start-Process htmlcov/index.html"

# Code quality commands
lint:
	uvx ruff check --no-fix src/ tests/

format:
	uvx ruff format src/ tests/

format-check:
	uvx ruff format --check src/ tests/

type-check:
	uv run mypy src/

structure:
	uv run python scripts/quality/check_structure.py

boundaries:
	uv run python scripts/quality/check_boundaries.py

prospector:
	uv run prospector --profile .prospector.yml --tool pylint --tool pyflakes --tool mccabe src/

# Cleanup
clean:
	@powershell -Command "if (Test-Path htmlcov) { Remove-Item -Recurse -Force htmlcov }"
	@powershell -Command "if (Test-Path coverage.xml) { Remove-Item -Force coverage.xml }"
	@powershell -Command "if (Test-Path test-results.xml) { Remove-Item -Force test-results.xml }"
	@powershell -Command "if (Test-Path .coverage) { Remove-Item -Force .coverage }"
	@powershell -Command "Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force"
	@powershell -Command "Get-ChildItem -Recurse -Filter *.pyc | Remove-Item -Force"
	@echo "Cleaned transient test artifacts (durable caches were preserved)"

clean-runtime: clean
	@powershell -Command "if (Test-Path build) { Remove-Item -Recurse -Force build }"
	@powershell -Command "if (Test-Path .pytest_cache) { Remove-Item -Recurse -Force .pytest_cache }"
	@powershell -Command "if (Test-Path .mypy_cache) { Remove-Item -Recurse -Force .mypy_cache }"
	@powershell -Command "if (Test-Path .ruff_cache) { Remove-Item -Recurse -Force .ruff_cache }"
	@powershell -Command "if (Test-Path main.build) { Remove-Item -Recurse -Force main.build }"
	@powershell -Command "if (Test-Path main.dist) { Remove-Item -Recurse -Force main.dist }"
	@powershell -Command "if (Test-Path main.onefile-build) { Remove-Item -Recurse -Force main.onefile-build }"
	@echo "Cleaned transient runtime files; durable output, indexes, caches, and logs were preserved"

clean-all: clean-runtime
	@echo "clean-all is a safe compatibility alias; use ddon-dwarf-artifacts for explicit purge operations"

# CI simulation (run what GitHub Actions runs)
ci: lint format-check type-check structure boundaries prospector test-unit
	@echo "All CI checks passed!"

# Run example
run:
	@if not defined CLASS (echo Error: CLASS not set. Usage: make run CLASS=MtObject) else (uv run python main.py resources/DDOORBIS.elf --generate $(CLASS))

run-full:
	@if not defined CLASS (echo Error: CLASS not set. Usage: make run-full CLASS=MtPropertyList) else (uv run python main.py resources/DDOORBIS.elf --generate $(CLASS) --full-hierarchy)

run-batch:
	@if not defined FILE (echo Error: FILE not set. Usage: make run-batch FILE=resources/season2-resources.txt) else (uv run python main.py resources/DDOORBIS.elf --symbols-file $(FILE))

run-batch-full:
	@if not defined FILE (echo Error: FILE not set. Usage: make run-batch-full FILE=resources/season2-resources.txt) else (uv run python main.py resources/DDOORBIS.elf --symbols-file $(FILE) --full-hierarchy)

# Local Langfuse observability stack. These targets intentionally stay as thin
# wrappers around Docker Compose so logs and service state remain visible.
langfuse-config:
	$(LANGFUSE_COMPOSE) config --quiet

langfuse-up:
	$(LANGFUSE_COMPOSE) up -d

langfuse-status:
	$(LANGFUSE_COMPOSE) ps --all

langfuse-logs:
	$(LANGFUSE_COMPOSE) logs --tail 200

langfuse-stop:
	$(LANGFUSE_COMPOSE) stop

langfuse-down:
	$(LANGFUSE_COMPOSE) down

