# DDON DWARF Reconstructor contributor guidance

This project extracts deterministic evidence from very large PS4 ELF/DWARF inputs. Performance is
the first constraint: avoid repeated ELF hashing, repeated full-DIE scans, whole-dump loads, and
unbounded in-memory intermediates. Preserve stable output ordering and source offsets.

## Development

- Use regular CPython 3.14.6 and install the complete development environment with
  `uv sync --python 3.14.6`.
- Use package-relative imports; do not import the package through the repository's `src` directory.
- Run fast tests with `uv run just test-unit` and the locked quality gate with `uv run just check`.
- Use `uv run ddon-dwarf-reconstructor` as the canonical unified Typer entry point. Generation uses
  `generate`, knowledge export uses `export-knowledge`, and durable maintenance is grouped under
  `artifacts`. Other launchers are implementation details, not separate behavior contracts.
- Real ELF tests are opt-in and must use explicit local paths. Never commit game binaries, dump
  files, generated headers, runtime caches, or credentials.
- The inputs for an identified DDON build are immutable. Retain deterministic SQLite indexes,
  symbol/header caches, and exports locally so fresh-process warm reruns stay fast; untracked and
  rebuildable does not mean routinely disposable.
- Key durable artifacts by source identity plus producer/schema/configuration identity, validate
  before reuse, and publish atomically. Routine cleanup must preserve them; make purge, repair, or
  rebuild narrowly targeted and explicit.
- `SourceIdentityCatalog` is the shared source-binding implementation. A warm identity may reuse a
  verified metadata key, while explicit verification rehashes the complete source; do not create
  boundary-sampling or path-only identity schemes.
- `SearchResult` is the contract for bounded targeted lookup. Preserve status and candidate
  provenance; partial results are never complete evidence and must not be consumed as complete.
- `ElfDwarfSession` owns the opened ELF/DWARF graph and one-time PS4 normalization. Generated
  headers go through `AtomicHeaderPublisher`, which writes a manifest and rolls back failed bundles.
- External inspection is an explicit artifact workflow: use `artifacts list-tool-profiles`,
  `probe-tool`, and `export-tool-evidence` for bounded one-time exports. Matching Orbis tools are
  authoritative for PS4 ABI/SCE semantics; LLVM, GNU, elfutils, libdwarf, pyelftools, LIEF, and
  OpenOrbis outputs are additive cross-checks until PS4 behavior is validated. `elfldr` is loader
  research only and must not be executed by the offline ingestion path.
- The standard non-proprietary container baseline is
  `tools/binary_toolchain/compose.yaml`. Mount explicit inputs read-only, publish outputs outside
  source control, and never copy Sony SDKs or SELF credentials into the image.

## Local acceptance artifact

- The PS4 `02020005` compressed LLVM DWARF dump is available at
  `D:\research\DDON-binaries\IDA9.3\PS4_DDON_02020005_2016_12_21\DDOORBIS.elf.llvmdwarfdump.zst`.
- It is about 1.09 GB compressed and more than 30 GB expanded. Validate compressed-dump changes
  against this artifact instead of assuming that only fixtures are available.
- The primary development machine has 64 GB RAM and a Ryzen 7800X3D. A resource-heavy explicit
  bootstrap is acceptable when it produces a persistent, source-bound index and makes subsequent
  lookups fast. Do not impose that bootstrap cost on every invocation.

## Change discipline

Preserve unrelated edits. Add focused tests for DIE traversal and evidence fidelity. Cache entries
must be fingerprinted to their inputs and written atomically. Any optimization must preserve
qualified names, inheritance, field offsets, sizes, source locations, DIE offsets, and deterministic
ordering.

## Maintainability and architecture

- Treat the following limits as maintainability guardrails for every non-generated Python file
  under `src/` and `tests/`: 600 physical lines per module, 500 lines per class (including its
  docstrings and internal documentation), 75 lines per function or method, and McCabe complexity
  of 10. Do not split a cohesive, functionally busy class solely to satisfy a line budget; split
  behavior when responsibilities, dependencies, or complexity justify it.
- Keep the dependency direction explicit: domain code may depend on domain models, ports, and the
  standard library; application code coordinates use cases through ports; infrastructure owns
  `pyelftools`, SQLite, zstd, Orbis/process integration, and filesystem adapters. Only composition
  roots construct concrete infrastructure adapters.
- Prefer typed internal contracts such as `GenerationRequest`, `HeaderBundle`,
  `DefinitionCandidate`, and type/declarator models. Breaking changes are allowed: update all
  in-repository callers, tests, and contracts together. Old import and method shapes are not
  design constraints.
- Keep one canonical implementation for definition selection, source identity, primitive and
  excluded-type classification, method evidence, special-header rendering, and array/declarator
  parsing. Do not reimplement policy in alternate generators or adapters.
- Use explicit `is not None` checks for offsets and other optional evidence; offset `0` is valid.
  Convert expected failures into specific exceptions or structured diagnostics rather than
  swallowing them with broad `except` clauses.
- New imports must be package-relative. Do not import the package through the repository's `src`
  directory, and do not make domain code aware of launchers or infrastructure details.

### Observability and exception policy

- Keep domain and application code on the standard-library logger boundary exposed by
  `core.observability`; infrastructure owns the structlog `ProcessorFormatter` configuration.
  Do not import structlog, Rich, or OpenTelemetry from domain code.
- Prefer `log_event` with stable snake_case event names and bounded fields. Bind `run_id`, command,
  source path/identity, symbol, stage, and optional `trace_id`/`span_id` at context boundaries.
  Do not log ELF/DWARF bytes, complete headers, every DIE, credentials, or unbounded subprocess
  output. Use debug for hot-loop detail, info for stage boundaries, warning for incomplete or
  recoverable evidence, and error only when an operation fails.
- Use `log_exception` or `exc_info=error` at the smallest useful boundary and preserve exception
  chaining with `raise ... from error`. The JSONL file must retain nested traceback frames; the
  stderr renderer is for human diagnosis. Do not replace an exception with `str(error)` alone.
- `LoggerSetup` must preserve foreign root handlers, emit JSONL to the configured log directory,
  and keep application diagnostics on stderr so artifact commands can reserve stdout for JSON.
  New observability behavior requires a focused test for fields, callsite data, and chained errors.

## Test and regression discipline

- Mirror the production package layout in `tests/`; put shared typed fixtures and DIE builders in
  `tests/support/`. Split tests by behavior when a test module or class approaches the structure
  limits.
- Use Hypothesis for pure type, declarator, array, and parser invariants. Use `pytest-regressions`
  only for small deterministic diagnostics, ordering records, and structured metadata; generated
  headers are validated with exact byte comparisons and SHA-256 manifests.
- Exercise incomplete, conflicting, duplicate, unavailable, cyclic, and timeout evidence paths,
  including offset `0`, malformed or stale cache artifacts, interrupted atomic writes, lock
  behavior, and warm lookup reuse.
- Maintain at least 80% total line coverage. Parsing, generation, orchestration, and artifact
  modules each require at least 80% line coverage and 70% branch coverage; keep the explicit
  failure-mode branches tested rather than excluding them from measurement.
- Every generation change must preserve qualified names, inheritance, field offsets, sizes, source
  locations, DIE/CU provenance, deterministic ordering, cache formats, and source identity. Validate
  the canonical entry point and each intentional output mode in fresh and warm-cache processes.
- Keep real-asset manifests and generated headers outside source control. Commit only deterministic
  manifests or small structured expectations that describe those external baselines.

### Test taxonomy and pyramid

- Every collected root test has exactly one scope marker: `unit`, `integration`, or `acceptance`;
  and at least one purpose marker: `functional`, `regression`, or `non_functional`. The collection
  hook in `tests/conftest.py` rejects missing or ambiguous classifications under strict markers.
- `performance`, `slow`, `real_asset`, `packaging`, and `quality` are explicit qualifiers. A
  performance or quality test must also be `non_functional`; a real-asset test must be integration
  or acceptance; a packaging test must be acceptance.
- Required deterministic integration tests are part of `uv run just test`, `coverage`, and
  `coverage-ci`. `uv run just test-without-integration` is an exceptional iteration shortcut, not
  a handoff or merge gate. Use `test-regression`, `test-non-functional`, `test-acceptance`,
  `test-real-assets`, and `test-performance` for explicit evidence slices.
- The knowledge exporter integration path must continue to run without proprietary ELF inputs;
  real PS4/PS3 inputs remain explicitly qualified environmental acceptance evidence.
- Update `docs/TESTING.md`, `docs/knowledge-base/testing/`, and the active Spec Kit feature when
  the taxonomy, test loop, test evidence, or external prerequisites change.

## Required validation

After each refactoring slice, run the smallest relevant tests plus the complete fast gate:

```text
uv run just test-unit
uv run just check
uv run just test
```

Before handoff, also run `uv run just test`, `uv run just coverage-ci`, and `uv run just audit`.
For distribution changes, also run `uv run just package` and `uv run just package-smoke`.
Use the matching just recipes so structure, architecture, typing, lint,
dependency, and duplicate/dead-code diagnostics remain part of routine development.
Ruff, Pyrefly, and deptry are authoritative for linting, formatting, production typing, and
dependency hygiene; keep Prospector focused on duplicate, dead-code, import, complexity, and
maintainability diagnostics. Run real PS4 and performance checks only with explicit local paths and
record cold/warm state, timing, and manifest identity in the relevant Spec Kit artifact. The nested
`tools/dwarf_spec_pipeline` project has its own uv lockfile and mirrors the marker vocabulary; run
its `just test`, `just test-official`, and `just check` from that project boundary as applicable.

## Spec-driven workflow

- Spec Kit 0.15.1 is initialized for Copilot skills mode under `.specify/` and
  `.github/skills/speckit-*/`.
- Project principles live in `.specify/memory/constitution.md`; feature intent and
  implementation artifacts live under `specs/<feature>/`.
- For cross-module behavior changes, use the feature sequence
  `/speckit-specify`, `/speckit-clarify`, `/speckit-plan`, `/speckit-tasks`,
  `/speckit-analyze`, implementation, and `/speckit-converge` as applicable.
- Keep ELF inputs, expanded dumps, SQLite sidecars, generated headers, caches, and
  logs outside Spec Kit feature directories and source control.
- Every task must name exact source/test paths and a validation tier; unresolved
  evidence and deferred compiler prerequisites belong in the feature artifacts.

## Goal-oriented research loop

- For multi-turn correctness work, create a thread-scoped goal whose objective names the outcome,
  evidence surface, preservation constraints, scope boundary, next iteration action, and blocked
  condition. The goal is a workflow aid, not a replacement for these repository instructions.
- Start DWARF investigations with `artifacts inspect-elf`, `artifacts inspect-dwarf-dump`, and the
  standalone specification `dwarf-spec-pipeline audit` command. For toolchain work, probe local
  `--help`/`--version` surfaces first, then run only named profiles and retain their manifests.
  Record confirmed, approximate, blocked, and remaining-uncertainty findings separately.
- After each parser or evidence slice, run the focused tests, `uv run just check`, and the required
  correctness loop before advancing. Complete the goal only when the named evidence surface passes;
  a time or token budget is never completion evidence.
