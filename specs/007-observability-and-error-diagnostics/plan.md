# Implementation Plan: Structured Observability and Error Diagnostics

The implementation preserves the existing hexagonal boundary: the core facade
uses only the standard library, application/domain code emits events through it,
and infrastructure configures structlog and Rich. No telemetry SDK is added in
this slice.

## Phase 0 — Baseline and design, completed

- Inventory `src/`, `tests/`, `AGENTS.md`, Copilot/Python/Claude instructions,
  architecture/readme/testing/spec/knowledge-base documents, and `justfile`.
- Review the supplied Python logging/traceback, structlog, comparison-library,
  and OpenTelemetry references.
- Select JSONL plus stderr rendering, stable event names, scoped context, and
  chained exception records as the local contract.

Validation: repository inventory, reference notes, dependency resolution.

## Phase 1 — Core logging boundary, completed

- Update `src/ddon_dwarf_reconstructor/core/observability.py` with contextvars,
  `bind_context`, `current_context`, `log_event`, `log_exception`, and low-noise
  timing events.
- Update `src/ddon_dwarf_reconstructor/infrastructure/logging/logger_setup.py`
  with structlog `ProcessorFormatter`, JSONL rendering, Rich stderr rendering,
  callsite fields, bounded object encoding, handler ownership, and test teardown.
- Update `progress_tracker.py` and logging exports.
- Add `structlog` and direct `rich` runtime dependencies in `pyproject.toml`
  and `uv.lock`.

Validation: `tests/infrastructure/test_logging.py`, compile, Ruff.

## Phase 2 — P1 critical paths, completed

- Instrument `main.py`, generator orchestration, header generation, atomic
  publication, ELF session/platform detection, and artifact CLI boundaries.
- Instrument bounded search and parser fallback paths while preserving
  `SearchResult` status/provenance and partial evidence semantics.
- Instrument source identity, symbol cache, compressed dump index/scan/query,
  and Orbis objdump lifecycle/exception paths.
- Add `exc_info` to critical parser/cache fallback diagnostics without logging
  unbounded data.

Validation: focused infrastructure/domain/application unit tests and full Ruff.

## Phase 3 — Documentation and instruction convergence, completed

- Update `AGENTS.md`, `.github/copilot-instructions.md`,
  `.github/instructions/python.instructions.md`, and `CLAUDE.md`.
- Update `README.md`, `docs/ARCHITECTURE.md`, `docs/TESTING.md`,
  `docs/GENERATION_FLOWS.md`, and `docs/README.md`.
- Add `docs/OBSERVABILITY.md` and the observability knowledge-base note.
- Add this feature's event contract and research record.

Validation: documentation links/search, instruction consistency, quality gates.

## Phase 4 — Acceptance and convergence, completed for the selected scope

- Run the required unit, static, full non-performance, coverage, and audit
  recipes in fresh processes; record the results in `tasks.md`.
- Run package gates because runtime dependencies changed; both package gates
  passed. Explicit real PS4/performance checks remain deferred until selected
  with the named local input paths.
- Inspect the diff for log spam, sensitive/unbounded fields, output changes,
  and preservation of the pre-existing `resources/.cache/` user artifact.

## Exact implementation surfaces

| Concern | Source | Tests |
| --- | --- | --- |
| facade/renderers | `core/observability.py`, `infrastructure/logging/` | `tests/infrastructure/test_logging.py` |
| command context | `main.py`, `artifact_cli.py` | `tests/test_main*.py`, artifact CLI tests |
| session/generation | `application/generators/`, `infrastructure/elf_*.py`, `header_output.py` | matching application/infrastructure tests |
| search/evidence | `domain/services/lazy_index_*.py`, class-parser fallbacks | `tests/domain/services/` |
| durable artifacts | `infrastructure/artifacts.py`, `zstd_dump_*.py`, cache repository | matching artifact/cache tests |
