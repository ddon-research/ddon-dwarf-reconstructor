# Structured logging and exception tracing

## Decision

Use the standard-library logging API at the core/domain/application boundary,
with structlog's standard-library `ProcessorFormatter` installed by
infrastructure. Emit one bounded event per meaningful stage to:

- a timestamped JSONL file at DEBUG level for offline investigation;
- a human-readable stderr stream at INFO by default, with DEBUG under
  `--verbose` and Rich chained tracebacks without local-variable dumps.

This keeps existing `logging.Logger` callers compatible, gives us structured
fields and nested exception data now, and avoids making domain policy depend on
an observability vendor or exporter.

## Why this fits the reconstructor

The application processes very large immutable inputs. A useful event identifies
the command/run, source identity, symbol, stage, offsets, evidence status,
counts, and duration. It must not materialize or log the entire dump, every DIE,
generated headers, or arbitrary subprocess output. The source-bound artifact
and search contracts remain authoritative; logs explain their decisions but do
not change them.

The core facade provides:

```python
with bind_context(run_id=run_id, symbol=symbol):
    log_event(logger, logging.INFO, "symbol_started", stage="generation")
    try:
        result = operation()
    except Exception as error:
        log_exception(logger, "symbol_failed", error, stage="generation")
        raise
```

Context is scoped with `contextvars`, so nested symbol/stage operations do not
leak fields into the next request. The renderer adds UTC timestamps, logger and
level, callsite filename/line/function, and structured traceback records.

## Alternatives considered

| Option | Decision | Reason |
| --- | --- | --- |
| stdlib logging only | Keep as API, not renderer | Stable and dependency-free, but JSON/chained exception shaping would be repeated in adapters |
| structlog everywhere | Reject as boundary contract | Excellent structured processing, but direct imports would couple domain policy to infrastructure |
| loguru | Reject | Attractive single-logger API, but less aligned with existing logger hierarchy and future stdlib/OTel bridges |
| full OpenTelemetry SDK now | Defer | Adds exporter/runtime policy before the local event contract is stable; use reserved trace fields first |
| unbounded Rich locals | Reject | Helpful interactively but can expose huge or sensitive parser state and overwhelm logs |

## Evidence reviewed

The design follows the Python logging guidance on hierarchical loggers,
propagation, handler ownership, `extra`, `exc_info`, `stack_info`, and
`stacklevel`; Python traceback formatting preserves chained causes by default.
Structlog's stdlib integration supports shared processors for stdlib and
structlog records, JSON rendering, and structured exception dictionaries.
OpenTelemetry Python provides a future traces/metrics/logs integration point;
trace/span identifiers are reserved as top-level fields in JSON records.

Primary references:

- [Python logging](https://docs.python.org/3/library/logging.html)
- [Python logging HOWTO](https://docs.python.org/3/howto/logging.html)
- [Python traceback](https://docs.python.org/3/library/traceback.html)
- [structlog getting started](https://www.structlog.org/en/stable/getting-started.html)
- [structlog standard-library integration](https://www.structlog.org/en/stable/standard-library.html)
- [structlog exceptions](https://www.structlog.org/en/stable/exceptions.html)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [OpenTelemetry log trace context](https://opentelemetry.io/docs/specs/otel/compatibility/logging_trace_context/)
- [Rich stack traces without exception-only logging](https://www.bugsink.com/blog/capture-stacktrace-no-exception/)

The supplied comparison articles were useful for trade-off review, but the
runtime contract is anchored in primary Python, structlog, and OpenTelemetry
documentation.

Comparative references reviewed during the design pass:

- [Highlight Python logging comparison](https://www.highlight.io/blog/5-best-python-logging-libraries)
- [Dash0 Python logging libraries](https://www.dash0.com/guides/python-logging-libraries)
- [Real Python logging best practices](https://realpython.com/ref/best-practices/logging/)
- [Better Stack Python logging practices](https://betterstack.com/community/guides/logging/python/python-logging-best-practices/)
- [Python errors tutorial](https://docs.python.org/3/tutorial/errors.html)
- [Python built-in exceptions](https://docs.python.org/3/library/exceptions.html)
- [Real Python exception handling](https://realpython.com/python-exceptions/)
- [Miguel Grinberg error handling](https://blog.miguelgrinberg.com/post/the-ultimate-guide-to-error-handling-in-python)
- [Real Python exception best practices](https://realpython.com/ref/best-practices/exception-handling/)
- [Exception handling patterns](https://jerrynsh.com/python-exception-handling-patterns-and-best-practices/)
- [Mimo error handling guide](https://mimo.org/glossary/python/error-handling)
- [Combining Python trace information and logging](https://stackoverflow.com/questions/63404899/combining-python-trace-information-and-logging)

## Follow-up

An OpenTelemetry slice can add an infrastructure-only processor/handler that
reads the active context and populates `trace_id`, `span_id`, and `trace_flags`,
while retaining JSONL when no exporter is configured. It should also record the
same exception on the active span, preserve local source identity fields, and
be validated against cold/warm generation timing before enabling exporters by
default.
