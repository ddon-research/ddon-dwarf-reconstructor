# Decisions and trade-offs

## Typed, layered core

The domain stays independent of pyelftools, SQLite, zstd, Rich, structlog, and subprocesses. This
makes policy testable and lets infrastructure adapters be replaced without changing evidence
semantics. Architecture tests enforce the dependency direction.

## Persistent, source-bound analytical artifacts

Hashing and full-DIE scans are too expensive to repeat for every lookup. The identity catalog and
one-pass analytical store therefore use validated source fingerprints, typed offset records,
checksummed raw references, and atomic publication. The typed row stream is the canonical
production contract; Parquet is the durable typed output, JSONL is an opt-in audit
projection, and Doris is a measured query/load backend. The former SQLite dump index remains
available only for explicit cross-check evidence while query parity is established.

## Evidence over inference

Producer facts are never overwritten by semantic or external-tool guesses. Partial lookup is not
complete evidence. This costs some convenience but makes generated headers and graph records
auditable.

## Static docs before live embedded graph infrastructure

The current exporter already provides deterministic JSONL nodes and relationships. Zensical gives
the project a low-cost, searchable publication surface without adding LadybugDB as a runtime
dependency. A LadybugDB-first graph loader/browser is intentionally a roadmap feature until its
compatibility, schema, provenance, concurrency, and update policy are verified in `KG-001`.

## One task runner

`just` is the automation contract for root validation. The nested specification project keeps its
own `justfile` and lockfile. This avoids undocumented shell wrappers and makes local and hosted
loops comparable.
