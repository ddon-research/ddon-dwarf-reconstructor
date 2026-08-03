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
| `domain/services` | DIE traversal, definition selection, type chains, locations, methods, hierarchy, rendering | launchers and concrete filesystem/process code |
| `application` | generation, export, setup orchestration, typed requests and bundles | direct adapter construction |
| `infrastructure` | `ElfDwarfSession`, source catalog, SQLite/zstd indexes, atomic publishers, Orbis/process adapters, logging setup | domain policy duplication |
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
