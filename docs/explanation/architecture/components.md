# Components and boundaries

The recurring policies that cross these boundaries are centralized in
[crosscutting concepts](crosscutting-concepts.md). This page stays focused on ownership and
dependency direction; the section-8 page explains how logging, evidence, validation, and
documentation rules apply across the layers below.

| Layer | Owns | Must not know about |
| --- | --- | --- |
| `core` | `DwarfInfo`, CU/DIE wrappers, platform values, logging/path contracts | outer infrastructure implementations |
| `domain/models` | class, member, method, type/declarator, evidence models | pyelftools, SQLite, CLI |
| `domain/ports` | cache, lookup, source identity, type resolution, external-tool contracts | adapter details |
| `domain/services` | DIE traversal, definition selection, type chains, locations, methods, hierarchy, and composed header rendering | launchers and concrete filesystem/process code |
| `application` | `GenerationFacade`, `GenerationRuntime`, knowledge export, typed requests, bundles, and resource ownership | direct adapter construction |
| `infrastructure` | `ElfDwarfSession`, source catalog, Doris serving adapters, composed JSONL/Parquet validation views, SQLite/zstd indexes, atomic publishers, Orbis/process adapters, logging setup | domain policy duplication |
| composition roots | construction of concrete adapters and CLI wiring | — |

## Evidence authority

The owning DWARF DIE is authoritative for producer facts. `DefinitionCandidate` selection resolves
declarations versus complete definitions; `SearchResult` preserves `complete`, `partial`,
`not_found`, and `unavailable` states. External-tool exports can add provenance but cannot overwrite
producer facts.

## Cross-cutting invariants

- Offset `0` is valid and is checked with `is not None`.
- Source identity binds caches to size, mtime, device, inode, retained ctime signal, and full
  SHA-256 when verification is explicitly requested.
- Durable outputs are fingerprinted, validated, and atomically published.
- Stable ordering, qualified names, inheritance, layouts, source locations, DIE offsets, and
  generated-header bytes are preserved across warm and fresh runs.
- Missing or conflicting evidence remains explicit rather than being silently repaired.
- `GenerationFacade` is the only application entry point for generation; the composition root owns
  concrete Doris, materialized-view, source, and publication adapters.
- Canonical Doris serving is distinct from JSONL/Parquet validation projections. Both use the same
  typed definition-selection policy, but neither projection subclasses the other.
- A bounded, truncated, unavailable, or publish-pending query is not complete evidence. A
  source-bound full-hierarchy run cannot publish an unresolved placeholder bundle.
