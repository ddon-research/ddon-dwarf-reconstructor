# Components and boundaries

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../reference/project-status.md).

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

The application `SymbolExtractionService` is the symbol-generation boundary. It receives one typed
`SymbolExtractionRequest` for one or many roots, asks the hierarchy builder for one union closure
with method-signature dependencies enabled, assigns each class to a resource or `shared/` using
qualified identity and CU/DIE provenance, rewrites includes from that ownership map, and returns
one `SymbolExtractionResult`. The composition root does not loop over roots as separate generation
jobs. `SymbolPublisher` is the infrastructure boundary that infers the client-version
directory, stages the complete version tree, records the source/list/producer/configuration
identity in `symbols.manifest.json` when context generation is enabled, and atomically commits or
rolls back the publication.

There is one normal symbol path: a single root receives the same dependency closure and flat
publication rules as a multi-root request. Readable `.asm` exports are an IDA-style
semicolon-comment evidence view, while exact-byte `.s`/`.o` generation remains a separate opt-in
assembler profile. `--no-generate-context` suppresses generation manifests and reports without
changing the C++/assembly publication.

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

The local CPU/ABI integration adds a versioned `OrbisToolchainContract` at the infrastructure
boundary. SDK 12 is the promoted host-tool profile; SDK 8 is historical and explicit. The
source-bound `orbis-bin` exports, compiler `.s`/`.o` probe manifests, object `e_flags`/section/CFI/
`.sce_stack_sizes` metadata, and `llvm-mca` performance manifests are additive observations. A
`SysmoduleId` loader constant is deliberately not a `NidBinding` dynamic identity, so the Sysmodule
catalog cannot affect general NID resolution.

## Optional validation feature boundary

Strict implementation validation is an optional infrastructure feature exposed through
`infrastructure/validation`. Its CLI, option wiring, compiler-probe entry point, and conversion of
strict validation reports into artifact context enrichment are owned by that feature facade; the
facade delegates to the dedicated strict evidence adapters that remain outside the generation
path. The normal generation path depends only on the neutral `MethodContextPacket`,
`ImplementationContextEnrichment`, and `ImplementationContextEnrichmentProvider` contracts; it
does not import validation models or invoke validation policy. The publisher accepts enrichment
only through the provider seam and behaves as before when no provider is supplied.

This makes later removal a bounded change: remove the validation feature facade, its delegated
strict evidence adapters and tests, and the one validation command registration; retain generic
method context, artifact rendering, canonical Orbis evidence, and header generation. The
serialized context keys remain stable while the feature is present, so this boundary is an
ownership seam, not a wire-format migration.

## C++ reconstruction analysis boundary

The C++ reconstruction slice is an `Implemented` domain boundary. Pure control-flow policy,
instruction effects, and operand interpretation live under
`src/ddon_dwarf_reconstructor/domain/services/cpp_reconstruction/`; the published control-flow
values live under `domain/models/cpp_reconstruction/`. The services preserve bounded paths,
unsupported-instruction status, uncertainty, and diagnostic ordering. They do not parse tool
output or construct processes. CFI acquisition and external instruction parsing remain
infrastructure responsibilities in `implementation_dwarf_context.py` and the toolchain adapters.

ABI handling follows the same split. `infrastructure/implementation_abi_facts.py` acquires typed
DWARF evidence, while `domain/services/cpp_reconstruction/abi.py` classifies that evidence with
the existing pointer, aggregate, qualifier, cycle, and incomplete-reference policies. This keeps
the source-bound lookup contracts and failure statuses at the adapter boundary instead of
duplicating them in pure analysis.

Analytical method context is keyed by the compilation-unit and DIE offsets together. A
`MethodContextRequest` carries the selected implementation and declaration CU provenance, and
the Doris batch adapter uses `(unit_offset, die_offset)` for filters and hydrated maps. An
unqualified offset that is ambiguous across CUs returns unavailable evidence. The behavior is
`Verified` by the two-CU collision and candidate-provenance cases in
`tests/infrastructure/analytical/test_doris_method_context.py` and by the root architecture and
correctness gates. Following the recovery of the local Doris serving backend, method-context
queries and full-corpus batch generation execute against the active backend on canonical host port
`29030`.

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
- The implementation-validation report schema is `4.4` and records toolchain-contract identity,
  reusable external-tool observations, parsed `orbis-bin` evidence, compiler-generated assembly
  descriptors, object metadata, and typed static-equivalence dispositions. The
  implementation-discovery report remains schema `4.2`.
- `llvm-mca` is an opt-in performance-model path for marked post-compile assembly. It cannot
  promote compiler ABI, target-object parity, correctness, or semantic-equivalence status.
- Orbis disassembly parsing is implemented as pure functions; profile execution is composed through
  one executor that owns invocation, cache, timeout, and atomic retention. A shared Orbis evidence
  projection constructs empty and populated reports without changing the flattened wire format.
- Artifact I/O, content hashing, safe-relative-path checks, and atomic text publication are shared
  infrastructure contracts. The external `disassembly-regression/1` builder owns strict inventory
  and normalization, while generation and validation retain their separate evidence gates.
