# Feature Specification: C++ reconstruction architecture

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../docs/reference/project-status.md).

**Feature Branch**: `codex/021-cpp-reconstruction-architecture`

**Created**: 2026-09-06

**Status**: Retired with incomplete acceptance; full-corpus parity and performance remain open

This feature serves maintainers and implementing agents reviewing the entire reconstructor.
Its outcome is a source-backed architectural refactoring with preserved header evidence,
explicit performance acceptance, and resumable implementation records. The accepted v6
[plan](plan.md) defines the scope. No new pseudocode-generation capability is promised.

## User Scenarios & Testing

### User Story 1 - Preserve reconstruction evidence (Priority: P1)

As a maintainer, I can compare new output with fresh output from the exact initial working
state, including all 289 roots and the MtObject/rLayout controls.

**Independent test**: new destinations, validated artifact inventories, repeated unchanged
producer runs, exact header bytes, and separately retained compiler results.

1. Given an existing dirty checkout, snapshotting preserves both index and effective files.
2. Given equivalent source/configuration, a missing file or changed header fails comparison.
3. Given unavailable method/tool evidence, the result retains that limitation explicitly.

### User Story 2 - Review and refactor every subsystem (Priority: P1)

As a maintainer, I can see which modules were inspected, why each change is justified, and
how it preserves dependency direction, state ownership, evidence fidelity, and performance.

**Independent test**: every inventory entry has a source-inspected disposition and each
accepted finding has implementation/test evidence or an explicit external blocker.

1. Pure reconstruction policies can run against typed inputs without external tools.
2. Tool adapters preserve bounded execution and provenance through narrow contracts.
3. Internal module moves update callers and coverage groups without forwarding shims.

### User Story 3 - Resume and enforce the workflow (Priority: P2)

As an implementing agent, I can resume from exact tasks and evidence without guessing what
ran, weakening acceptance, or treating historical results as current.

**Independent test**: required root/nested gates, source-derived API validation, specification
convergence, and an accurate handoff with executable next actions.

## Requirements

- **FR-001**: Preserve the initial working state and durable source-bound artifacts.
- **FR-002**: Inventory and inspect every subsystem, including nested and supporting tools.
- **FR-003**: Capture fresh full-output baselines before production refactoring.
- **FR-004**: Validate artifact integrity independently of output equivalence; headers remain exact.
- **FR-005**: Separate pure C++ reconstruction policies, application coordination, and adapters.
- **FR-006**: Consolidate justified duplication and retain bounded, source-bound state lifetimes.
- **FR-007**: Enforce demonstrated architecture and coverage rules using existing tooling first.
- **FR-008**: Compare each workload/cache-state median and sampled p95 against a 110% bound.
- **FR-009**: Synchronize Spec Kit, Diataxis/arc42 documentation, and contributor instructions.
- **FR-010**: Derive lessons from completed evidence and maintain an exact resumable handoff.

## Success Criteria

- **SC-001**: No unexplained header, ownership, provenance, diagnostic, or file-inventory drift.
- **SC-002**: Every reviewed module and accepted finding has a documented disposition.
- **SC-003**: Candidate p50 and sampled p95 are each at most 110% for every matched pair.
- **SC-004**: Required correctness, coverage, quality, audit, documentation, and applicable
  packaging/nested checks pass; unavailable real evidence is separately blocked.

## Edge cases and evidence boundaries

Preserve offset zero, CU-relative references, conflicting candidates, cycles, unknown
instructions, partial searches, timeouts, unavailable SDKs, interrupted publication, stale
stores, corrupt manifests, lock failures, and source-identity/cache isolation. Static parity,
assembler acceptance, host compilation, Sony ABI acceptance, and live behavior are distinct.

## Clarifications: 2026-09-06

- The user selected repository-wide audit and justified refactoring, including analytical and
  nested tooling; this is not limited to assembly/toolchain packages.
- The user selected 10% allowable median and tail runtime regression per workload/state.
- Header-output changes require a separate behavioral specification and explicit acceptance.
- Existing approved constraints settle the scope; no further product clarification is pending.

## Related authority

Features [001](../001-header-foundation/spec.md), [006](../006-clean-architecture-audit/plan.md),
[010](../010-toolchain-evidence/spec.md), [016](../016-performance-profiling/plan.md),
[018](../018-performance-algorithm-audit/plan.md), [019](../019-analytical-dwarf-store/spec.md),
and [020](../020-documentation-api-reference/plan.md) remain authoritative for their contracts.
