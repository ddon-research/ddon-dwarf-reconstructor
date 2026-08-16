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
| `application` | `GenerationFacade`, `GenerationRuntime`, knowledge export, typed requests, bundles, post-header implementation discovery, canonical definition-signature rendering, and resource ownership | direct adapter construction |
| `infrastructure` | `ElfDwarfSession`, source catalog, Doris serving adapters, composed JSONL/Parquet validation views, SQLite/zstd indexes, atomic header and implementation publishers, Orbis/process adapters, logging setup | domain policy duplication |
| composition roots | construction of concrete adapters and CLI wiring | — |

## Evidence authority

The owning DWARF DIE is authoritative for producer facts. `DefinitionCandidate` selection resolves
declarations versus complete definitions; `SearchResult` preserves `complete`, `partial`,
`not_found`, and `unavailable` states. External-tool exports can add provenance but cannot overwrite
producer facts.

For PS4 implementation evidence, authority is intentionally split. Orbis binutils owns instruction
decoding, PS4 demangling, and textual disassembly. LLVM `llvm-readobj` is an opt-in generic ELF/DWARF
structural cross-check and preserves unknown numeric SCE tags without replacing Orbis facts. The
in-repository `OrbisSceMetadataReader` owns structured interpretation of SCE dynamic tags,
`PT_SCE_DYNLIBDATA`, and 24-byte RELA records because those tables are not exposed as conventional
generic relocation sections. The SCE reader preserves raw records and names where resolvable but
never applies relocations or synthesizes external declarations.

LLVM `llvm-objdump` is a separate opt-in structural cross-check. It receives the explicit
`x86_64-scei-ps4` triple by default and is sliced per method range; its complete output is cached,
while the canonical report stores only comparison summaries. `llvm-readobj` remains generic because
it has no triple option, and `llvm-tli-checker` is outside ELF extraction. SDK-derived definitions
are typed and source-hash-bound; the official SDK source contains `PT_GNU_RELRO`, not
`PT_SCE_RELRO`.

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
- Header generation is the canonical first chain. Optional implementation discovery runs only
  after a completed header request and publishes a separate report; it cannot mutate header
  bytes or make assembly-tool availability a header-generation prerequisite.
- Implementation artifact emission is a stricter opt-in extension of the report chain. The
  `AtomicImplementationReportPublisher` stages the schema-4.2 report, a schema-3.1 publication
  envelope, bounded per-method `.raw.asm` evidence, exact-byte `.s` compiler input, accepted
  `.o` objects, and `.context.json` transformation packets as one source bundle. It emits
  artifacts only when DWARF and Orbis association are unique; C++ translation is a later agentic
  workflow.
- Orbis command output is additive evidence. `OrbisReference` and `OrbisToolInvocation` preserve
  unresolved operands, consumed profile failures, raw stdout/stderr, and source/file offsets.
  Known-invalid SDK profiles are capability-filtered and documented rather than retained as
  repeated runtime diagnostics.
