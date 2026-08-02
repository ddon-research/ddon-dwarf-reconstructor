# Observability knowledge base

This section records the logging, traceback, and telemetry decisions used by
the reconstructor. The runtime remains deterministic and source-provenance
first: diagnostics describe decisions and durations without becoming a second
copy of the ELF/DWARF data.

- [Structured logging and exception tracing](structured-logging-and-exception-tracing.md)
  - framework decision, event schema, exception policy, and OpenTelemetry seam
