# Observability contract

## Record shape

The JSONL renderer emits one JSON object per record. `event`, `level`, `logger`,
`timestamp`, `filename`, `lineno`, and `func_name` are present for records
produced after `LoggerSetup.initialize`. Context and event fields are present
when observed.

```json
{
  "timestamp": "2026-08-03T12:34:56.123456Z",
  "level": "error",
  "logger": "ddon_dwarf_reconstructor.main",
  "event": "symbol_failed",
  "filename": "main.py",
  "lineno": 190,
  "func_name": "_record_failure",
  "run_id": "opaque-run-id",
  "command": "generate",
  "symbol": "rLayout",
  "source_path": "D:/research/DDON-binaries/DDOORBIS.elf",
  "status": "unavailable",
  "duration_ms": 12.5,
  "exception": [
    {"exc_type": "RuntimeError", "exc_value": "outer", "frames": []},
    {"exc_type": "ValueError", "exc_value": "inner", "frames": []}
  ]
}
```

The exact traceback frame fields are owned by structlog's structured traceback
processor; consumers must treat unknown additional fields as forward-compatible.

## Severity contract

| Level | Use |
| --- | --- |
| DEBUG | bounded detail, cache hits, component timing, candidates, lock/schema diagnostics |
| INFO | command/session/stage start or completion, index scan, publication, summary |
| WARNING | partial/unavailable evidence, stale/recoverable artifact, unknown platform |
| ERROR | failed operation, rollback, durable write failure, unexpected boundary failure |

## Reserved telemetry fields

`trace_id`, `span_id`, and `trace_flags` are reserved for an infrastructure-only
OpenTelemetry adapter. They must be lower-case top-level fields when present and
must not be synthesized by domain code.

