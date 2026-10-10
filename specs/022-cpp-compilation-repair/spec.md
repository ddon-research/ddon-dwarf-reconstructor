# Feature Specification: C++ compilation repair

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../docs/reference/project-status.md).

**Feature**: `022-cpp-compilation-repair`  
**Created**: 2026-09-20  
**Status**: Retired with incomplete acceptance; implementation preserved as-is
**Input**: Review the unfinished compilation recovery, repair the existing pipeline first, and
hand evidence-backed architectural blockers to a subsequent declaration-IR feature.

This specification serves contributors repairing the current dirty implementation. It requires
the repository development environment and explicit local source/store paths for environmental
acceptance. [Measured evidence](measured-evidence.md) separates the reviewed state from future
results. Creating this package does not accept the existing implementation.

## User Scenarios & Testing

### User Story 1 - Reproduce and repair semantic defects (Priority: P1)

A maintainer can reproduce a failure against an identified producer, repair the responsible
semantic rule, and demonstrate that recovered identities and evidence survive the repair.

**Why this priority**: Compiler counts without producer identity or faithful declarations can
reward omitted types and fabricated definitions.

**Independent Test**: Run deterministic alias, scope, template, method, enum, bitfield, and
declarator fixtures, then compile their minimal generated headers.

**Acceptance Scenarios**:

1. **Given** two template arguments differing only by namespace, **when** definitions are selected,
   **then** both qualified specializations remain independently represented.
2. **Given** conflicting or cyclic aliases, **when** publication is planned, **then** a source-bound
   diagnostic identifies the conflict or cycle; no dummy aggregate replaces an alias.
3. **Given** incomplete or contradictory enum/method evidence, **when** declarations are rendered,
   **then** unsupported choices remain explicit instead of becoming guessed C++ semantics.

### User Story 2 - Publish legally ordered, complete closures (Priority: P1)

A consumer can include a generated header and obtain every declaration needed by its full
dependency closure, including nested owners, aliases, and template primaries.

**Why this priority**: A correct declaration still fails when its prerequisites are unavailable.

**Independent Test**: Generate small nested-owner and allocator fixtures; validate standalone,
aggregate, and selected reversed include orders independently of the proprietary corpus.

**Acceptance Scenarios**:

1. **Given** a pointer to `Outer::Inner`, **when** dependencies are classified, **then** the real
   definition of `Outer` exposes `Inner` before use; a fake outer shell is never emitted.
2. **Given** an alias to an incomplete class, **when** only a pointer is used, **then** the alias
   declaration and target declaration suffice without forcing target completeness.
3. **Given** a file include cycle with a legal declaration order, **when** publication is planned,
   **then** deterministic co-location preserves identity and provenance and removes that cycle.
4. **Given** an unschedulable declaration cycle, **when** publication is attempted, **then** a
   minimal reasoned cycle is reported without silently dropping or renaming declarations.

### User Story 3 - Decide acceptance or a precise handoff (Priority: P2)

A reviewer can distinguish a completed 289-root repair from partial improvement and from a
demonstrated limitation requiring Feature 023.

**Why this priority**: An evidence-based handoff permits architectural progress without lowering
the definition of successful reconstruction.

**Independent Test**: Exercise the acceptance ledger with complete, omitted, failed, timed-out,
and unavailable validation results; verify that only the complete case can close the feature.

**Acceptance Scenarios**:

1. **Given** all requested roots, **when** a candidate bundle is validated, **then** every emitted
   header and the aggregate translation unit are accounted for, with compiler/configuration IDs.
2. **Given** a residual blocker, **when** it is handed to Feature 023, **then** its DWARF provenance,
   minimal reproduction, rejected repairs, and next experiment are retained; Feature 022 stays open.

### Edge Cases

- CU/DIE offset zero; same display name in different namespaces or compilation units.
- Multiple aliases to anonymous aggregates/enums, self cycles, alias chains, and unavailable targets.
- Nested template owners, nested by-value types, default arguments, and conflicting primary signatures.
- Overloads differing only by return type or exception specification; access/virtualness conflicts.
- Unknown enum scopedness, non-fixed underlying representations, unnamed zero-width bitfields.
- Arrays of function pointers, member pointers, multidimensional arrays, static members, and references.
- Source/store mismatch, unhealthy Doris, partial lookup, stale caches, interrupted publication.
- Compiler timeouts, regex ownership misidentification, omitted roots, and legitimate output changes.

## Requirements

### Functional Requirements

- **FR-001**: Preserve the effective dirty producer, requested roots, source/store identity,
  configuration, tool versions, reports, and output hashes before comparing or changing behavior.
- **FR-002**: Preserve qualified type/template identity and CU/DIE provenance through selection,
  rendering, deduplication, and publication. Ambiguous name-only fallback MUST fail explicitly.
- **FR-003**: Resolve alias declarations, anonymous targets, missing targets, duplicates, conflicts,
  and cycles without fabricating aggregate declarations or erasing additional aliases.
- **FR-004**: Use one evidenced template-primary signature and lexical scope per family. Concrete
  observations default to explicit specializations; unsupported generic bodies MUST NOT be inferred.
- **FR-005**: Separate C++ overload identity from declaration compatibility. Preserve enum evidence,
  legal bitfields, and structured declarator precedence without silently changing semantics.
- **FR-006**: Distinguish declaration availability, alias availability, enclosing-owner visibility,
  template-primary visibility, and complete-definition requirements before choosing includes.
- **FR-007**: Schedule actual owner definitions and nested declarations legally; co-locate file
  strongly connected components only when the underlying declaration schedule is legal.
- **FR-008**: Reconcile requested/resolved/emitted/validated identities and source diagnostics in
  the publication manifest. Compiler failure, timeout, omissions, and unsupported evidence MUST
  remain distinct and MUST NOT be converted to successful validation.
- **FR-009**: Validate the complete 289-root request, every resulting header, aggregate compilation,
  relevant include orders, fresh/warm processes, context-on/off modes, and semantic evidence.
- **FR-010**: Permit a residual-blocker handoff only with a source-bound minimal reproduction,
  evidence of attempted lawful repairs, and a falsifiable next experiment. Handoff is not completion.
- **FR-011**: Preserve normal Doris-only serving, atomic publication, durable artifacts, and bounded
  source-aware caching. Recover storage only after current diagnosis warrants a targeted repair.
- **FR-012**: Pass repository correctness/quality/coverage/audit gates and the matching Feature 021
  performance contract; intentional semantic corrections require explicit evidence and comparisons.

### Key Entities

- **Evidence identity**: Source hash, CU/DIE identity, observation kind, and status.
- **Dependency requirement**: Consumer, provider, required capability, reason, and evidence.
- **Publication ledger**: Requested and emitted identities, owning paths, hashes, and diagnostics.
- **Residual blocker**: Reproducible semantic limitation with repair history and successor task.

## Success Criteria

- **SC-001**: All 289 requested roots resolve; every required declaration is emitted or diagnosed;
  accepted output has zero unexplained omissions, identity collisions, or fabricated definitions.
- **SC-002**: Every candidate header and aggregate unit pass the recorded MSVC profile with zero
  compiler errors, timeouts, and C1003 aborts. Declared compiler canaries pass their named profiles.
- **SC-003**: Equivalent fresh/warm runs produce byte-identical deterministic artifacts. Context
  modes preserve corresponding C++/assembly bytes; only documented context artifacts differ.
- **SC-004**: Evidence checks preserve names, inheritance, field offsets/sizes, and provenance;
  host syntax success never substitutes for independent PS4 layout/ABI validation.
- **SC-005**: Required repository gates pass; matching workload/profile/cache-state p50 and p95
  remain at most 110% of the corresponding accepted Feature 021 baseline.

## Assumptions and Scope

Reuse current typed references/scopes, existing graph algorithms, and the analytical store.
Full completion is contingent on the named gates; a blocked baseline yields blocked performance
acceptance. Feature 021 retains its broader parity/performance and repository review obligations.
Feature 019 owns analytical storage architecture. Feature 001 owns independent PS4 ABI evidence.
[Feature 023](../023-cpp-declaration-ir/spec.md) follows repair or a documented blocker handoff.
New generic inference, a new storage backend, LLVM IR lowering, and a wholesale rewrite are outside
this repair feature. The spec packages themselves do not authorize service or data deletion.
