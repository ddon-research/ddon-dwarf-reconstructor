# Tasks: Structured Observability and Error Diagnostics

**Input**: `spec.md`, `research.md`, `plan.md`, and `contracts/observability.md`

**Status**: Implementation and documentation delivered; final full-gate results
are recorded during convergence.

## Phase 1 — Foundation

- [x] T001 Inventory existing logger setup, exception catches, critical paths,
  instruction surfaces, specs, docs, and validation recipes. **Tier 1**
- [x] T002 Add `structlog` and direct `rich` dependencies and refresh `uv.lock`.
  **Tier 1**
- [x] T003 Implement scoped context, structured events, chained exception
  helpers, and timing in `core/observability.py`. **Tier 1**
- [x] T004 Implement JSONL/Rich stderr rendering, callsite fields, bounded
  values, handler ownership, reconfiguration, and shutdown in
  `infrastructure/logging/logger_setup.py`. **Tier 1**
- [x] T005 Add focused field/traceback/handler tests in
  `tests/infrastructure/test_logging.py`. **Tier 1**

## Phase 2 — Critical paths

- [x] T006 Instrument CLI run/symbol context and summary in `main.py` and
  artifact operation boundaries in `artifact_cli.py`. **Tier 1**
- [x] T007 Instrument generator/session/header lifecycle in
  `application/generators/`, `elf_session.py`, `elf_platform.py`, and
  `header_output.py`. **Tier 1/2**
- [x] T008 Instrument bounded search, partial/timeout/unavailable outcomes, and
  critical parser fallback tracebacks. **Tier 1**
- [x] T009 Instrument source identity, symbol cache, dump index/scan/query,
  and Orbis producer cache/subprocess boundaries. **Tier 1/2**
- [x] T010 Preserve existing output/evidence semantics, including cache save
  failure behavior and partial `SearchResult` provenance. **Tier 1**

## Phase 3 — Documentation and tooling loop

- [x] T011 Update `AGENTS.md`, Copilot, Python, and Claude instructions with
  event/severity/exception and dependency-boundary rules. **Tier 1**
- [x] T012 Add the observability how-to and update README, architecture, testing,
  generation-flow, docs index, and knowledge-base index. **Tier 1**
- [x] T013 Add this Spec Kit package and the typed event contract. **Tier 1**
- [x] T014 Re-run the complete fast/static/full/coverage/audit gates and record
  exact outcomes below. **Tier 2**
- [ ] T015 Run explicit real PS4/performance acceptance only with selected local
  paths; record source identity, cold/warm state, timings, and log artifact
  identity. **Tier 3** Deferred: no real-asset/performance run was selected for
  this observability slice; the explicit local asset path remains documented in
  `AGENTS.md`.

## Validation record

- Focused logging + main error paths: passed; focused infrastructure/domain/
  application slice passed with 267 tests and 3 deselected.
- `uv run just test-unit`: 407 passed, 21 deselected.
- `uv run just check`: passed (Ruff, format, Pyrefly, deptry, structure,
  architecture).
- `uv run just test`: 426 passed, 2 deselected.
- `uv run just coverage-ci`: 426 passed, 2 deselected; total 86.59% pytest
  coverage; named groups passed at lines 86.5%–93.8% and branches 73.4%–79.7%.
- `uv run just audit`: passed with zero Prospector messages.
- `uv run just package`: source distribution and wheel built successfully.
- `uv run just package-smoke`: packaging CLI smoke test passed.
- Real PS4/compiler/performance: deferred until explicitly selected; no
  proprietary artifacts belong in this feature directory.
