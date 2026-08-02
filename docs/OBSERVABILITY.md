# Observability and exception diagnostics

The reconstructor treats logs as bounded evidence about a run, not as a dump of
the DWARF input. The goal is to locate the failing stage, symbol, source
identity, and exception line quickly while preserving deterministic output and
the performance characteristics of the parser.

## Runtime design

The boundary is intentionally hybrid:

```text
domain/application -> core.observability (stdlib Logger + typed helpers)
                   -> infrastructure LoggerSetup
                   -> structlog processors
                   -> JSONL file + human stderr renderer
```

`structlog` is a rendering and processor adapter, not a domain dependency.
`LoggerSetup` uses the standard-library `ProcessorFormatter`, so existing
stdlib loggers and future structlog/telemetry emitters share the same schema.
The JSON file is always DEBUG-capable; stderr is INFO unless `--verbose` is
selected. Artifact commands keep their result JSON on stdout and send logs to
stderr.

## Event contract

Every record has a stable event name and common metadata. Fields are optional
when they are not observed; do not invent evidence.

| Field | Meaning |
| --- | --- |
| `timestamp` | UTC ISO-8601 emission time |
| `level`, `logger`, `event` | severity, producer module, stable event name |
| `filename`, `lineno`, `func_name` | source callsite for pinpoint diagnosis |
| `run_id`, `command` | one CLI invocation and its operation |
| `symbol`, `symbol_index`, `symbol_count` | current bounded symbol scope |
| `source_path`, `source_sha256`, `source_size` | immutable input binding |
| `stage`, `status`, `duration_ms` | lifecycle and performance evidence |
| `cu_offset`, `die_offset`, `candidate_score` | DWARF lookup provenance |
| `trace_id`, `span_id`, `trace_flags` | reserved telemetry context fields |

Event names use lower-case `snake_case`. Data is bounded: file lists and failed
symbol lists are sampled, subprocess diagnostics are truncated, and full
headers, DWARF lines, bytes, credentials, and arbitrary object graphs are never
logged.

## Severity policy

- `DEBUG`: cache hits, bounded search candidates, component timing, lock and
  schema diagnostics, and details useful when `--verbose` or a JSONL file is
  being investigated.
- `INFO`: command, generator/session, dump scan, header publication, and symbol
  stage boundaries. These should remain understandable when read linearly.
- `WARNING`: partial or unavailable evidence, unknown platform, stale-lock
  recovery, malformed reusable artifacts, and non-fatal fallback behavior.
- `ERROR`: an operation failed, publication rolled back, or durable state could
  not be written. Include `exc_info` so nested causes and source line frames are
  retained.

Hot loops must not emit one record per DIE, instruction, or source line. A
single completion event with counts and duration is preferred.

## Exception rules

Catch the narrowest exception set at the boundary that can make a decision. Use
`raise NewError("context") from error` when translating an exception. Use
`log_exception` or `exc_info=error` before returning an explicit unavailable or
partial result. The file renderer uses structured tracebacks, including chained
`__cause__`/`__context__` records; the stderr renderer uses Rich without local
variable dumps to prevent sensitive or high-volume output.

Expected fallbacks must remain visible. For example, an invalid warm cache can
be rebuilt, but the log should say why it was rejected and include the relevant
path and source identity. An unexpected error must reach the command boundary
with its chain intact rather than being converted to a bare string.

## Troubleshooting loop

```powershell
# Generate with human-readable stage progress and DEBUG stderr events
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf `
  --symbol rLayout --verbose

# Inspect the most recent JSONL records without changing artifacts
$log = Get-ChildItem logs -Filter 'ddon_reconstructor_*.jsonl' |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
Get-Content $log.FullName | ConvertFrom-Json |
  Where-Object { $_.event -in @('symbol_failed', 'generation_failed') }
```

Start with `run_id`, then narrow to `symbol`, `stage`, and source identity.
For a failure, inspect `exception` and its nested frames before changing the
parser. Compare `duration_ms`, cache-hit events, and `cus_searched` to determine
whether a regression is correctness, invalidation, or performance.

## OpenTelemetry extension path

No OpenTelemetry SDK is required for the current deterministic CLI. The
reserved trace fields and context scope let a future adapter inject the active
span identifiers and translate lifecycle events without changing domain
interfaces. When that work is selected, add SDK/exporter dependencies only in
infrastructure, map `run_id`/`symbol` to span attributes, and record exceptions
on the active span as well as the log record. Keep JSONL as a local fallback for
offline reverse-engineering runs.

The design follows the standard-library logging controls for hierarchical
loggers, propagation, `exc_info`, `stack_info`, `stacklevel`, and `extra`, plus
structlog's stdlib integration and structured traceback processors. See the
[Python logging documentation](https://docs.python.org/3/library/logging.html),
[Python traceback documentation](https://docs.python.org/3/library/traceback.html),
[structlog standard-library integration](https://www.structlog.org/en/stable/standard-library.html),
[structlog exception handling](https://www.structlog.org/en/stable/exceptions.html), and
[OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/).
