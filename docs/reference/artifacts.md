# Durable artifact reference

Durable artifacts are keyed by source identity plus producer, schema, and configuration identity.
They are validated before reuse and published atomically.

## Source identity

`SourceIdentityCatalog` uses size, mtime, device, and inode for a relocation-stable fast key. It
retains ctime as a mutation signal. A moved catalog entry may reuse ctime evidence only when the
old path disappeared and stable object metadata matches. `verify-source` always computes a full
SHA-256 hash.

## Dump indexes

`ZstdDumpParser` streams the compressed LLVM dump instead of loading the expanded file. Its SQLite
sidecar records source identity, schema metadata, compilation-unit producer/version facts, class
definitions, and method implementations. Reuse requires matching metadata, tables, and source
identity; rebuilds publish through a temporary file and atomic replacement.

## Analytical DWARF stores

`artifacts materialize-dwarf <elf> --output-dir <external-dir>` performs the single authoritative
CU traversal and publishes a source-bound store atomically. The canonical output is a family of
typed Parquet tables: units, DIEs, attributes, references, derived indexes, sections, and raw
chunks. It retains CU/DIE offsets and order, null DIE terminators, typed raw and decoded attribute
values, parent/reference edges, unresolved targets, and a section inventory. `records.jsonl` is an
opt-in audit/interchange projection only. Large raw sections are copied in bounded chunks under
`raw_sections/`; large byte attributes use checksummed references under `raw_values/`.

`artifacts inspect-dwarf-store <manifest>` validates the manifest and source binding. Parquet is
written directly during materialization, Zstandard-compressed, and partitioned by family, source
identity, and a bounded unit-offset bucket. Complete Parquet manifests include closed-file size,
modification timestamp, SHA-256, compression,
footer, and row-group metadata. Publication also reads every closed row group so a valid footer and
hash cannot mask a corrupt compressed page. Normal readers reject missing, stale, open, or partial
stores; `inspect-dwarf-store` performs full artifact-hash and payload verification. These artifacts
must remain outside source control.

For a long diagnostic run, add `--checkpoint-every-cus 64`. The producer closes and rotates
Parquet writers at each boundary and writes an immutable file list to an in-progress
`checkpoint.json`. Inspect it explicitly with `artifacts inspect-dwarf-store <checkpoint.json>
--allow-incomplete`; normal generation and Doris loading reject incomplete snapshots.
For simple file-query timings against the same committed snapshot, use
`performance benchmark-dwarf-store <elf> --store-manifest <checkpoint.json> --allow-incomplete`.
The resulting report is partial, excludes Parquet parts created after the checkpoint, and marks
Doris as not observed.

For a bounded real-ELF parser/schema probe, use `--max-cus N`. It publishes a `partial` Parquet
manifest that may be inspected with `--allow-incomplete`, but it cannot load Doris,
serve generation or knowledge export, or establish complete-CU evidence.

`artifacts load-doris <manifest>` emits a validated native Doris load plan. Use
`--dry-run` for SQL/file evidence; execution requires a healthy local Doris Compose deployment and
the pinned Doris 4.1.3 image digests recorded by the acceptance evidence. A Docker daemon outage is
recorded as blocked evidence, not treated as a successful load. Use
`D:/doris-cli/target/release/doriscli.exe` for service-side `SHOW`, `EXPLAIN`, and profile evidence
when it is available. For Doris clarifications, also consult the checked-out 4.x documentation at
`D:\Apache-Doris-version-4.x-docs`, especially the POC, load, bucketing, schema/index, and
statistics pages. `information_schema.statistics` and `information_schema.column_statistics` are
compatibility views and remain empty; use `SHOW TABLE STATS`, `SHOW COLUMN STATS`, `SHOW ANALYZE`,
`SHOW AUTO ANALYZE`, and `__internal_schema.column_statistics` for actual statistics evidence.

## Header bundles

`AtomicHeaderPublisher` stages UTF-8 headers, writes a manifest containing byte counts and
SHA-256 values, backs up existing targets, and commits the bundle. Any failure rolls back the
staged publication so a previously valid result remains available.

## External-tool evidence

Tool probes and exports are bounded, source-aware, and manifest-backed. They retain authority and
provenance metadata. External evidence is additive and cannot replace deterministic DWARF facts.
