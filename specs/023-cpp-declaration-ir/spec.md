# Feature Specification: Incremental C++ declaration IR and compiler validation

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../docs/reference/project-status.md).

**Feature**: `023-cpp-declaration-ir`  
**Created**: 2026-09-20  
**Status**: Retired with incomplete acceptance; specified but unimplemented
**Input**: Derive an incremental declaration intermediate representation and compiler-based
validation from the repair findings, with researched adoption gates for external tooling.

This specification serves reconstruction maintainers. It describes intended behavior, not an
implemented compiler pipeline. Prerequisites are the repository environment, Feature 022's
identified producer and evidence, and explicit compiler profiles for optional validation.

## User Scenarios & Testing

### User Story 1 - Follow evidence into one declaration model (Priority: P1)

A maintainer can trace each emitted declaration from source observations through canonical
identity and a legal emission plan, without reinterpreting presentation strings.

**Why this priority**: Parallel string and structured representations currently allow divergent
scope, dependency, and declarator decisions.

**Independent Test**: Adapt deterministic DWARF fixtures into the IR and render one declaration
family; compare its semantics and unchanged bytes against the repaired producer.

**Acceptance Scenarios**:

1. **Given** equivalent observations of one declaration, **when** identity is resolved, **then**
   all contributing provenance remains and disagreements are explicit.
2. **Given** a declaration with aliases, templates, and nested owners, **when** dependencies and
   output are planned, **then** both consume the same immutable semantic model.
3. **Given** insufficient evidence, **when** lowering is attempted, **then** the result remains
   unresolved with reasons rather than synthesizing an unsupported source-language fact.

### User Story 2 - Validate semantics through compiler observations (Priority: P1)

A reviewer can check generated C++ types and declaration relationships using a pinned compiler,
and join its observations back to repository-owned declaration identities.

**Why this priority**: Compiler acceptance alone does not expose all semantic substitutions.

**Independent Test**: Validate a small emitted bundle and normalize compiler syntax/AST results;
exercise compiler absence, timeout, unsupported schema, and conflicting observations.

**Acceptance Scenarios**:

1. **Given** a named toolchain profile, **when** validation runs, **then** executable identity,
   arguments, target, include environment, input hashes, and bounded diagnostics are retained.
2. **Given** an AST observation, **when** it is normalized, **then** implementation-specific node
   addresses and unstable fields never become durable declaration identities.
3. **Given** no compiler installation, **when** normal generation runs, **then** generation remains
   usable and optional validation is explicitly unavailable; compiler acceptance stays open.

### User Story 3 - Migrate with evidence and bounded cost (Priority: P2)

A maintainer can replace one legacy policy at a time and decide whether compiler tooling or a
native library adds enough value to justify its cost.

**Why this priority**: A new IR must remove semantic duplication without creating a second permanent
generator or imposing compiler startup and AST loading on ordinary requests.

**Independent Test**: Run a synthetic C++ to DWARF to reconstructed C++ differential fixture,
measure it, and compare a migrated declaration family against Feature 022's identified baseline.

**Acceptance Scenarios**:

1. **Given** a migrated family, **when** parity and semantic checks pass, **then** its superseded
   string policy is removed together with obsolete callers and tests.
2. **Given** a proposed native dependency, **when** it is evaluated, **then** adoption requires a
   demonstrated capability gap, reproducible Windows results, and maintenance/license/cost evidence.

### Edge Cases

- Partial/conflicting DWARF, source/CU collisions, offset zero, unknown Sony forms.
- Anonymous declarations with multiple aliases; nested templates and non-type arguments.
- Compiler-synthesized declarations mistaken for recovered evidence; implicit methods and defaults.
- AST schema drift, diagnostic truncation, target mismatch, timeout, process failure, and missing SDK.
- AST dumps larger than memory budgets; nondeterministic node IDs and filesystem paths.
- Legal source patterns that cannot be reconstructed as explicit specializations with available evidence.

## Requirements

### Functional Requirements

- **FR-001**: Separate source observations, resolved declaration identity, and emission decisions;
  preserve all provenance and distinguish observed, derived, unresolved, and conflicting information.
- **FR-002**: Extend the existing structured type/scope contracts into an immutable declaration IR
  covering aggregates, aliases, enums, template signatures/arguments, members, methods, and declarators.
- **FR-003**: Derive dependency requirements, lexical ownership, and deterministic schedules from
  the IR, with reasoned unschedulable cycles and an emission ledger linking IDs to output locations.
- **FR-004**: Isolate compiler execution behind a typed port and infrastructure adapter. Normal
  generation MUST NOT require a compiler or depend on its private AST representation.
- **FR-005**: Normalize compiler syntax/AST observations into versioned project-owned records with
  source joins, bounded output, timeout handling, and explicit unsupported/unavailable statuses.
- **FR-006**: Compare canonical types and declaration relationships using synthetic differential
  fixtures, property tests, compiler canaries, and selected include permutations.
- **FR-007**: Migrate by declaration family, preserving accepted behavior and accounting for every
  intentional correction; remove superseded semantic string policies after each proven migration.
- **FR-008**: Research compiler integrations on common fixtures before dependency promotion; record
  API stability, Windows packaging, licensing, omissions, inferred facts, CPU/RSS, and alternatives.
- **FR-009**: Keep host language acceptance separate from target ABI/layout evidence. Pin actual
  tool versions, flags, target/data model, and environment; a target triple alone is insufficient.
- **FR-010**: Preserve bounded normal runtime, atomic/source-bound artifacts, all Feature 022
  acceptance dimensions, and Feature 021's per-workload/cache-state 110% p50/p95 performance limit.

### Key Entities

- **Observation**: Immutable recovered fact and evidence locator.
- **Declaration**: Stable semantic identity and typed body, with observation references.
- **Emission plan**: Legal ordered declarations, ownership, dependency reasons, and output ledger.
- **Compiler profile/result**: Toolchain identity and normalized additive observations.
- **Migration record**: Replaced policy, parity evidence, semantic changes, and cost measurements.

## Success Criteria

- **SC-001**: All migrated families use a single semantic model for rendering and dependency
  planning; zero unexplained identity/provenance loss or surviving duplicate policy implementations.
- **SC-002**: Deterministic fixtures preserve representable canonical types, ownership, aliases,
  and template relationships through the differential loop; unsupported constructs are explicit.
- **SC-003**: Compiler absence/failure/schema drift produces truthful results; normal generation
  remains compiler-independent and repeated normalized results are stable.
- **SC-004**: Full 289-root acceptance and repository gates pass for the final migrated producer,
  with separate recorded host, semantic, target-layout, determinism, and performance outcomes.
- **SC-005**: Every promoted external dependency has a reproduced decision record; no speculative
  library addition or LLVM lowering is needed to declare the initial migration successful.

## Assumptions and Scope

The initial adapter uses a pinned Clang subprocess and normalized observations. LibTooling is a
conditional later choice if that approach cannot satisfy a demonstrated requirement. LLDB's
DWARF-to-Clang design is a research reference, not an assumed embeddable exporter. No dependency
is promoted by this specification. Raw LLVM IR is outside the declaration problem's scope.
Feature 022 may hand over a proven blocker without being marked complete. That exception allows
research and targeted experiments, not acceptance of incomplete output or guessed template bodies.
