# Operational observability

The runtime logging boundary is the standard-library facade in `core.observability`. Infrastructure
configures structlog rendering and the JSONL file; domain and application code do not import
structlog, Rich, or OpenTelemetry.

Bind bounded context at run boundaries: `run_id`, command, source path or identity, symbol, stage,
and optional trace/span identifiers. Use info for stage boundaries, debug for bounded hot-loop
detail, warning for incomplete or recoverable evidence, and error for failed operations.

Diagnostics go to stderr and the configured JSONL log directory so artifact commands can reserve
stdout for JSON. Chained exceptions retain nested traceback frames through `log_exception` or
`exc_info`; replacing an exception with `str(error)` loses evidence.

For local Copilot/Codex tracing, use [Langfuse developer tracing](observability/langfuse.md). That
deployment is opt-in and separate from application instrumentation. For generated C++ analysis, use
the [SonarQube C/C++ analysis guide](quality/sonarqube.md).

The architecture-level policy, ownership map, and evidence boundaries live in the
[crosscutting concepts](../explanation/architecture/crosscutting-concepts.md) page.
