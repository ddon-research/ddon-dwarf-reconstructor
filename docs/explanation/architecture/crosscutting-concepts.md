# Crosscutting concepts

This page is the repository's arc42 section-8 home. It documents the few policies that recur
across multiple building blocks: observability, durable evidence, authority and provenance,
validation, and documentation publication. It explains how those policies work, links them to
source and tests, and routes task-oriented readers to the relevant how-to pages.

arc42 section 8 is intentionally selective: it is a central specification of important recurring
approaches, not a catalogue of every helper or framework option. The [application logging
how-to](../../how-to/observability.md), [Langfuse how-to](../../how-to/observability/langfuse.md),
and [SonarQube how-to](../../how-to/quality/sonarqube.md) contain the operational procedures.

## Concept map

The C4 component view identifies the implementation surfaces that carry these policies. It keeps
runtime logging, optional external telemetry, and local quality analysis distinct: only the first
two logging components are in the runtime application path, while Langfuse and SonarQube are
developer tooling adapters.

```mermaid
C4Component
title "Crosscutting concepts — observability and quality components"
Container_Boundary(runtime, "Runtime composition") {
    Component(coreObservability, "core.observability", "Python standard logging facade", "Binds context and emits structured events without importing infrastructure libraries.")
    Component(loggerSetup, "LoggerSetup", "structlog + Rich adapters", "Adds JSONL file and human-readable stderr handlers while preserving foreign handlers.")
    Component(performanceRunner, "PerformanceRunner", "opt-in infrastructure adapter", "Samples isolated process trees and publishes bounded CPU, RAM, I/O, and manifest evidence.")
    Component(historyStore, "HistoryStore", "SQLite infrastructure adapter", "Stores source-bound summaries and method aggregates for like-for-like comparison.")
}
Component_Ext(jsonl, "JSONL diagnostic log", "Process-local file", "Retains structured fields, callsite data, and chained traceback frames.")
Component_Ext(stderr, "Diagnostic stderr", "Human-readable stream", "Shows bounded operational messages; stdout remains available for JSON artifacts.")
Component_Ext(langfuse, "Langfuse developer tracing", "Optional loopback Docker stack", "Receives Copilot/Codex telemetry; the Python application is not instrumented.")
Component_Ext(sonar, "SonarQube adapter", "tools/sonar Python CLI", "Creates and validates a local MSVC compilation database for generated headers.")
Component_Ext(qualityTests, "Focused quality tests", "pytest", "Verify logging fields, chained errors, tool arguments, and compilation-database contracts.")
Component_Ext(performanceArtifacts, "OS-local performance artifacts", "external files", "Retains raw profiles, sample streams, and bounded child output outside Git.")
Rel(coreObservability, loggerSetup, "uses standard LogRecord boundary")
Rel(performanceRunner, coreObservability, "emits bounded stage events")
Rel(performanceRunner, historyStore, "records summaries")
Rel(historyStore, performanceArtifacts, "references checksummed paths")
Rel(loggerSetup, jsonl, "renders structured records")
Rel(loggerSetup, stderr, "renders diagnostics")
Rel(langfuse, qualityTests, "is validated as an external developer workflow")
Rel(sonar, qualityTests, "is covered by focused adapter tests")
```

Mermaid's C4 syntax is experimental and its layout is order-sensitive. The diagram is therefore a
semantic map, not a build-time contract. The native UML and sequence diagrams below are the stable
code-oriented views for the logging boundary.

## Observability boundary

### Policy

Core and application code use the standard-library logging facade from
[`core.observability`](../../../src/ddon_dwarf_reconstructor/core/observability.py). They must not
import `structlog`, Rich, OpenTelemetry, or a concrete telemetry vendor. The infrastructure
composition root installs [`LoggerSetup`](../../../src/ddon_dwarf_reconstructor/infrastructure/logging/logger_setup.py),
which owns rendering and handlers.

Every run should bind bounded context at a useful boundary: `run_id`, command, source path or
identity, symbol, stage, and optional trace/span identifiers. Event names are stable snake_case
values. Use debug for bounded hot-loop detail, info for stage boundaries, warning for incomplete or
recoverable evidence, and error for failed operations. Never log ELF/DWARF bytes, complete
generated headers, credentials, every DIE, or unbounded subprocess output.

### Contract view

This UML view distinguishes the technology-neutral facade from the infrastructure adapter:

```mermaid
classDiagram
direction LR
class CoreObservabilityModule {
    <<module>>
    +get_logger(name) Logger
    +current_context() Mapping
    +bind_context(fields)
    +log_event(logger, level, event, fields)
    +log_exception(logger, event, error, fields)
    +log_timing(callable)
}
class LoggerSetup {
    <<infrastructure adapter>>
    +initialize(log_dir, verbose)
    +shutdown()
    +get_log_file_path() Path
    +is_initialized() bool
}
class PerformanceRunner {
    +run(workload) RunSummary
    +publish(summary)
}
class HistoryStore {
    +record(summary)
    +compare(workload, run_id) Mapping
    +export_payload(workload) Mapping
}
class StructuredLogRecord {
    +event: str
    +ddon_fields: Mapping
    +callsite: Mapping
    +exception: list
}
CoreObservabilityModule ..> StructuredLogRecord : adds fields through LogRecord
LoggerSetup ..> StructuredLogRecord : renders JSONL and stderr
PerformanceRunner --> CoreObservabilityModule : emits bounded events
PerformanceRunner --> HistoryStore : records summaries
```

The boundary is exercised by
[`tests/infrastructure/test_logging.py`](../../../tests/infrastructure/test_logging.py). Those
tests verify scoped context, structured fields, callsite data, complete chained exceptions, and
preservation of handlers owned by callers. `LoggerSetup` writes one JSONL file per process under
the configured log directory and keeps diagnostics on stderr so artifact commands can reserve
stdout for JSON.

### Runtime sequence

```mermaid
sequenceDiagram
    participant UseCase as Application use case
    participant Core as core.observability
    participant Root as LoggerSetup
    participant File as JSONL file
    participant Console as stderr
    UseCase->>Core: bind_context(run_id, command, source_identity)
    UseCase->>Core: log_event(level, event, fields)
    Core->>Root: standard LogRecord + ddon_fields
    Root->>File: structured JSON with callsite and traceback
    Root->>Console: human-readable bounded diagnostic
    Core-->>UseCase: context reset at scope exit
```

Langfuse is intentionally outside this runtime sequence. The [Langfuse how-to](../../how-to/observability/langfuse.md)
configures Copilot and Codex directly; it does not add a vendor SDK to the reconstructor.

## Durable artifacts and identity

Source-bound state is a crosscutting correctness rule. [`SourceIdentityCatalog`](../../../src/ddon_dwarf_reconstructor/infrastructure/artifacts.py)
binds reusable indexes and caches to size, mtime, device, inode, the retained ctime mutation
signal, and a full SHA-256 when explicit verification is requested. A warm identity may be reused
only when metadata proves the same filesystem object; path-only or boundary-sampling identity is
not a valid shortcut.

Durable output is validated before reuse and published atomically by
[`AtomicHeaderPublisher`](../../../src/ddon_dwarf_reconstructor/infrastructure/header_output.py).
Generated headers, manifests, JSONL bundles, SQLite indexes, and external-tool exports are keyed by
source plus producer, schema, and configuration identity. Interrupted writes must leave the previous
valid bundle available.
The [durable artifacts reference](../../reference/artifacts.md) and
[artifact inspection how-to](../../how-to/inspect-artifacts.md) describe the operational contract.

## Evidence authority and provenance

Producer facts and derived observations have different authority:

| Evidence | Authority | Crosscutting rule |
| --- | --- | --- |
| Owning DWARF DIE | Producer fact | Preserve qualified names, inheritance, offsets, sizes, source locations, DIE/CU provenance, and deterministic order. |
| `DefinitionCandidate` selection | Reconstructor policy | Prefer complete definitions without silently converting declarations into behavior. |
| `SearchResult` | Bounded lookup contract | Preserve `complete`, `partial`, `not_found`, and `unavailable`; partial evidence is never complete evidence. |
| Orbis/LLVM/GNU/other tool export | Additive observation | Keep tool identity, command, version, manifest, and uncertainty; never overwrite producer facts. |
| SonarQube diagnostics | Local quality observation | Report compiler and database evidence separately from generated-header correctness. |
| JSONL knowledge bundle | Current projection | It is a deterministic export contract, not proof that a live LadybugDB loader exists. |

The [knowledge graph reference](../../reference/knowledge-graph.md),
[external-tool evidence record](../../knowledge-base/tools/external-tool-evidence.md), and
[LadybugDB import contract](https://github.com/ddon-research/ddon-dwarf-reconstructor/blob/main/specs/015-ladybugdb-knowledge-graph/contracts/import-contract.md)
are the details. Live graph ingestion remains a separately tracked task; this documentation slice
does not introduce a graph integration.

## Validation and quality analysis

The normal loop includes deterministic integration coverage. Environmental real-asset, performance,
packaging, compiler, and Sonar evidence are explicit tiers. The [testing reference](../../reference/testing.md)
and [testing knowledge base](../../knowledge-base/testing/testing-pyramid-and-validation-loop.md)
define marker and command policy.

## Boundary and completeness semantics

`GenerationFacade` and `GenerationRuntime` form the application boundary. The runtime receives
ready, typed collaborators from the composition root and owns one explicit resource scope. Domain
rendering depends on the immutable `HeaderRenderContext`; it does not construct a filesystem,
Doris, or compiler adapter.

The canonical analytical serving path is Doris. JSONL and Parquet are composed validation adapters
behind `MaterializedStorePort`; they are not substitutable storage subclasses. Definition
construction and ordering use the domain `DefinitionCandidate` policy in every adapter. Query
results retain provenance, truncation, diagnostics, and one of `complete`, `partial`, `not_found`,
or `unavailable`. A partial or unavailable result cannot be converted to a successful placeholder
header. A full-hierarchy request backed by a source-bound manifest rejects an unresolved
`UncategorizedDefinitions.h` bundle before atomic publication.

Doris publication is staged and verified by source-bound family counts. Stream Load distinguishes
`loaded`, `publish_pending`, and `failed`; a publish timeout remains incomplete until bounded
verification proves row-count parity. Request-scoped hydration caches are cleared at each root and
emit bounded size/hit/miss lifecycle events. Registry schema mismatches fail closed rather than
falling back to an unversioned compatibility shape.

Performance is a separate infrastructure boundary. `PerformanceRunner` samples only an explicit
child process, while `HistoryStore` writes the v1 ledger at `resources/performance/` and static
exports under the knowledge base. The normal generation path has no profiler hooks. See [Profile
the application](../../how-to/profile-performance.md) and the [performance reference](../../reference/performance.md).

SonarQube follows the same boundary. `tools.sonar.prepare_msvc_analysis` creates one standalone
translation unit per generated header, runs the required MSVC flags through the Build Wrapper, and
validates the resulting compilation database. The default strict exit code is acceptance evidence;
`--allow-validation-failure` is a deliberately weaker analysis-only mode. See
[Prepare local SonarQube C/C++ analysis](../../how-to/quality/sonarqube.md).

## Documentation as a crosscutting control

Documentation is maintained as a static, source-backed product:

- Tutorials teach one successful first experience.
- How-to guides solve one concrete developer problem and include prerequisites, commands, and
  verification.
- Reference pages state exact contracts and stable options.
- Explanation pages record arc42 architecture, reasons, trade-offs, and crosscutting concepts.
- Knowledge-base pages preserve research provenance and uncertainty.
- Specs are the roadmap and acceptance surface; they are not copied into prose as a second source
  of truth.

Architecture diagrams use C4 context/container/component/code levels only when each level adds
information. UML class diagrams show code contracts, sequence diagrams show a scenario, and
flowcharts show a pipeline or boundary. Every diagram is Mermaid source, has one stated question,
labels every important relationship, and is validated by `uv run just docs-check`.

## Concept-to-source matrix

| Concept | Primary implementation | Focused evidence | Task-oriented entry point |
| --- | --- | --- | --- |
| Logging boundary | `core/observability.py`, `infrastructure/logging/logger_setup.py` | `tests/infrastructure/test_logging.py` | [Application logging](../../how-to/observability.md) |
| Opt-in performance evidence | `infrastructure/performance/runner.py`, `infrastructure/performance/history.py` | performance runner/history tests and explicit fixture tier | [Profile the application](../../how-to/profile-performance.md) |
| Local developer tracing | `ops/langfuse/compose.yaml`, `justfile` | compose config and manual trace verification | [Langfuse](../../how-to/observability/langfuse.md) |
| MSVC/Sonar evidence | `tools/sonar/prepare_msvc_analysis.py` | `tests/tools/sonar/test_prepare_msvc_analysis.py` | [SonarQube](../../how-to/quality/sonarqube.md) |
| Source-bound publication | [`SourceIdentityCatalog`](../../../src/ddon_dwarf_reconstructor/infrastructure/artifacts.py), [`AtomicHeaderPublisher`](../../../src/ddon_dwarf_reconstructor/infrastructure/header_output.py) | artifact and determinism tests | [Durable artifacts](../../how-to/inspect-artifacts.md) |
| Documentation publication | `zensical.toml`, `.github/workflows/docs.yml`, `justfile` | strict site build and Pages deployment | [Write documentation](../../how-to/write-documentation.md) |

## Scan result and deliberate boundaries

The incremental source scan covered the CLI/application/domain/infrastructure paths, observability
modules and tests, Sonar adapter and tests, Langfuse compose and recipes, documentation navigation,
README/instruction adapters, active specs, and the Pages workflow. The formerly separate Langfuse
and SonarQube pages are now task-oriented entries, and the architecture policy has one section-8
home. No stale navigation or active-document links to the retired flat pages should remain.

The following are intentional boundaries rather than undocumented gaps:

- The Python application has no Langfuse SDK instrumentation; only Copilot and Codex developer
  clients export traces.
- SonarQube is local, optional, and additive; it is not a CI correctness gate.
- The LadybugDB-first knowledge graph loader remains deferred to `KG-001`; current exports are
  JSONL plus manifest.
- The C4 views stop at context, container, and component levels because finer diagrams would repeat
  the package inventory without adding a reader decision; native UML/sequence views cover the code
  and runtime questions.

If any of these boundaries change, update this page, the affected how-to, the active feature spec,
and the relevant source-linked tests in the same change.
