# Decisions and trade-offs

## Typed, layered core

The domain stays independent of pyelftools, SQLite, zstd, Rich, structlog, and subprocesses. This
makes policy testable and lets infrastructure adapters be replaced without changing evidence
semantics. Architecture tests enforce the dependency direction.

## Persistent, source-bound artifacts

Hashing and full-DIE scans are too expensive to repeat for every lookup. The identity catalog and
SQLite dump index therefore use validated metadata and source fingerprints, publish atomically,
and retain warm artifacts. A forced verification path remains available when evidence must be
re-established.

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
