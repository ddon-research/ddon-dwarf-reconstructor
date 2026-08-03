# Observability knowledge base

This section records the logging, traceback, and telemetry decisions used by
the reconstructor. The runtime remains deterministic and source-provenance
first: diagnostics describe decisions and durations without becoming a second
copy of the ELF/DWARF data.

For the current architecture policy, use [crosscutting concepts](../../explanation/architecture/crosscutting-concepts.md).
For task execution, use [application logging](../../how-to/observability.md) or the
[Langfuse developer tracing how-to](../../how-to/observability/langfuse.md). The notes below retain
the design evidence and alternatives behind the runtime contract.

- [Structured logging and exception tracing](structured-logging-and-exception-tracing.md)
  - framework decision, event schema, exception policy, and OpenTelemetry seam
