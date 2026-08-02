# Research: Structured Observability and Error Diagnostics

## Findings

1. The codebase already had a wide standard-library logger surface and a timing
   decorator, but setup cleared every root handler, emitted text-only files,
   used f-string messages, and often discarded exception traceback context.
2. The highest-value boundaries are the CLI run/symbol scope, ELF/DWARF session,
   bounded search result, source identity and durable cache/index decisions,
   Orbis subprocess execution, and atomic header publication. Logging each DIE
   or instruction would make a large-input run less useful.
3. `logging.Logger` remains the right internal contract. It supports hierarchy,
   propagation control, `extra`, `exc_info`, `stack_info`, and `stacklevel`, and
   it avoids coupling domain policies to a renderer.
4. Structlog's standard-library integration can process both existing stdlib
   records and structlog records. Its JSON renderer and structured traceback
   processor provide the desired machine-readable nested exception shape, while
   its Rich formatter provides human-readable chained traces.
5. OpenTelemetry is a future seam rather than a current default. Reserved
   `trace_id`, `span_id`, and `trace_flags` context fields allow an
   infrastructure-only bridge later; deterministic offline runs still need a
   local JSONL fallback.

## Decision record

Adopt `structlog>=26.1,<27` and `rich>=13,<16` as runtime dependencies. Keep
the standard-library facade in `core.observability`; install a root
`ProcessorFormatter` only in `LoggerSetup`. File output is JSONL with UTC
timestamps, callsite fields, bounded values, and `dict_tracebacks`. Stderr uses
Rich tracebacks with `show_locals=False` and an INFO/DEBUG threshold controlled
by `--verbose`.

The application binds context with `contextvars` rather than global mutable
state. Event names are stable and fields are bounded. Source identity and
evidence statuses remain producer facts; log records do not promote partial
results or mutate caches.

## Rejected approaches

- Replacing the existing logger API with loguru would create a second hierarchy
  and weaken the future stdlib/OTel bridge.
- Importing structlog in domain code would violate the dependency direction and
  make renderer changes a policy change.
- Adding an exporter now would introduce network/runtime behavior before local
  event names, field bounds, and performance baselines are stable.
- Full Rich locals or per-DIE debug logs would increase privacy, volume, and
  memory risks without improving first-stage diagnosis.

## Sources

- [Python logging](https://docs.python.org/3/library/logging.html)
- [Python traceback](https://docs.python.org/3/library/traceback.html)
- [structlog getting started](https://www.structlog.org/en/stable/getting-started.html)
- [structlog standard-library integration](https://www.structlog.org/en/stable/standard-library.html)
- [structlog exceptions](https://www.structlog.org/en/stable/exceptions.html)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [OpenTelemetry logging trace context](https://opentelemetry.io/docs/specs/otel/compatibility/logging_trace_context/)
- User-supplied comparison references are listed in the observability knowledge
  base; primary sources anchor the implementation contract.

