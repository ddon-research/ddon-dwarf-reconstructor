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

## Header bundles

`AtomicHeaderPublisher` stages UTF-8 headers, writes a manifest containing byte counts and
SHA-256 values, backs up existing targets, and commits the bundle. Any failure rolls back the
staged publication so a previously valid result remains available.

## External-tool evidence

Tool probes and exports are bounded, source-aware, and manifest-backed. They retain authority and
provenance metadata. External evidence is additive and cannot replace deterministic DWARF facts.
