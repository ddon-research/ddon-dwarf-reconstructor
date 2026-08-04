set dotenv-load := true

[windows]
set shell := ["powershell.exe", "-NoLogo", "-Command"]

default:
    @just --list

sync:
    uv sync --python 3.14.6
    npm ci --prefix tools/documentation --no-audit --no-fund

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

test-performance-fixtures:
    uv run pytest tests/performance/test_fixture_benchmark.py -m "performance and not real_asset"

test-performance-real-assets:
    $env:DDON_REAL_PERFORMANCE = "1"; uv run pytest -m "performance and real_asset"

test-performance:
    uv run pytest -m performance

performance-tools-install:
    uv sync --group performance

performance-profile elf_file="resources/DDOORBIS.elf" symbol="rLayout" state="warm":
    uv run ddon-dwarf-reconstructor performance profile {{elf_file}} --symbol {{symbol}} --state {{state}} --profiler scalene --profiler cprofile --profiler pyinstrument

performance-profile-index dwarf_dump="D:/research/DDON-binaries/IDA9.3/PS4_DDON_02020005_2016_12_21/DDOORBIS.elf.llvmdwarfdump.zst" index_path="D:/ddon-perf-artifacts/cold-dump-index.sqlite3":
    uv run ddon-dwarf-reconstructor performance profile-index {{dwarf_dump}} --index-path {{index_path}} --state cold --profiler process-sampler

performance-profile-index-traces dwarf_dump="D:/research/DDON-binaries/IDA9.3/PS4_DDON_02020005_2016_12_21/DDOORBIS.elf.llvmdwarfdump.zst" artifact_root="D:/ddon-perf-artifacts/algorithm-audit" history_db="D:/ddon-perf-artifacts/algorithm-audit/benchmarks.sqlite3":
    uv run ddon-dwarf-reconstructor performance profile-index {{dwarf_dump}} --index-path {{artifact_root}}/cold-process-sampler.sqlite3 --artifact-dir {{artifact_root}}/profiles --history-db {{history_db}} --name cold-dump-index-process-sampler --state cold --profiler process-sampler --timeout-seconds 3600 --sample-interval 1
    uv run ddon-dwarf-reconstructor performance profile-index {{dwarf_dump}} --index-path {{artifact_root}}/cold-cprofile.sqlite3 --artifact-dir {{artifact_root}}/profiles --history-db {{history_db}} --name cold-dump-index-cprofile --state cold --profiler cprofile --timeout-seconds 3600 --sample-interval 1
    uv run ddon-dwarf-reconstructor performance profile-index {{dwarf_dump}} --index-path {{artifact_root}}/cold-scalene.sqlite3 --artifact-dir {{artifact_root}}/profiles --history-db {{history_db}} --name cold-dump-index-scalene --state cold --profiler scalene --timeout-seconds 3600 --sample-interval 1
    uv run ddon-dwarf-reconstructor performance profile-index {{dwarf_dump}} --index-path {{artifact_root}}/cold-pyinstrument.sqlite3 --artifact-dir {{artifact_root}}/profiles --history-db {{history_db}} --name cold-dump-index-pyinstrument --state cold --profiler pyinstrument --timeout-seconds 3600 --sample-interval 1

performance-history:
    uv run ddon-dwarf-reconstructor performance history export

performance-runtime-compare elf_file="resources/DDOORBIS.elf" nuitka_executable="D:/ddon-perf-artifacts/nuitka/cpython314/ddon-reconstructor-cpython314.exe" free_threaded_python="D:/ddon-perf-artifacts/venvs/ddon-3.14t/Scripts/python.exe" dwarf_index="resources/.cache/DDOORBIS.elf.llvmdwarfdump.index.sqlite3":
    uv run ddon-dwarf-reconstructor performance compare-runtimes {{elf_file}} --symbol rLayout --nuitka-executable {{nuitka_executable}} --free-threaded-python {{free_threaded_python}} --dwarf-index {{dwarf_index}} --build-id ps4-02020005

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

docs-serve:
    uv run zensical serve

docs-tools-install:
    npm ci --prefix tools/documentation --no-audit --no-fund

docs-lint:
    npm --offline --prefix tools/documentation exec -- markdownlint-cli2

docs-diagrams:
    npm --prefix tools/documentation run validate:mermaid

docs-build:
    uv run zensical build --strict

docs-check: docs-lint docs-diagrams docs-build

audit:
    uv run prospector --profile .prospector.yml --tool pylint --tool pyflakes --tool mccabe src

check: lint format-check actionlint type-check deps structure architecture docs-check

ci: check test-unit package-smoke

package:
    uv build

package-smoke:
    uv run pytest tests/packaging/test_uv_tool_install.py -m packaging

sonar-validate:
    uv run python -m tools.sonar.prepare_msvc_analysis --validate-only

sonar-capture:
    uv run python -m tools.sonar.prepare_msvc_analysis

native-build output_dir="D:/ddon-perf-artifacts/nuitka/cpython314":
    uv run python -m nuitka --msvc=latest --mode=onefile --jobs=16 --lto=yes --remove-output --deployment --output-dir={{output_dir}} --output-filename=ddon-reconstructor-cpython314.exe main.py

nuitka-build: native-build

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
