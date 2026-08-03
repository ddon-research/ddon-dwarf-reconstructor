# Implementation Plan: LadybugDB-first knowledge-graph loader

## Research synthesis

- LadybugDB documents an embedded, in-process graph database with on-disk and in-memory modes,
  columnar storage, Cypher, and serializable transactions.
- The Python client uses `Database` and `Connection` objects and is installable from PyPI through
  `uv`; the CLI is a separate standalone `lbug` executable with JSON/JSONL output modes.
- LadybugDB requires an explicit schema for the structured property-graph model. Native JSON is
  available from v0.15, which fits the heterogeneous `properties` dictionaries in the current
  bundle without flattening producer records.
- Full-text search and vector indexing are extensions with separate availability and schema
  constraints. They are optional query stages, not prerequisites for importing the canonical
  bundle.
- The official system-requirements page documents precompiled Python wheels through CPython 3.11,
  while the current local `uv` probe resolved `ladybug` 0.19.0 and imported it under CPython 3.14.6.
  This discrepancy is an acceptance gate and must be recorded as observed evidence, not assumed
  compatibility.

## Research sources

### Primary sources

- [LadybugDB installation](https://docs.ladybugdb.com/installation/)
- [LadybugDB overview](https://docs.ladybugdb.com/)
- [Python API](https://docs.ladybugdb.com/client-apis/python/)
- [CLI](https://docs.ladybugdb.com/client-apis/cli/)
- [System requirements](https://docs.ladybugdb.com/system-requirements/)
- [Differences with Neo4j](https://docs.ladybugdb.com/cypher/difference/)
- [Data types and native JSON](https://docs.ladybugdb.com/cypher/data-types/)
- [JSON extension](https://docs.ladybugdb.com/extensions/json/)
- [Graph database interoperability](https://docs.ladybugdb.com/import/graph-databases/)
- [Connections and concurrency](https://docs.ladybugdb.com/concurrency/)
- [Full-text search](https://docs.ladybugdb.com/extensions/full-text-search/)
- [Vector search](https://docs.ladybugdb.com/extensions/vector/)
- [LadybugDB source repository](https://github.com/LadybugDB/ladybug)

### Secondary context

- [The Consensus: LadybugDB, DuckDB, and PostgreSQL](https://theconsensus.dev/p/2026/05/29/ladybug-duckdb-and-postgresql.html)
  is useful for the schema-shape and analytical-workload discussion. Its performance observations
  are not project acceptance evidence.
- [Hybrid Graph RAG with LadybugDB](https://volodymyrpavlyshyn.medium.com/hybrid-graph-rag-with-ladybugdb-when-vectors-meet-graphs-aa7ddec45632)
  is useful for identifying graph, FTS, vector, and algorithm stages. Its code and benchmark
  claims are secondary and are not treated as compatibility proof.

## Design

1. Keep the existing manifest and JSONL files as the immutable source boundary.
2. Validate all declared files, checksums, schema versions, and endpoint references before a write
   transaction.
3. Project records into the explicit schema defined in
   `contracts/import-contract.md`, retaining canonical JSON properties and deterministic derived
   search fields.
4. Publish a closed database and import manifest atomically from a temporary source-bound path.
5. Expose only bounded typed query behavior through the future application adapter. Keep raw Cypher
   an infrastructure/diagnostic concern.
6. Treat FTS and vector indexes as independently probed stages with explicit availability status.
7. Add production dependencies and runtime integration only after the compatibility, fidelity,
   determinism, failure-mode, and resource gates pass.

## Implementation slices

- **Slice 1 — evidence and contract:** retain this feature record, run package/CLI probes, and
  finalize the import manifest and table schema.
- **Slice 2 — deterministic fixture:** add a small source-controlled bundle fixture and canonical
  query expectations covering producer authority, provenance, zero values, partial evidence, and
  duplicate/conflict behavior.
- **Slice 3 — loader adapter:** implement a typed infrastructure adapter that streams JSONL input,
  writes LadybugDB in bounded batches, validates endpoints, and publishes atomically.
- **Slice 4 — query and extension stages:** implement exact, typed, bounded-neighbor, and FTS
  queries; add vector only when an embedding projection is present and the extension probe passes.
- **Slice 5 — operational evidence:** validate warm reuse, locks, read-only access, failure
  recovery, cold/warm resource measurements, and explicit real-asset/performance tiers.
- **Slice 6 — synchronization:** update the current docs/spec references and mark only evidence-
  backed tasks complete.

## Validation tiers

- Focused documentation: `uv run just docs-check` and scoped stale-reference/link checks.
- Deterministic unit/integration: bundle validation, schema projection, query ordering, provenance,
  status semantics, idempotence, and atomic publication.
- Acceptance: fresh-process Python and standalone CLI probes on the supported Windows environment.
- Non-functional: cold/warm time, peak memory, database/WAL size, and bounded query latency.
- Environmental: real bundles and performance runs only with explicit local paths and retained
  manifests; they are not default correctness evidence.

## Files

- Feature record: `specs/015-ladybugdb-knowledge-graph/`.
- Research record: `specs/015-ladybugdb-knowledge-graph/research.md`.
- Import contract: `specs/015-ladybugdb-knowledge-graph/contracts/import-contract.md`.
- Synchronized source docs: `docs/reference/knowledge-graph.md`,
  `docs/how-to/export-knowledge-graph.md`, `docs/explanation/architecture/`,
  `docs/explanation/documentation-system.md`, `docs/reference/documentation-style.md`, and
  `docs/roadmap/index.md`.
- Existing feature records: `specs/012-documentation-platform/`,
  `specs/013-documentation-style-governance/`, and
  `specs/014-documentation-architecture-observability/`.
