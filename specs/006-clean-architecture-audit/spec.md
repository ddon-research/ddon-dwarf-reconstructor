# Feature Specification: Clean Architecture Audit and Modernization

**Feature Branch**: `006-clean-architecture-audit`

**Status**: Implementation and Tier 1/2 convergence complete; Tier 3 deferred

## Goal

Leave the reconstructor with one coherent, evidence-preserving architecture.
The project may make intentional breaking changes to remove duplicate policies,
stale artifact readers, unnecessary indirection, and untyped fallback behavior. The
feature package is both the decision record and implementation record for the
focused refactor. Remaining Tier 3 work is explicitly tracked as deferred
real-asset/compiler validation rather than hidden behind alternate paths.

## Requirements

- **CA-001**: Source identity MUST prevent a same-path source replacement from
  reusing stale DIE offsets, cache records, indexes, or generated declarations.
- **CA-002**: Search and parse operations MUST represent complete, partial,
  unavailable, conflicting, and timed-out evidence explicitly. A timed-out or
  partial result MUST NOT be cached as complete, consumed as complete, or
  reported as complete.
- **CA-003**: Every external DWARF/ELF shape MUST be normalized at one adapter
  boundary. Domain services MUST consume one typed CU, DIE, attribute, and
  source-identity contract.
- **CA-004**: Each reconstruction policy MUST have one owner. The application
  path MUST not depend on inheritance layers, duplicate caches, or alternate CLI
  behavior that only exists to avoid refactoring.
- **CA-005**: Configuration MUST be typed, validated at startup, and connected
  to the behavior it controls. Unknown or unused settings MUST be removed.
- **CA-006**: Artifact readers MUST accept the current schema and source/
  producer/configuration identity. Rebuilding an older or invalid artifact MUST
  be an explicit maintenance action, not an implicit load-time transformation.
- **CA-007**: Generated output MUST publish atomically and MUST retain source,
  CU, DIE, completeness, and diagnostic provenance for every derived declaration.
- **CA-008**: Active README, architecture, generation-flow, testing, Spec Kit,
  and Python instruction documents MUST describe the canonical packaged command,
  typed boundaries, and the breaking-change policy consistently.

## Non-goals

- Reconstructing source constructs absent from DWARF evidence.
- Broad changes to generated headers without a replacement output contract and
  exact byte-level regression evidence.
- Editing generated DWARF standard documents to change terminology supplied by
  the standards themselves.
- Moving proprietary ELF files, compressed dumps, indexes, caches, logs, or
  generated headers into the repository.
- Completing explicit real-asset and compiler validation when the required local
  inputs and toolchains are not selected.

## Target architecture

The target runtime has one composition root and one typed use-case path:

```text
Typer CLI
   -> typed GenerationRequest / artifact request
   -> application use case
   -> domain policies and typed evidence results
   -> infrastructure ports for ELF, DWARF, dump, cache, filesystem, and Orbis
   -> atomic output/artifact publication
```

The ELF adapter owns resource lifetime and pyelftools normalization. Source
identity is shared by all durable products. Search returns a result object rather
than an integer that loses status. Renderers consume structured declarators and
diagnostics rather than reparsing presentation strings. The application builds
the graph through composition, not multiple inheritance.

The current implementation realizes this shape through `ElfDwarfSession`, a
typed `DwarfSessionFactory`, `DwarfRuntimeConfig`, `SearchResult`,
`GeneratorWorkflow`, and `AtomicHeaderPublisher`. Duplicate cache and utility
policies are not part of the runtime surface.

## Acceptance criteria

The implementation feature is complete only when:

1. the CA-001 through CA-008 requirements have focused tests at the named paths;
2. source replacement, malformed artifacts, timeout, partial evidence, cycles,
   invalid configuration, offset zero, and failed publication are covered;
3. the canonical command produces deterministic fresh-process and warm-cache
   output for fixture and explicit real-asset manifests;
4. `uv run just test-unit`, `uv run just check`, `uv run just test`,
   `uv run just coverage-ci`, and `uv run just audit` pass;
5. explicit real-asset and compiler tiers record input identity, producer/schema/
   configuration identity, cold/warm state, timing, and manifest hashes; and
6. active instructions and architecture/spec artifacts no longer ask developers
   to preserve removed shapes or maintain duplicate paths.

## Evidence and unresolved decisions

The confirmed defects and hypotheses are recorded in `research.md`. The task
list was ordered so source identity and evidence status were fixed before cache
deletion, composition cleanup, or renderer expansion. Root and nested quality
gates are complete; explicit real-asset/compiler validation remains deferred
because no compiler probe or selected 30+ GB acceptance run was requested.
