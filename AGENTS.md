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
  `artifacts`. If the native launcher remains, test that it produces byte-identical exports.
- Real ELF tests are opt-in and must use explicit local paths. Never commit game binaries, dump
  files, generated headers, runtime caches, or credentials.
- The inputs for an identified DDON build are immutable. Retain deterministic SQLite indexes,
  symbol/header caches, and exports locally so fresh-process warm reruns stay fast; untracked and
  rebuildable does not mean routinely disposable.
- Key durable artifacts by source identity plus producer/schema/configuration identity, validate
  before reuse, and publish atomically. Routine cleanup must preserve them; make purge, repair, or
  rebuild narrowly targeted and explicit.

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

- Treat the following limits as hard gates for every non-generated Python file under `src/` and
  `tests/`: 400 physical lines per module, 250 lines per class, 75 lines per function or method,
  and McCabe complexity of 10. Do not add baseline exemptions; decompose the behavior instead.
- Keep the dependency direction explicit: domain code may depend on domain models, ports, and the
  standard library; application code coordinates use cases through ports; infrastructure owns
  `pyelftools`, SQLite, zstd, Orbis/process integration, and filesystem adapters. Only composition
  roots construct concrete infrastructure adapters.
- Prefer typed internal contracts such as `GenerationRequest`, `HeaderBundle`,
  `DefinitionCandidate`, and type/declarator models. Preserve public compatibility façades and
  thin re-exports when callers may rely on existing imports or methods.
- Keep one canonical implementation for definition selection, source identity, primitive and
  excluded-type classification, method evidence, special-header rendering, and array/declarator
  parsing. Do not reimplement policy in legacy generators or adapters.
- Use explicit `is not None` checks for offsets and other optional evidence; offset `0` is valid.
  Convert expected failures into specific exceptions or structured diagnostics rather than
  swallowing them with broad `except` clauses.
- New imports must be package-relative. Do not import the package through the repository's `src`
  directory, and do not make domain code aware of compatibility or infrastructure details.

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
  locations, DIE/CU provenance, deterministic ordering, cache formats, and source identity. Compare
  canonical and compatibility entrypoints when both exist, in fresh and warm-cache processes.
- Keep real-asset manifests and generated headers outside source control. Commit only deterministic
  manifests or small structured expectations that describe those external baselines.

## Required validation

After each refactoring slice, run the smallest relevant tests plus the complete fast gate:

```text
uv run just test-unit
uv run just check
```

Before handoff, also run `uv run just test`, `uv run just coverage-ci`, and `uv run just audit`.
Use `scripts/check.ps1` or the matching just recipes so structure, boundary, typing, lint,
dependency, and duplicate/dead-code diagnostics remain part of routine development.
Ruff, Pyrefly, and deptry are authoritative for linting, formatting, production typing, and
dependency hygiene; keep Prospector focused on duplicate, dead-code, import, complexity, and
maintainability diagnostics. Run real PS4 and
performance checks only with explicit local paths and record cold/warm state, timing, and manifest
identity in the relevant Spec Kit artifact.

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
