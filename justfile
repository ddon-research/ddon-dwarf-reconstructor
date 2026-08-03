set dotenv-load := true

[windows]
set shell := ["powershell.exe", "-NoLogo", "-Command"]

default:
    @just --list

sync:
    uv sync --python 3.14.6

test-unit:
    uv run pytest -m unit -o addopts='-q --strict-markers'

test-observability:
    uv run pytest tests/infrastructure/test_logging.py -m unit -q

test-integration:
    uv run pytest -m "integration and not performance and not real_asset"

test-without-integration:
    uv run pytest -m "not integration and not acceptance and not performance and not packaging and not real_asset"

test-regression:
    uv run pytest -m regression

test-non-functional:
    uv run pytest -m "non_functional and not performance and not packaging and not real_asset"

test-acceptance:
    uv run pytest -m acceptance

test-real-assets:
    uv run pytest -m real_asset

test-performance:
    uv run pytest -m performance

test:
    uv run pytest -m "not performance and not packaging and not real_asset"

coverage:
    uv run pytest -m "not performance and not packaging and not real_asset" --cov=src/ddon_dwarf_reconstructor --cov-branch --cov-fail-under=80 --cov-report=json --cov-report=term-missing --cov-report=html
    uv run python -m tests.support.quality.check_coverage coverage.json

coverage-open:
    uv run pytest -m "not performance and not packaging and not real_asset" --cov=src/ddon_dwarf_reconstructor --cov-branch --cov-fail-under=80 --cov-report=json --cov-report=html
    uv run python -m tests.support.quality.check_coverage coverage.json
    powershell -NoProfile -Command "Start-Process htmlcov/index.html"

coverage-ci:
    uv run pytest -m "not performance and not packaging and not real_asset" --cov=src/ddon_dwarf_reconstructor --cov-branch --cov-fail-under=80 --cov-report=json --cov-report=xml --cov-report=html --junit-xml=test-results.xml
    uv run python -m tests.support.quality.check_coverage coverage.json

lint:
    uv run ruff check --no-fix src tests tools/sonar

format:
    uv run ruff format src tests tools/sonar

format-check:
    uv run ruff format --check src tests tools/sonar

actionlint:
    actionlint -color

type-check:
    uv run pyrefly check --min-severity warn

deps:
    uv run deptry .

structure:
    uv run python -m tests.support.quality.check_structure src tests tools/sonar

architecture:
    uv run pytest tests/quality/test_architecture.py -q

audit:
    uv run prospector --profile .prospector.yml --tool pylint --tool pyflakes --tool mccabe src

check: lint format-check actionlint type-check deps structure architecture

ci: check test-unit package-smoke

package:
    uv build

package-smoke:
    uv run pytest tests/packaging/test_uv_tool_install.py -m packaging

sonar-validate:
    uv run python -m tools.sonar.prepare_msvc_analysis --validate-only

sonar-capture:
    uv run python -m tools.sonar.prepare_msvc_analysis

native-build:
    uv run python -m nuitka --clang --onefile --jobs=16 --lto=yes --static-libpython=auto --remove-output --deployment --output-dir=build main.py

run elf_file="resources/DDOORBIS.elf" symbol="MtObject":
    uv run ddon-dwarf-reconstructor generate {{elf_file}} --symbol {{symbol}}

run-full elf_file="resources/DDOORBIS.elf" symbol="MtPropertyList":
    uv run ddon-dwarf-reconstructor generate {{elf_file}} --symbol {{symbol}} --full-hierarchy

run-batch symbols_file elf_file="resources/DDOORBIS.elf":
    uv run ddon-dwarf-reconstructor generate {{elf_file}} --symbols-file {{symbols_file}}

run-batch-full symbols_file elf_file="resources/DDOORBIS.elf":
    uv run ddon-dwarf-reconstructor generate {{elf_file}} --symbols-file {{symbols_file}} --full-hierarchy

spec-check:
    uv run --directory tools/dwarf_spec_pipeline just check

binary-toolchain-config:
    docker compose --file tools/binary_toolchain/compose.yaml config --quiet

langfuse-config:
    docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env config --quiet

langfuse-up:
    docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env up -d

langfuse-status:
    docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env ps --all

langfuse-logs:
    docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env logs --tail 200

langfuse-stop:
    docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env stop

langfuse-down:
    docker compose --project-name ddon-langfuse --file ops/langfuse/compose.yaml --env-file ops/langfuse/.env down
