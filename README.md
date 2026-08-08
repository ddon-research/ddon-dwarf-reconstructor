# DDON DWARF Reconstructor

Reconstructs deterministic C++ class definitions from DWARF debug information in ELF files for
Dragon's Dogma Online research and modding.

## Features

- Complete type dependency and inheritance resolution across compilation units.
- Validated PS4 DWARF 4 and PS3 DWARF 2 producer detection, with parser contracts covering the
  DWARF 2-4 vocabulary.
- Read-only ELF and compressed-dump evidence inspection, plus a searchable DWARF 2/3/4 semantic
  index for correctness reviews.
- Deterministic single-file and multi-file header generation.
- Persistent source-bound symbol caches and streaming compressed-DWARF indexes.
- Source-bound analytical DWARF stores with canonical typed Parquet rows, optional lossless
  JSONL audit output, and Doris projections.
- Knowledge-graph exports with explicit producer and Orbis evidence provenance.
- Bounded one-time exports from Orbis, LLVM, GNU Binutils, elfutils, and libdwarf profiles, with
  source/tool/output hashes and authority metadata.
- Typed CLI, locked uv dependencies, Ruff, Pyrefly, deptry, and just automation.

## Requirements and setup

- Regular CPython 3.14.6.
- `uv`.
- An ELF file with DWARF debug information for generation.

```text
uv sync --python 3.14.6
uv run just test-unit
```

The analytical projection tools are an explicit optional dependency group. Install them when
materializing Parquet output or preparing Doris evidence:

```text
uv sync --group analytical
```

The analytical runtime is pinned to `pyarrow==25.0.0`. Verify the installed Arrow, Parquet, and
Dataset modules without loading the ELF:

```powershell
uv run python -c "import pyarrow as pa, pyarrow.dataset as ds, pyarrow.parquet as pq; print(pa.__version__, pa.default_memory_pool().backend_name, ds.__file__, pq.__file__)"
```

To install the reconstructor as a standalone uv tool from a checkout:

```text
uv tool install . --python 3.14.6
ddon-dwarf-reconstructor --version
ddon-dwarf-reconstructor --help
```

The installed tool contains the runtime package and dependencies only; repository quality and
SonarQube maintenance commands remain checkout-local `just` or Python-module workflows.

The committed `[tool.pyrefly]` sections are the authoritative project configuration. If a fresh
checkout has no Pyrefly section, run `uv run pyrefly init pyproject.toml` once, review the result,
and retain the explicit configuration with the recommended Pyrefly VS Code extension. Normal
validation is `uv run just type-check`.

The standalone specification pipeline has its own dependency boundary:

```text
uv sync --directory tools/dwarf_spec_pipeline --python 3.14.6
uv run --directory tools/dwarf_spec_pipeline just check
```

## CLI usage

The packaged `ddon-dwarf-reconstructor` command is canonical. Symbols are supplied by repeating
`--symbol` or by using `--symbols-file`; comma-separated symbol values are no longer accepted.

```text
# Materialize once into the ignored durable local store, publish it into Doris, then use the
# source-bound manifest for Doris-backed generation
uv run ddon-dwarf-reconstructor artifacts materialize-dwarf resources/DDOORBIS.elf \
  --output-dir output/analytical-dwarf/main --write-parquet
uv run ddon-dwarf-reconstructor artifacts load-doris \
  output/analytical-dwarf/main/store-<source-sha16>/manifest.json

# Optional diagnostic checkpoints for a long traversal; they remain explicitly partial
uv run ddon-dwarf-reconstructor artifacts materialize-dwarf resources/DDOORBIS.elf \
  --output-dir $env:TEMP/ddon-analytical-dwarf/checkpoint-run --checkpoint-every-cus 64

# Query the latest committed checkpoint while the producer continues; this is diagnostic only
uv run ddon-dwarf-reconstructor performance benchmark-dwarf-store resources/DDOORBIS.elf \
  --store-manifest $env:TEMP/ddon-analytical-dwarf/checkpoint-run/<checkpoint>.json \
  --allow-incomplete --output-dir $env:TEMP/ddon-analytical-dwarf/checkpoint-benchmark

# One or more headers
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf \
  --dwarf-store output/analytical-dwarf/main/store-<source-sha16>/manifest.json --symbol MtObject
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf \
  --dwarf-store output/analytical-dwarf/main/store-<source-sha16>/manifest.json \
  --symbol MtObject --symbol rLayout

# Full hierarchy and exhaustive root lookup
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf \
  --dwarf-store output/analytical-dwarf/main/store-<source-sha16>/manifest.json \
  --symbol rLayout --full-hierarchy --exhaustive

# Batch processing
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf \
  --dwarf-store output/analytical-dwarf/main/store-<source-sha16>/manifest.json \
  --symbols-file resources/season2-resources.txt --full-hierarchy

# Knowledge export
uv run ddon-dwarf-reconstructor export-knowledge resources/DDOORBIS.elf \
  --dwarf-store output/analytical-dwarf/main/store-<source-sha16>/manifest.json \
  --symbol rLayout --output-dir output/rLayout --build-id ps4-02020005 \
  --orbis-objdump 'D:/SCE/ORBIS SDKs/8.000/host_tools/bin/orbis-objdump.exe'
```

When `--symbols-file` is combined with `--full-hierarchy` and multiple roots, generation writes
separate source-derived bundles under `output/season2/<platform>/symbols/<index>-<safe-root>/`.
Each bundle has its own manifest and status; aggregate publication fails closed on conflicting
same-named headers. Validate a selected root bundle standalone before treating aggregate, Sonar,
or IDA diagnostics as additive evidence.

Use `uv run ddon-dwarf-reconstructor --help` or a command’s `--help` for the complete typed
interface. Normal `generate` and `export-knowledge` runs require `--dwarf-store` and a matching
complete source publication in Doris; a missing, stale, incomplete, unavailable, or
count-mismatched publication fails closed. They never perform an implicit CU traversal or read
Parquet/JSONL at runtime. `--dwarf-dump` and `--dwarf-index` remain explicit validation-only
inputs for the legacy cross-check workflow.

## Logging and diagnostics

Each command writes structured JSON-lines diagnostics to `logs/` and human-readable progress to
stderr. Use `--verbose` to include DEBUG events on stderr; artifact commands keep their result JSON
on stdout. Records include the run ID, symbol/stage context, source identity when available,
callsite filename/line, durations, bounded counts, and nested exception tracebacks.

```powershell
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf --symbol rLayout --verbose

$log = Get-ChildItem logs -Filter 'ddon_reconstructor_*.jsonl' |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
Get-Content $log.FullName | ConvertFrom-Json |
  Where-Object event -in @('symbol_failed', 'generation_failed')
```

See the [operational observability guide](docs/how-to/observability.md) for the event contract,
low-noise severity policy, exception handling, and the boundary between runtime logging and
optional developer-tool tracing. Use the [Langfuse developer tracing how-to](docs/how-to/observability/langfuse.md)
for local Copilot/Codex telemetry and the [SonarQube C/C++ how-to](docs/how-to/quality/sonarqube.md)
for local generated-header analysis.

## Durable artifact operations

Artifact maintenance is grouped under the root command and is intentionally explicit:

```powershell
uv run ddon-dwarf-reconstructor artifacts inspect `
  --elf resources/DDOORBIS.elf `
  --dwarf-dump D:/research/DDON-binaries/DDOORBIS.elf.llvmdwarfdump.zst `
  --dump-index output/real-dump-index/DDOORBIS.elf.index.sqlite3

uv run ddon-dwarf-reconstructor artifacts inspect-elf `
  D:/research/DDON-binaries/IDA9.3/PS4_DDON_02020005_2016_12_21/DDOORBIS.elf

uv run ddon-dwarf-reconstructor artifacts inspect-dwarf-dump `
  D:/research/DDON-binaries/IDA9.3/PS4_DDON_02020005_2016_12_21/DDOORBIS.elf.llvmdwarfdump.zst

uv run ddon-dwarf-reconstructor artifacts inspect-dwarf-store `
  output/analytical-dwarf/main/store-<source-sha16>/manifest.json

uv run ddon-dwarf-reconstructor artifacts load-doris `
  output/analytical-dwarf/main/store-<source-sha16>/manifest.json --dry-run

uv run ddon-dwarf-reconstructor artifacts verify-source resources/DDOORBIS.elf
uv run ddon-dwarf-reconstructor artifacts repair-dump-index D:/research/DDON-binaries/dump.zst
uv run ddon-dwarf-reconstructor artifacts rebuild-dump-index D:/research/DDON-binaries/dump.zst
uv run ddon-dwarf-reconstructor artifacts repair-catalog
```

`purge-dump-index` requires `--confirm-index-path` containing the exact resolved sidecar path.
Repair, rebuild, and purge operations never broaden their target beyond the explicitly selected
artifact. The former `ddon-dwarf-artifacts` executable is intentionally removed.

The source catalog uses a relocation-stable metadata key (size, mtime, device, and inode) to
reuse a verified SHA-256 when an immutable input is moved. It retains ctime and recorded paths as
a same-path replacement guard; ctime drift is reusable only when the old path disappeared. Use
`artifacts verify-source` when an explicit full rehash is required. This distinction is covered by
the artifact regression tests on both the Linux CI runner and the Windows development host; the
post-fix PR checks and the merged `main` workflows now pass this contract.

## External tool evidence

External inspection is an explicit, source-bound artifact workflow. Probe local executables first,
then run a named profile; raw output is streamed to disk, hashed, and published atomically.
Matching Orbis tools remain authoritative for PS4 ABI and SCE-specific values. LLVM, GNU Binutils,
elfutils, libdwarf, pyelftools, LIEF, and OpenOrbis outputs are additive evidence until a PS4
behavior has been validated. `elfldr` is loader research and is not executed by this project.

```powershell
uv run ddon-dwarf-reconstructor artifacts list-tool-profiles
uv run ddon-dwarf-reconstructor artifacts probe-tool `
  D:/SCE/ORBIS SDKs/8.000/host_tools/bin/orbis-readelf.exe `
  --output-dir output/tool-probes
uv run ddon-dwarf-reconstructor artifacts export-tool-evidence `
  resources/DDOORBIS.elf `
  --tool 'D:/SCE/ORBIS SDKs/8.000/host_tools/bin/orbis-readelf.exe' `
  --profile orbis-elf-headers --output-dir output/tool-exports
uv run ddon-dwarf-reconstructor export-knowledge resources/DDOORBIS.elf `
  --symbol rLayout --output-dir output/rLayout `
  --tool-evidence output/tool-exports/<artifact-key>/manifest.json
```

`--tool-evidence` may be repeated. A manifest whose source identity, output checksum, artifact key,
or output path is stale is rejected before graph export. The resulting bundle contains additive
`Tool`, `SourceArtifact`, and `Evidence` records; deterministic DWARF layout and producer facts are
not overwritten. The non-proprietary Docker baseline is documented in
[`tools/binary_toolchain/README.md`](tools/binary_toolchain/README.md):

```text
docker compose --file tools/binary_toolchain/compose.yaml build
docker compose --file tools/binary_toolchain/compose.yaml run --rm binary-toolchain
```

The container does not include Sony SDKs, proprietary binaries, credentials, SELF loading, or
decryption. Mount explicit input directories read-only and keep raw outputs under ignored output
paths.

`inspect-elf` performs an explicit all-CU header/producer pass. `inspect-dwarf-dump` performs an
explicit streaming pass over the compressed LLVM text and retains only bounded counters. Neither
command is part of ordinary generation or the default test loop.

The standalone specification project builds the semantic index from the checked-in JSON/Markdown
source artifacts:

```text
uv run --directory tools/dwarf_spec_pipeline dwarf-spec-pipeline audit \
  --output-dir ../../docs/knowledge-base/dwarf-specification/generated --source-root ../../src
```

The index records versioned tags, attributes, forms, operations, attribute encodings, tag
applicability, and source references. It is review evidence, not a runtime dependency.

## DWARF dump and cache behavior

The analytical store is the normal lookup boundary. Its canonical typed row stream is written to
family-specific Parquet tables with Zstandard and bounded row groups. Doris loads those
source-bound files through the explicit native-table path. `records.jsonl`
preserves the same source identity, CU/DIE traversal order, null terminators, raw and decoded tagged
attributes, references, and checksummed raw-section/chunk artifacts only when the opt-in audit
projection is requested. JSONL is not a mandatory intermediary. Doris loading is explicit and never
starts Compose implicitly. All optional projections and benchmark artifacts belong outside source
control, normally under `%TEMP%` on Disk C.

The PyArrow 25 boundary is explicit: family schemas are declared before conversion, Parquet writers
append bounded row groups, and the native `Table.from_pylist` input is capped because nested DWARF
values can exceed a cheap byte estimate. Dataset readers use typed layout-specific Hive
partitioning, column/filter pushdown, and `to_batches()` for large scans. Arrow memory-pool
telemetry is not a substitute for process RSS. If a complete JSONL audit store later requests a
Parquet projection, the backfill uses the same bounded writer sink and the manifest's layout and
writer cap before atomically publishing `parquet/`.

The former compressed-dump SQLite index remains a validation-only cross-check until parity evidence
is complete. The full PS4 dump is more than 30 GB expanded, so real-asset work is opt-in and should
use the local acceptance paths documented in the [testing and evidence reference](docs/reference/testing.md).

This checkout also retains the regenerated PS4 dump index at
`resources/.cache/DDOORBIS.elf.llvmdwarfdump.index.sqlite3` and source-bound symbol caches under
`.cache/` and `resources/PS3/.cache/`. To reuse the checked-in cache for this checkout, set
`DWARF_CACHE_DIR` to the corresponding cache directory before running the generator. These cache
filenames include the resolved source path identity; regenerate them after moving the checkout.

Runtime DWARF settings are validated at startup:

```text
DWARF_DIE_CACHE_SIZE       positive integer, default 10000
DWARF_TYPE_CACHE_SIZE      positive integer, default 5000
DWARF_MAX_SEARCH_TIME_MS   positive milliseconds, default 1000
```

ELF/DWARF handles are owned by one session boundary. Generated headers are staged and committed
through a source-independent atomic bundle publisher with `header-bundle.manifest.json`; failed
publication restores the previous bundle.

## Development automation

`just` is the single task-runner source of truth. Python tools use the locked uv environment, and
documentation validators use the locked `tools/documentation/package-lock.json` environment:

```text
uv run just                 # list recipes
uv run just sync
uv lock --check
uv run just test-unit       # fast tests
uv run just test-integration # required deterministic integrations
uv run just test-without-integration # exceptional fast opt-out
uv run just test-regression  # output and authority contracts
uv run just test-non-functional # quality/operational checks
uv run just test-observability # focused JSONL/chained traceback tests
uv run just test            # required correctness loop, including integrations
uv run just actionlint      # GitHub Actions workflow syntax and expression checks
uv run just check           # code quality, Markdownlint, Mermaid, and strict site build
uv run just coverage-ci     # coverage thresholds and CI reports
uv run just audit            # Prospector duplicate/dead-code audit
uv run just test-acceptance  # CLI, real-asset, and distribution acceptance
uv run just test-real-assets # explicit local external inputs
uv run just test-performance # explicit performance budgets
uv run just test-performance-fixtures # deterministic resource budget
uv run just test-performance-real-assets # explicit real-asset performance
uv run just performance-tools-install # install Scalene/pyperf/profiler tools
uv run just performance-profile # warm rLayout profile recipe
uv run just performance-profile-index # cold compressed-dump index profile recipe
uv run just performance-runtime-compare # CPython/Nuitka/free-threaded comparison
uv run just analytical-materialize # typed Parquet materialization
uv run just analytical-fixture # deterministic analytical-store fixture tests
uv run just analytical-benchmark # one-pass and projection benchmark report
uv run just analytical-compose-config # validate the local Doris Compose file
uv run just performance-history # export tracked benchmark history
uv run just docs-tools-install # install locked Markdown/Mermaid validators
uv run just docs-serve       # local Zensical preview
uv run just docs-lint        # lint authored Markdown
uv run just docs-diagrams    # render Mermaid fences to temporary SVGs
uv run just docs-check       # docs-lint, docs-diagrams, and strict site build
uv run just package         # wheel and sdist
uv run just package-smoke   # isolated uv tool install and CLI smoke test
uv run just native-build    # optional MSVC-backed Nuitka onefile executable
uv run just nuitka-build    # alias for the external Nuitka build recipe
uv run just sonar-validate  # validate local Sonar/MSVC prerequisites
uv run just sonar-capture   # capture the MSVC compilation database
uv run just spec-check      # nested project checks
```

The normal change loop is:

```text
uv run just test-unit
uv run just check
uv run just test
uv run just coverage-ci
uv run just audit
```

The default `test` and coverage recipes include deterministic integration tests and exclude only
`performance`, `packaging`, and `real_asset` qualifiers. `test-without-integration` is an explicit
iteration shortcut. Packaging, real-asset, and performance checks remain separate because they
mutate temporary environments or require local external inputs.

The root Pyrefly configuration checks `src`, typed test support, and the checkout-local SonarQube
adapter; the nested project checks its own `src`. Pyrefly is authoritative for typing, deptry
validates dependency declarations, and the required CI quality workflow includes the Prospector
audit as a blocking gate. See [validate changes](docs/how-to/validate-changes.md) and the
[architecture/deployment notes](docs/explanation/architecture/deployment.md) for the local/hosted
contract, security integrations, and Pages build.

## Architecture and testing

- [Documentation site](docs/index.md)
- [Documentation style and authoring loop](docs/reference/documentation-style.md)
- [Architecture overview](docs/explanation/architecture/index.md)
- [Component boundaries](docs/explanation/architecture/components.md)
- [Generation runtime](docs/explanation/architecture/runtime.md)
- [Observability and diagnostics](docs/how-to/observability.md)
- [Testing and acceptance tiers](docs/reference/testing.md)
- [Performance commands and metrics](docs/reference/performance.md)
- [Profile the application](docs/how-to/profile-performance.md)
- [DWARF tag classification](docs/reference/dwarf/tags.md)
- [DWARF specification pipeline](tools/dwarf_spec_pipeline/README.md)
- [Goal-oriented research workflow](docs/how-to/goal-oriented-workflow.md)
- [DWARF 2-4 correctness audit](docs/knowledge-base/dwarf/dwarf2-4-correctness-audit.md)

The architecture policy is executable: `uv run just architecture` runs the pinned
ArchUnitPython rules for the `src/` hexagon and is included in both `just check` and the unit
pytest tier.

Generated headers and evidence bundles are wire-format contracts. Validate them with exact
byte-level output manifests across fresh and warm processes. The test taxonomy and rationale are
documented in the [testing reference](docs/reference/testing.md) and the [testing knowledge
base](docs/knowledge-base/testing/).
Real ELF, compressed dumps, compiler validation, and performance tests require explicit local paths
and never commit proprietary inputs or generated runtime artifacts.

Performance evidence is collected only through the opt-in `performance` command group. The
process runner uses psutil for CPU/RAM/I/O sampling and publishes checksummed raw profiler
manifests outside the checkout; historical summaries and static exports are tracked under
`resources/performance/` and `docs/knowledge-base/performance/`. Profiling is never enabled in the
normal generation path. `performance compare-runtimes` compares regular CPython, a validated
Nuitka launcher, and an explicitly installed free-threaded CPython runtime. The current warm
`rLayout` evidence shows no runtime-speed benefit from Nuitka's onefile launcher, while free-threaded
CPython uses more memory and is slower for this workload. Free-threaded Nuitka and Scalene remain
blocked by upstream/native Windows compatibility failures, and pyinstrument currently re-enables
the GIL when its native extension is imported.

## License

GPLv3-or-later; see [LICENSE](LICENSE).
