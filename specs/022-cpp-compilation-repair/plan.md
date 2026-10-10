# Implementation Plan: C++ compilation repair

**Feature**: `022-cpp-compilation-repair` | **Date**: 2026-09-20 | [Specification](spec.md)

This plan is for implementers of the reviewed dirty producer. It defines future work; reviewed
results and their limits live in [measured evidence](measured-evidence.md). No Git branch switch
or service repair is required to create these planning artifacts.

## Summary and Solution Strategy

Keep the structured type/scope parser and explicit-specialization direction. Repair identity,
evidence fidelity, declaration requirements, and scheduling before changing architecture. Build
small compiler reproductions before full-root generation. Transfer only demonstrated residual
limitations to [Feature 023](../023-cpp-declaration-ir/plan.md).

## Technical Context

| Item | Decision |
| --- | --- |
| Runtime | Regular CPython 3.14.7, uv 0.12.3, locked existing dependencies |
| Product | Python CLI and deterministic DWARF-to-C++ reconstruction pipeline |
| Storage | Existing source-bound Parquet producer and Doris serving; no new fallback |
| Tests | pytest, Hypothesis, exact bytes/manifests, MSVC bundle validator, small Clang canaries |
| Platform | Windows development; MSVC host syntax and optional Clang observations; PS4 authority separate |
| Scale | 289 roots; 753 headers in retained full reports, not a fixed future header-count requirement |
| Performance | Matching Feature 021 workload/profile/cache-state p50 and p95 <=110% baseline |
| Limits | Bounded targeted lookup; no repeated whole-source scans, destructive cache cleanup, or guessed declarations |

## Constitution Check

Pre-design and post-design review: the plan preserves evidence fidelity, durable source-bound
artifacts, determinism/performance, layered design, and validation before expansion. No exception
is requested. Current implementation gate failures are recorded, not treated as design waivers.
Modules/functions/complexity remain subject to AGENTS.md limits. Any unavailable target compiler
leaves target acceptance open; it does not prevent deterministic fixture work.

## Building Blocks and Project Structure

- `domain/models/dwarf/`: existing type references/scopes and additive enum/identity evidence.
- `domain/services/parsing/`: source-bound type, anonymous aggregate, and alias observations.
- `domain/services/generation/`: one family authority, dependency requirements, legal ordering,
  and deterministic rendering; reuse `header_cycles.py` for SCCs.
- `application/generators/`: closure, publication ownership, layout, and validation reconciliation.
- `infrastructure/symbol_output.py`: atomic publication and source-bound validation records.
- `tools/sonar/validate_header_bundle.py`: existing external compiler boundary.
- Mirrored `tests/` paths are enumerated in [tasks](tasks.md).

Feature artifacts comprise `spec.md`, this plan, `research.md`, `data-model.md`, `contracts/`,
`tasks.md`, `quickstart.md`, `measured-evidence.md`, and `checklists/requirements.md`.

## Runtime and Implementation Sequence

1. **Freeze and reconcile** the effective working state, retained reports, root list, manifest
   hashes, and toolchain profiles. Doris preflight is read-only. Live healthy queries remove the
   need for a recovery action; outage diagnosis remains a separate conditional operation.
2. **Stabilize regressions**: reproduce alias self-cycle failure and formatting debt; preserve
   anonymous aliases, exact specialization identity, method compatibility, enum/bitfield facts,
   array order, and request-owned cache correctness. Test intended semantics, not current mistakes.
3. **Close declaration requirements** using typed evidence. A pointer can avoid target completeness
   while still requiring an alias or enclosing owner. Distinguish primary visibility from a
   complete specialization. Record why each dependency exists.
4. **Schedule publication**: define each real owner once, declare nested members inside it, and
   define nested types later only where legal. Normalize include edges after declaration choices;
   merge file SCCs only if the declaration graph admits a legal schedule. Record component sizes
   and fan-out; a size limit must diagnose failure, never silently cut required edges.
5. **Reconcile diagnostics** against emitted identity/ownership records. Repair scope parsing and
   origin matching; a regex's simple-name match cannot prove a qualified declaration exists.
6. **Accept or hand off**: run minimal fixtures, focused real roots, and finally all 289 roots in
   fresh directories. Record all acceptance dimensions. An irreducible residual case requires the
   blocker contract; it does not earn a checked acceptance task.

## Crosscutting Decisions

Alias availability and target completeness are different obligations. Enum opaque declarations
require compatible evidenced semantics; an observed DWARF underlying type alone does not prove
the original source used a fixed enum base. Unknown scopedness is not `enum class`.

The renderer consumes structured references. Where transitional strings remain, update them from
the canonical reference rather than independently rewriting both. Cache keys bind source, CU/DIE,
and output-affecting configuration; Python object identity and mapping length are insufficient.

Explicit specializations remain the default. A lawful source using a generic template and a
nested argument can defeat an explicit-only schedule. First prove this is a real source-bound
case; report a limitation instead of inventing a generic body, new type name, or outer definition.

## Quality and Acceptance

Follow [quickstart](quickstart.md) and the [acceptance contract](contracts/acceptance.md). Each
coherent code slice runs focused tests plus `test-unit`, `check`, and `test`; final implementation
also runs `coverage-ci` and blocking `audit`. Performance is measured after semantic parity,
without profiler overhead in acceptance samples. Missing baselines remain blocked evidence.

Exact parity applies to unchanged output. Intentional semantic corrections require an explicit
source-backed difference ledger; unrelated output drift remains a failure. Compare equivalent
context modes and explicit fresh/warm processes. Host compilation does not prove PS4 ABI layout.

## Complexity and Risks

No new dependency is required. The dominant risks are false semantic equivalence, loss of DWARF
scope evidence, hidden declaration cycles, and acceptance over a reduced corpus. Mitigations are
identity-preserving fixtures, reasoned edges, per-root accounting, and pinned producer comparisons.
Storage health is a monitored prerequisite, not a presumed cause of every compilation problem.
