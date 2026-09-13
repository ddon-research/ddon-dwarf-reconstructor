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
- Versioned local Orbis SDK 12 CPU/ABI contracts with explicit SDK 8 history, source-bound
  `orbis-bin` utility exports, retained compiler `.s`/`.o` probes, and separate `llvm-mca`
  performance evidence.
- An exhaustive, source-derived Python module reference grouped by package layer; indexed modules
  include implementation internals and are not all stable public API.
- Source-bound implementation validation with explicit load-image, relocation, NID, ABI/CFI,
  register/stack, Orbis target-object, and static-parity evidence dimensions.
- Typed CLI, locked uv dependencies, Ruff, Pyrefly, deptry, and just automation.

## Requirements and setup

- Regular CPython 3.14.7.
- uv 0.12.3.
- An ELF file with DWARF debug information for generation.

```text
uv sync --python 3.14.7 --locked
uv run just test-unit
```

The documentation environment is the locked Zensical docs group with the preliminary
`mkdocstrings-python` integration. Regenerate the source-derived Python API pages after adding or
moving a module, then verify them before the strict site build:

```powershell
uv run just docs-api
uv run just docs-api-check
```

The analytical projection and serving runtime is part of the default project environment. Its
locked contract pins `pyarrow==25.0.0`. Verify the installed Arrow, Parquet, and
Dataset modules without loading the ELF:

```powershell
uv run python -c "import pyarrow as pa, pyarrow.dataset as ds, pyarrow.parquet as pq; print(pa.__version__, pa.default_memory_pool().backend_name, ds.__file__, pq.__file__)"
```

To install the reconstructor as a standalone uv tool from a checkout:

```text
uv tool install . --python 3.14.7
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
uv sync --directory tools/dwarf_spec_pipeline --python 3.14.7 --locked
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

# Optional PS4 method evidence and guarded reconstruction artifacts
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf \
  --dwarf-store output/analytical-dwarf/main/store-<source-sha16>/manifest.json \
  --symbol rLayout --extract-assembly --emit-implementation-sources \
  --orbis-objdump 'D:/SCE/ORBIS SDKs/8.000/host_tools/bin/orbis-objdump.exe' \
  --orbis-as 'D:/SCE/ORBIS SDKs/8.000/host_tools/bin/orbis-as.exe' \
  --llvm-readobj 'C:/msys64/ucrt64/bin/llvm-readobj.exe' \
  --llvm-objdump 'C:/msys64/ucrt64/bin/llvm-objdump.exe' \
  --llvm-target-triple x86_64-scei-ps4
```

Every `generate` request uses the same symbol-set workflow. One `--symbol` resolves that class
and its complete dependency closure. Repeated `--symbol` values or `--symbols-file` resolve one
global union, deduplicate it across all requested roots, and publish it atomically under
`generated/ps4-<client-version>/` by default (`--output` overrides the root):

```text
generated/ps4-02020005/
  symbols.manifest.json      # emitted when context generation is enabled
  shared/<dependency>.h
  rAchievement/<resource>.h
  rAchievement/<owner>-<method>-<stable-hash>.asm
```

Headers and human-readable assembly files are flat within each owner directory. Dependencies
reached by multiple roots go under `shared/`; same-name, different-content definitions receive a
deterministic identity suffix and are never overwritten. The manifest binds the ELF identity,
input-list hash, producer configuration, class/header ownership, file hashes, per-root status,
and unresolved/conflict diagnostics. Complete dependency traversal is implicit and `--single-file`
is rejected because symbol-set output is always flat. The expected regression spelling is
`rAchievement`.

Context generation is enabled by default for development and retained evidence. Use
`--no-generate-context` when the handoff must contain only generated C++ headers and assembly
files; this suppresses the manifest, implementation report, validation objects, and other
generation-context JSON.
The explicit `--generate-context` spelling is also accepted to make that intent visible in scripts.

Use `uv run ddon-dwarf-reconstructor --help` or a command’s `--help` for the complete typed
interface. Normal `generate` and `export-knowledge` runs require `--dwarf-store` and a matching
complete source publication in Doris; a missing, stale, incomplete, unavailable, or
count-mismatched publication fails closed. They never perform an implicit CU traversal or read
Parquet/JSONL at runtime. `--dwarf-dump` and `--dwarf-index` remain explicit validation-only
inputs for the legacy cross-check workflow.

The symbol-set assembly report retains raw method disassembly, decoded instructions, references,
source/file offsets, candidates, tool invocations, and explicit limitations when context generation
is enabled. With source emission enabled, uniquely matched methods receive exact-byte `.s`
compiler input and, when `orbis-as` is available, an accepted `.o` file. The core pipeline emits
no empty, reference, or diagnostic placeholder C++ files. Ambiguous and unavailable methods remain
evidence only.

Symbol-set assembly uses the same additive evidence boundary but writes one flat `.asm` namespace per
resource (and `shared/` for shared methods) beside the headers. Each `.asm` begins with semicolon
comments for the method/definition signature, pseudo-symbol, address/range, file offset, source
location, ABI/type facts, and evidence status; available calls are recorded as `; pseudo_call:`
comments. Exact-byte `.s` and accepted `.o` files are separate opt-in artifacts and are never
confused with the readable IDA-style export. Source references in readable exports are always
semicolon comments; the structured/raw disassembly remains in the report/cache.

The latest full Season 2 rerun covered all 289 roots, checked 2,760 header files, and emitted
1,150 complete assembly handoff bundles with exact raw/report and object/text parity. It remains
`observed-partial` until the independent Doris-backed relocation, NID, ABI/CFI, safety, and static
parity gates are observed; independent MSVC declaration closure passed 2,760/2,760 units, and
live PS4 behavior is not observed. See the
[`Season 2 acceptance record`](specs/001-header-foundation/acceptance-season2-assembly-20260816.md)
for measured counts, the cache repair, and the isolated IDA completeness audit.

Run the read-only validator against the complete analytical store when method-specific DWARF
locations and CFI are needed. Keep the address policy explicit; `--original-addresses` uses ELF
virtual addresses, while `--load-base` must be aligned to the PS4 image policy. The validator
emits canonical `.s` files and accepted `.o` files only in the external validation directory;
it reports CFG/call-edge parity, unresolved loader state, and live behavior separately rather than
promoting them. Supply `--orbis-objdump` to observe normalized generated-object edges; `--orbis-ld`
is optional and records a relocatable link result.
The supplied analytical manifest pins the source-bound publication; method DIE, location, and CFI
rows are queried from Doris, never read directly from Parquet/JSONL. Set the existing
`DDON_DORIS_SQL_HOST`, `DDON_DORIS_SQL_PORT`, `DDON_DORIS_DATABASE`, and `DDON_DORIS_TABLE`
settings before running the command.

SDK 12 is the promoted host-tool profile; SDK 8 is historical and requires an explicit SDK root.
Use repeatable `--tool-evidence` options for complete `orbis-bin` manifests and
`--abi-probe-manifest` for the retained compiler matrix. The default `--assembly-profile
byte-replay` preserves canonical `.text` byte replay; opt-in `--assembly-profile sectioned`
checks `.text.<symbol>` and `EF_FFUNC_DATA_SECS_ENABLED`. The current implementation-validation
report schema is `4.4`, while the implementation-discovery report remains `4.2`. Schema-4.3
reports remain readable but default static-equivalence disposition to `not_promoted`.

See [Validate local Orbis CPU/ABI evidence](docs/how-to/validate-orbis-toolchain.md) for the
offline SDK 12 profiles, local documentation provenance, Sysmodule/NID distinction, and the
separate marked-assembly `performance analyze-assembly` workflow. Keep all SDK outputs, probe
manifests, and `llvm-mca` artifacts under `%TEMP%` or another external evidence directory.

Validation hydrates method context through deterministic Doris batches of 512 requests and builds
relocation/NID indexes once per run. The bounded SDK 12 `rLayout` acceptance retained target
objects for all 26 code-bearing methods; 17 are `target_object_equivalent` and 9 remain
`not_promoted` because source-bound return-type/ABI facts are incomplete. The full Season 2
validator remains deferred, and live behavior remains `not_observed`. No arbitrary timeout is used
as completion evidence.

### SDK 12 disassembly refactor parity baseline

On 2026-08-18 the complete 289-root Season 2 set was regenerated before and after the disassembly
refactor with SDK `12.000`, full hierarchy, assembly extraction, and implementation-source emission.
The source-bound baseline and post-refactor outputs are external evidence under
`C:\Users\morph\AppData\Local\Temp\ddon-disassembly-refactor-20260818\baseline` and
`C:\Users\morph\AppData\Local\Temp\ddon-disassembly-refactor-20260818\post`;
the configuration and strict comparison are recorded in `baseline-config.json` and
`comparison.json`. The versioned manifests are `disassembly-regression/1`, both have SHA-256
`db59e07ebaf34ccd582065223b79897b3a75bc64352343497c2f56519cda3533`, and the comparison reports
zero differences.

The matched aggregate is 289 roots, 2,745 headers, 83,754 method entries, 60,117 unique method
identities, 4,504 artifact descriptors, 289 implementation reports/source bundles, and 8,116
files totaling 354,480,609 bytes. The comparison requires exact header, assembly, object, context,
identity, descriptor, and normalized evidence equality; only explicitly allowlisted runtime paths
and timing fields are normalized. This current SDK 12 baseline is separate from the historical
2,760-header/MSVC record and does not promote ABI, semantic, or live-behavior equivalence.

```powershell
uv run ddon-dwarf-reconstructor artifacts validate-implementation resources/DDOORBIS.elf `
  --implementation-report output/ps4/implementations/0001-rLayout.json `
  --dwarf-store output/analytical-dwarf/main/store-<source-sha16>/manifest.json `
  --output-dir $env:TEMP/ddon-implementation-validation `
  --original-addresses `
  --sdk-root 'D:/SCE/ORBIS SDKs/12.000'
```

Use `--tool-timeout-seconds <positive-seconds>` only for an explicitly bounded SDK validation
run. The default has no arbitrary tool timeout and the validator keeps hashes/statuses rather than
per-tool stdout/stderr files. No method `.cpp` files are generated; the optional ABI probe matrix
may retain its eight small compiler probe sources, while the method handoff remains `.raw.asm`,
`.s`, `.o`, and `.context.json`.

The implementation report is schema `4.2` and includes the DWARF-derived target manifest, scope
hash, all retained function candidates, and match reasons. IDA is isolated to a post-generation
completeness audit:

```powershell
uv run ddon-dwarf-reconstructor artifacts audit-implementation-coverage `
  --implementation-report output/ps4/implementations/0001-rLayout.json `
  --ida-c-dump <ida-export.c> --elf resources/DDOORBIS.elf `
  --output-dir $env:TEMP/ddon-implementation-audit
```

The audit cannot modify Doris targets, production names/addresses, caches, compiler inputs, or
statuses; an IDA body absence is not evidence of DWARF method absence.

The evidence chain has three boundaries: Orbis binutils is authoritative for PS4 instruction
decoding and demangling; optional LLVM `llvm-readobj` metadata and `llvm-objdump --triple` slices
are additive generic/structural cross-checks; and the in-repository SCE metadata reader decodes
`PT_SCE_DYNLIBDATA` and 24-byte RELA tables. Conventional Orbis relocation output being empty and
the SDK dynamic-relocation limitation do not mean the ELF has no relocations; the unsupported
profile is capability-filtered from normal runs. Complete
SCE entries remain in the source-bound JSONL cache, while the implementation report projects only
method-relevant entries. The SDK dynamic-relocation limitation is capability-filtered from normal
generation and documented rather than retried. `llvm-tli-checker` is not used for ELF extraction.

When the analytical-dwarf Compose stack remaps the FE SQL port on the workstation, keep the
application endpoint aligned with that host mapping. For example, the container may still listen
on `9030` while Windows publishes it as `19030`; set `DDON_DORIS_SQL_HOST=127.0.0.1` and
`DDON_DORIS_SQL_PORT=19030` before generation. A refusal at the default `9030` is an endpoint
configuration failure, not evidence that the running Doris service is unavailable.

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

Transient test and documentation outputs are separate from durable evidence. Review the
[artifact retention contract](specs/001-header-foundation/contracts/artifact-retention.md) before
cleanup; the only repository cleanup recipe is the narrow, explicit `just clean-transient`, which
does not target `output/`, `resources/`, `logs/`, source-bound caches, or retained external reports.

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

The Linux compatibility and profiler image is documented in
[`ops/reconstructor/README.md`](ops/reconstructor/README.md). It pins CPython 3.14.7 and uv 0.12.3,
mounts the checkout read-only, publishes logs/output/profiler artifacts to host paths, and enables
the `SYS_PTRACE` capability only for the opt-in py-spy service:

```text
uv run just reconstructor-container-config
docker compose --file ops/reconstructor/compose.yaml build
docker compose --file ops/reconstructor/compose.yaml run --rm reconstructor performance doctor
```

The image is a profiling and Linux-compatibility boundary, not a replacement for the normal host
workflow. Doris remains the separate analytical service, and proprietary inputs stay outside image
layers and source control.

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
uv run just reconstructor-container-config # validate Linux profiling Compose files
uv run just performance-history # export tracked benchmark history
uv run just docs-tools-install # install locked Markdown/Mermaid validators
uv run just docs-api          # regenerate source-derived Python API pages
uv run just docs-api-check    # fail when generated API pages are stale or incomplete
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
- [Python API reference](docs/api/index.md)
- [Architecture overview](docs/explanation/architecture/index.md)
- [Component boundaries](docs/explanation/architecture/components.md)
- [Generation runtime](docs/explanation/architecture/runtime.md)
- [Architecture review evidence](specs/021-cpp-reconstruction-architecture/measured-evidence.md)
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
