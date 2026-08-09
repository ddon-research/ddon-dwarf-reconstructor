# Feature 019: Analytical DWARF Store and Runtime Replacement

## Goal 1: research and design

| Field | Contract |
| --- | --- |
| Outcome | A source-backed claim ledger, tool matrix, compatibility gates, lossless record schema, and storage/runtime decision. |
| Evidence | Current implementation; DWARF specifications; pyelftools 0.33; LLVM DWARF sources and verifier output; related converters; Arrow, Parquet, and Doris documentation. |
| Constraints | Claims are labeled `confirmed`, `observed`, `supported`, `blocked`, `rejected`, or `uncertain`. File-format evidence is contextual only and is not a runtime competitor. |
| Boundary | Research does not make a database dependency or runtime integration authoritative. |
| Iteration | Research inventory -> evidence matrix -> schema -> fixture round-trip -> compatibility review. |
| Blocker | Missing executables, packages, or services are recorded and retried explicitly; no claim is inferred from an unavailable tool. |

## Goal 2: one-pass materialization and benchmark

| Field | Contract |
| --- | --- |
| Outcome | One CU traversal produces typed normalized rows directly into Parquet, retains JSONL only for fixtures and debugging, compares native Doris with the prior live lookup baseline, and replaces normal runtime lookups with the measured query backend. |
| Evidence | Deterministic fixtures, `resources/DDOORBIS.elf`, source-bound manifests, exact output hashes, LLVM verification when available, and cold/warm benchmark reports. |
| Constraints | No missing CUs, dropped attributes, name-only IDs, whole-dump loads, or silent fallback. Producer RAM is measured but is not an acceptance blocker on the 64 GB workstation; normal query/runtime memory remains bounded. |
| Boundary | The compressed-text SQLite index is cross-check evidence only during migration and is not a normal runtime dependency. |
| Iteration | Preflight -> fixture -> real subset -> full real ELF -> storage comparison -> query parity -> runtime migration -> full validation. |
| Blocker | Doris and LLVM verification remain explicit evidence tiers. A repeated environmental blocker is reported after three checks. |

## Acceptance

The canonical producer must emit every CU and every DIE, including null terminators, in stable source-offset order. It writes typed normalized rows directly to Parquet during the single traversal; JSONL is an opt-in lossless audit/interchange projection, not a prerequisite for a full-corpus run. Every attribute preserves its form, raw value, decoded value, source offset, and provenance. The normalized families include ranges, locations, line programs, macros, frames, abbreviations, and names in addition to sections, units, DIEs, attributes, references, and derived indexes. Macro sections remain explicitly represented as `raw_only` records when pyelftools has no public decoder. Unsupported values remain tagged records or bounded raw-section references.

The PyArrow 25 implementation boundary uses explicit family schemas, bounded `ParquetWriter` row
groups, capped `Table.from_pylist` inputs, and typed Dataset partitioning/filtering. A later
JSONL-to-Parquet backfill must use the same bounded sink and manifest layout/writer settings as
direct materialization, validate closed payloads, and publish atomically.

A complete manifest is source-bound and publication-bound: it records the producer, schema, and
configuration identities, CU and family counts, and the closed Parquet file descriptors including
relative path, size, modification timestamp, SHA-256, compression, footer, and row-group metadata.
The publisher validates those hashes before complete publication. Normal readers fail closed on
missing, stale, or open files; explicit inspection performs full hash verification. A manifest with
status `partial` or `in_progress` is diagnostic evidence only.

Long diagnostic runs may opt into `--checkpoint-every-cus N`. The producer closes and rotates
Parquet writers at CU boundaries, records the exact closed-file list in an `in_progress`
`checkpoint.json`, and preserves that snapshot after interruption. Checkpoints are explicitly
partial query evidence: normal store loading, Doris plans, generation, and knowledge export reject
them unless a diagnostic caller opts into incomplete loading, in which case query results carry
`partial` status. Checkpoint rotation is not part of the production benchmark until its cost and
file-count effect is measured.

`--max-cus N` is a bounded real-ELF compatibility probe. It may publish a partial Parquet store
for schema and parser validation, but it cannot load Doris, serve generation or
knowledge export, or establish CU completeness.

Known malformed-DWARF profiles are source-bound and must record independent LLVM evidence plus
guarded context bytes. A complete producer may report `dwarf_recovery.status=applied` when it
installs the replacement as an in-memory overlay, or `already_applied` when the exact replacement
contexts are already present in the source; mixed or unknown contexts fail closed. Both statuses
require zero parser diagnostics before normal runtime use.

The file-based runtime is eligible only when all critical queries and complete knowledge export match the current byte-stable output and remain within 110% of baseline p95 and 110% of baseline peak memory. Otherwise Doris is the required runtime. If neither backend satisfies the evidence gate, the replacement remains blocked.

The current-data Doris benchmark is a read-only downstream evidence route. Against an existing
complete manifest and live publication it retains a schema-`1.2` report (with the nested diagnostics
artifact retaining its own schema) outside source
control: one `EXPLAIN` and `EXPLAIN VERBOSE` per distinct exact suite SQL, and one query-ID-bound
raw/full profile for every cold and warm PyMySQL execution. CLI, PyMySQL, and FE HTTP attempts,
schema/session context, normalized plan hashes, ordered-result hashes, and explicit missing,
evicted, timeout, routing, and fallback states are part of the report. The query result may remain
observed when diagnostics are partial, but the diagnostic section and overall report remain
incomplete. The diagnostic scope is limited to the explicit bounded Doris suite; canonical
generate children are not instrumented by this route. No materialization, load, DDL, MV, schema,
or implicit cache/session tuning is authorized by this benchmark route.

The optimization evaluation is a separate opt-in route over the same complete manifest. It defines
typed `DorisServingVariant`, `DorisQueryObservation`, and `DorisOptimizationReport` contracts. The
actual generation child may enable bounded redacted query tracing; the trace records query-shape
digests, query IDs, local execute/fetch timing, rows, scan/tablet/operator/memory/spill metrics,
and profile status without parameter values. Profiles are retrieved immediately on the executing
FE, and a missing, mismatched, evicted, or timed-out profile is `partial` evidence. The route
captures all query summaries but only one representative profile per shape, slow queries over
500 ms, and a maximum of 20 profile instances. Tracing is paired with an untraced run and adds no
authority to the performance result when overhead exceeds 5%.

The default canonical model remains unchanged: source-first `DUPLICATE KEY`, bounded distribution,
one partition, V2/ZSTD, and replication one. One-factor candidates include explicit projections,
512-key set hydration, source/name lookup buckets 2/4/8, trace-gated method-target and DIE-offset
locators, index/Bloom removal, tiny-table buckets, V3/LZ4, pipeline parallelism, SQL cache, and
Stream Load workers. Candidates are auxiliary and isolated; Unique/Aggregate models, row store,
asynchronous MVs, group commit, and unrelated complex SQL are rejected or `not_applicable` for the
current workload. Promotion requires source/manifest binding, exact fourteen-family counts,
ordered-result and generated-header hashes, zero diagnostics, terminal-success statistics, healthy
tablets, and at least 10% confirmatory warm p50/p95 improvement without exceeding the existing 110%
regression bound.

Arrow Flight SQL is an opt-in transport evaluation only. The default MySQL/PyMySQL path remains
authoritative for semantic queries, DDL, and HTTP Stream Load. The optional ADBC benchmark must
prove exact parameterized parity for all critical queries and types, keep point-query and complete
contract p95 within 110% of MySQL in cold and warm connection runs, and demonstrate at least one
20% end-to-end or peak-RSS improvement on a representative Arrow-native multi-row workload. A
missing listener, incompatible parameter protocol, unreachable BE DoGet endpoint, or unmeasured
server cache/profile surface remains `blocked` or `not_observed`; it cannot trigger a default
runtime migration.
