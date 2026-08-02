# Feature Specification: Structured Observability and Error Diagnostics

**Feature Branch**: `007-observability-and-error-diagnostics`

**Status**: Selected implementation slice complete; real PS4/performance acceptance is
deferred until explicitly selected; full quality-gate convergence is recorded in `tasks.md`.

## Goal

Make one generation or artifact-maintenance run diagnosable from its logs. A
developer should be able to identify the run, symbol, stage, source identity,
cache/index decision, duration, and complete chained exception without
reproducing a 30+ GB input immediately.

## User stories and priorities

### P1 — Pinpoint one failed symbol

When a batch generation fails for one symbol, the developer can filter one
JSONL run by `run_id` and `symbol`, see the failed stage and callsite, and read
the nested exception chain with source line references. Other symbols retain
their existing partial-success behavior.

### P2 — Explain stage and artifact behavior

When a lookup is slow, incomplete, unavailable, or unexpectedly cold, the
developer can distinguish cache reuse, source rehash, dump-index build, bounded
search timeout, header rendering, and atomic publication from one bounded
sequence of events with counts and durations.

### P3 — Preserve an OpenTelemetry seam

When tracing is enabled in a future infrastructure change, active trace/span
context can be added to records and spans without importing a telemetry SDK into
domain policies or changing evidence/output contracts.

## Functional requirements

- **OBS-001**: The runtime MUST expose a standard-library logging facade with
  structured event fields, scoped context, exception helpers, and timing.
- **OBS-002**: The CLI MUST emit JSONL diagnostics to a timestamped file and
  human-readable diagnostics to stderr; artifact command stdout MUST remain
  valid machine-readable JSON.
- **OBS-003**: JSONL records MUST include stable event names, UTC timestamps,
  logger/level, callsite filename/line/function, and bounded fields for run,
  command, symbol/stage, source identity, status, counts, offsets, and duration
  when observed.
- **OBS-004**: Error records MUST preserve `exc_info`, chained
  `__cause__`/`__context__`, nested frames, and source line references. Error
  translation MUST preserve the chain with `raise ... from error`.
- **OBS-005**: Critical lifecycle boundaries MUST emit start/completion/failure
  or explicit partial/unavailable events for generation, ELF/DWARF session,
  bounded search, durable identity/cache/index, Orbis evidence, and atomic
  header publication.
- **OBS-006**: Hot loops MUST NOT emit one info/error record per DIE,
  instruction, or source line. Lists, subprocess output, and previews MUST be
  bounded.
- **OBS-007**: Domain and application policy code MUST NOT import structlog,
  Rich, or OpenTelemetry. Infrastructure MUST own renderer configuration and
  future telemetry adapters.
- **OBS-008**: Focused tests MUST verify context reset, JSON field shape,
  callsite data, chained exceptions, handler preservation, and affected failure
  paths.

## Non-goals

- Enabling an OpenTelemetry exporter or network telemetry by default.
- Capturing every parser loop iteration or full input/output objects.
- Changing generated headers, evidence status, cache schema, source identity, or
  deterministic ordering.
- Committing runtime logs, ELF/DWARF inputs, expanded dumps, or derived indexes.

## Acceptance criteria

1. `tests/infrastructure/test_logging.py` proves JSONL rendering, context
   scoping, callsites, nested exceptions, and foreign-handler preservation.
2. Critical code paths use bounded structured lifecycle events and
   `exc_info`/exception chaining at failure boundaries.
3. `uv run just test-unit`, `uv run just check`, `uv run just test`,
   `uv run just coverage-ci`, and `uv run just audit` pass, or any deferred
   prerequisite is recorded here and in `tasks.md`.
4. A fresh-process generation run keeps stdout/output artifacts unchanged and
   writes a source-bound JSONL record stream to the configured log directory.
5. The instruction surfaces, architecture/readme/testing/generation-flow docs,
   knowledge base, and this feature package agree on the logging contract.
