# Tasks: LadybugDB-first knowledge-graph loader

## Research and compatibility gate

- [ ] T001 Record official LadybugDB capabilities, version constraints, schema differences,
  concurrency limitations, and secondary-source authority labels in `research.md`.
- [ ] T002 Probe the pinned CPython 3.14.6/Windows environment with the exact `ladybug` package
  version and record import, on-disk, JSON, FTS, and vector-extension results.
- [ ] T003 Install or locate the standalone `lbug` CLI separately, record its version, and verify
  read-only open plus deterministic JSONL output. A missing CLI remains a concrete external blocker.

## Import contract and loader

- [ ] T004 Implement manifest/checksum/schema validation before any LadybugDB write transaction.
- [ ] T005 Implement the `KnowledgeNode`, `KnowledgeEdge`, and `KnowledgeInstruction` projection
  from the contract, including stable derived IDs, native JSON properties, and `search_text`.
- [ ] T006 Implement source-bound import manifests keyed by bundle hash, schema/configuration
  identity, loader version, and Ladybug version.
- [ ] T007 Implement bounded streaming/batching, temporary staging, checkpoint/close, atomic
  publication, stale-artifact rejection, and rollback-safe failure handling.

## Query and evidence behavior

- [ ] T008 Add deterministic exact-ID, typed-filter, bounded-neighbor, and full-text query fixtures
  with explicit result status and provenance assertions.
- [ ] T009 Add an optional embedding fixture and vector-extension probe; report missing embeddings
  as `not_observed` or `unavailable` without failing the base import.
- [ ] T010 Exercise malformed input, checksum mismatch, unsupported schema, conflicting node,
  dangling endpoint, duplicate record, stale manifest, interrupted write, failed extension, and
  locked-database paths.
- [ ] T011 Verify fresh-process determinism, warm reuse, read-only multi-process behavior, and
  single-writer diagnostics without mutating the canonical source bundle.

## Resource and documentation evidence

- [ ] T012 Measure cold/warm import time, peak memory, database/WAL size, and representative query
  latency on the deterministic fixture; retain structured results outside source control.
- [ ] T013 Run explicit real-asset/performance evidence only with named local inputs and record
  cold/warm state, tool versions, configuration, and manifest identity.
- [ ] T014 Synchronize the existing specs, architecture pages, knowledge-graph reference, how-to,
  roadmap, and documentation-style wording with this feature record.
- [ ] T015 Run `uv run just docs-check`, `uv run just check`, the relevant tests, and final diff
  review. Mark the gate complete only when all required evidence is retained.
