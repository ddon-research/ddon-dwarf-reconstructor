set dotenv-load := true

[windows]
set shell := ["powershell.exe", "-NoLogo", "-Command"]

default:
    @just --list

sync:
    uv sync --python 3.14.7 --locked
    npm ci --prefix tools/documentation --no-audit --no-fund

lock-check:
    uv lock --check
    uv lock --directory tools/dwarf_spec_pipeline --check

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
    uv sync --locked --group performance

performance-profile elf_file="resources/DDOORBIS.elf" dwarf_store="output/analytical-dwarf/main/store-4236f598acc8f158/manifest.json" symbol="rLayout" state="warm":
    uv run ddon-dwarf-reconstructor performance profile {{elf_file}} --dwarf-store {{dwarf_store}} --symbol {{symbol}} --state {{state}} --profiler scalene --profiler cprofile --profiler pyinstrument

performance-profile-index dwarf_dump="D:/research/DDON-binaries/IDA9.3/PS4_DDON_02020005_2016_12_21/DDOORBIS.elf.llvmdwarfdump.zst" index_path="$env:TEMP/ddon-analytical-dwarf/performance/cold-dump-index.sqlite3":
    uv run ddon-dwarf-reconstructor performance profile-index {{dwarf_dump}} --index-path {{index_path}} --state cold --profiler process-sampler

performance-profile-index-traces dwarf_dump="D:/research/DDON-binaries/IDA9.3/PS4_DDON_02020005_2016_12_21/DDOORBIS.elf.llvmdwarfdump.zst" artifact_root="$env:TEMP/ddon-analytical-dwarf/performance/algorithm-audit" history_db="$env:TEMP/ddon-analytical-dwarf/performance/algorithm-audit/benchmarks.sqlite3":
    uv run ddon-dwarf-reconstructor performance profile-index {{dwarf_dump}} --index-path {{artifact_root}}/cold-process-sampler.sqlite3 --artifact-dir {{artifact_root}}/profiles --history-db {{history_db}} --name cold-dump-index-process-sampler --state cold --profiler process-sampler --timeout-seconds 3600 --sample-interval 1
    uv run ddon-dwarf-reconstructor performance profile-index {{dwarf_dump}} --index-path {{artifact_root}}/cold-cprofile.sqlite3 --artifact-dir {{artifact_root}}/profiles --history-db {{history_db}} --name cold-dump-index-cprofile --state cold --profiler cprofile --timeout-seconds 3600 --sample-interval 1
    uv run ddon-dwarf-reconstructor performance profile-index {{dwarf_dump}} --index-path {{artifact_root}}/cold-scalene.sqlite3 --artifact-dir {{artifact_root}}/profiles --history-db {{history_db}} --name cold-dump-index-scalene --state cold --profiler scalene --timeout-seconds 3600 --sample-interval 1
    uv run ddon-dwarf-reconstructor performance profile-index {{dwarf_dump}} --index-path {{artifact_root}}/cold-pyinstrument.sqlite3 --artifact-dir {{artifact_root}}/profiles --history-db {{history_db}} --name cold-dump-index-pyinstrument --state cold --profiler pyinstrument --timeout-seconds 3600 --sample-interval 1

performance-history:
    uv run ddon-dwarf-reconstructor performance history export

performance-runtime-compare elf_file="resources/DDOORBIS.elf" nuitka_executable="$env:TEMP/ddon-analytical-dwarf/performance/nuitka/cpython314/ddon-reconstructor-cpython314.exe" free_threaded_python="$env:TEMP/ddon-analytical-dwarf/performance/venvs/ddon-3.14t/Scripts/python.exe" dwarf_store="output/analytical-dwarf/main/store-4236f598acc8f158/manifest.json":
    uv run ddon-dwarf-reconstructor performance compare-runtimes {{elf_file}} --symbol rLayout --nuitka-executable {{nuitka_executable}} --free-threaded-python {{free_threaded_python}} --dwarf-store {{dwarf_store}} --build-id ps4-02020005

analytical-materialize elf_file="resources/DDOORBIS.elf" output_dir="output/analytical-dwarf/main":
    uv run ddon-dwarf-reconstructor artifacts materialize-dwarf {{elf_file}} --output-dir {{output_dir}} --write-parquet

analytical-bounded elf_file="resources/DDOORBIS.elf" output_dir="$env:TEMP/ddon-analytical-dwarf/bounded" max_cus="1":
    uv run ddon-dwarf-reconstructor artifacts materialize-dwarf {{elf_file}} --output-dir {{output_dir}} --write-parquet --max-cus {{max_cus}}

analytical-checkpoint elf_file="resources/DDOORBIS.elf" output_dir="$env:TEMP/ddon-analytical-dwarf/checkpoint" every_cus="64":
    uv run ddon-dwarf-reconstructor artifacts materialize-dwarf {{elf_file}} --output-dir {{output_dir}} --write-parquet --checkpoint-every-cus {{every_cus}}

analytical-checkpoint-benchmark elf_file="resources/DDOORBIS.elf" checkpoint_manifest="" output_dir="$env:TEMP/ddon-analytical-dwarf/checkpoint-benchmark":
    uv run ddon-dwarf-reconstructor performance benchmark-dwarf-store {{elf_file}} --store-manifest {{checkpoint_manifest}} --allow-incomplete --output-dir {{output_dir}}

analytical-benchmark elf_file="resources/DDOORBIS.elf" output_dir="$env:TEMP/ddon-analytical-dwarf/analytical-benchmark" dwarf_store="":
    uv run ddon-dwarf-reconstructor performance benchmark-dwarf-store {{elf_file}} --output-dir {{output_dir}} {{ if dwarf_store != "" { "--store-manifest " + dwarf_store } else { "" } }}

analytical-profile-doris elf_file="resources/DDOORBIS.elf" store_manifest="output/analytical-dwarf/main/store-4236f598acc8f158/manifest.json" output_dir="$env:TEMP/ddon-analytical-dwarf/analytical-profile-doris":
    uv run ddon-dwarf-reconstructor performance profile-dwarf-store {{elf_file}} --store-manifest {{store_manifest}} --output-dir {{output_dir}} --query-existing-doris --profiler scalene --profiler cprofile

analytical-benchmark-current-doris elf_file="resources/DDOORBIS.elf" store_manifest="output/analytical-dwarf/main/store-4236f598acc8f158/manifest.json" output_dir="$env:TEMP/ddon-analytical-dwarf/current-doris-benchmark":
    uv run ddon-dwarf-reconstructor performance benchmark-doris-current {{elf_file}} --store-manifest {{store_manifest}} --output-dir {{output_dir}} --control-iterations 1 --query-iterations 3 --aifsm-iterations 1 --control-timeout-seconds 900 --aifsm-timeout-seconds 7200

analytical-fixture:
    uv run pytest tests/infrastructure/test_analytical_store.py tests/infrastructure/test_analytical_checkpoint.py tests/infrastructure/test_analytical_parquet_contract.py tests/infrastructure/test_analytical_benchmark_paths.py -m "unit and functional"

analytical-compose-config:
    docker compose --file ops/analytical-dwarf/compose.yaml config --quiet

analytical-compose-flight-config:
    docker compose --file ops/analytical-dwarf/compose.yaml --file ops/analytical-dwarf/compose.flight.yaml config --quiet

analytical-check-flight output="$env:TEMP/ddon-analytical-dwarf/analytical-flight/doris-flight-preflight.json":
    uv run --group flight-sql ddon-dwarf-reconstructor performance check-doris-flight --output {{output}}

analytical-benchmark-flight store_manifest="output/analytical-dwarf/main/store-4236f598acc8f158/manifest.json" output_dir="$env:TEMP/ddon-analytical-dwarf/analytical-flight":
    uv run --group flight-sql ddon-dwarf-reconstructor performance benchmark-doris-flight --store-manifest {{store_manifest}} --output-dir {{output_dir}}

reconstructor-container-config:
    docker compose --file ops/reconstructor/compose.yaml config --quiet
    docker compose --file ops/reconstructor/compose.yaml --profile py-spy config --quiet
    docker compose --file ops/reconstructor/compose.yaml --profile doris config --quiet
    docker compose --file ops/reconstructor/compose.yaml --profile doris --profile py-spy config --quiet

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
    uv run deptry . --per-rule-ignores "DEP002=pyarrow|pymysql"

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

check: lock-check lint format-check actionlint type-check deps structure architecture docs-check

ci: check test-unit package-smoke

package:
    uv build

package-smoke:
    uv run pytest tests/packaging/test_uv_tool_install.py -m packaging

sonar-validate:
    uv run python -m tools.sonar.prepare_msvc_analysis --validate-only

sonar-capture:
    uv run python -m tools.sonar.prepare_msvc_analysis

native-build output_dir="$env:TEMP/ddon-analytical-dwarf/performance/nuitka/cpython314":
    uv run python -m nuitka --msvc=latest --mode=onefile --jobs=16 --lto=yes --remove-output --deployment --output-dir={{output_dir}} --output-filename=ddon-reconstructor-cpython314.exe main.py

nuitka-build: native-build

run elf_file="resources/DDOORBIS.elf" symbol="MtObject":
    uv run ddon-dwarf-reconstructor generate {{elf_file}} --symbol {{symbol}}

run-full elf_file="resources/DDOORBIS.elf" symbol="MtPropertyList":
    uv run ddon-dwarf-reconstructor generate {{elf_file}} --symbol {{symbol}} --full-hierarchy

run-batch symbols_file elf_file="resources/DDOORBIS.elf":
    uv run ddon-dwarf-reconstructor generate {{elf_file}} --symbols-file {{symbols_file}}

run-batch-full symbols_file elf_file="resources/DDOORBIS.elf" output_dir="output/season2" dwarf_store="output/analytical-dwarf/main/store-4236f598acc8f158/manifest.json":
    uv run ddon-dwarf-reconstructor generate {{elf_file}} --symbols-file {{symbols_file}} --dwarf-store {{dwarf_store}} --output {{output_dir}} --full-hierarchy

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
