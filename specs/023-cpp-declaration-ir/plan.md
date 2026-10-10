# Implementation Plan: Incremental C++ declaration IR

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../docs/reference/project-status.md).

**Feature**: `023-cpp-declaration-ir` | **Date**: 2026-09-20 | [Specification](spec.md)

This architecture plan serves contributors after Feature 022 repair or its documented blocker
handoff. All new modules and adapters are proposed. [Measured evidence](measured-evidence.md)
does not claim an implemented IR or compiler integration.

## Summary and Solution Strategy

Extend `TypeReference` and `TypeScope` into a C++ declaration intermediate representation (IR).
Keep source observations, canonical identities, and output scheduling distinct. Use the compiler
as an optional validation authority through an infrastructure port, not as a hidden runtime parser
or a replacement source of recovered facts. Migrate a single declaration family at a time.

## Technical Context

| Item | Decision |
| --- | --- |
| Runtime | CPython 3.14.7, uv 0.12.3; existing dependency lock remains authoritative |
| Domain | Immutable Python declaration models built on existing structured references/scopes |
| Compiler default | Explicit pinned Clang subprocess, syntax checks and normalized AST observations |
| Alternative | LibTooling only after a reproduced subprocess capability gap and adoption decision |
| Storage | Existing analytical serving; versioned source-bound validation artifacts outside Git |
| Tests | Property tests, differential synthetic DWARF fixtures, normalized AST comparisons, MSVC bundles |
| Platform | Windows first; compiler/profile availability is explicit environmental evidence |
| Runtime budget | No compiler in normal generation; per-workload/cache-state p50/p95 <=110% matching baseline |

## Constitution Check

Pre-design and post-design checks pass at the plan level with no exceptions: recovered facts stay
separate from inferred compiler observations; new adapters stay in infrastructure; reusable
artifacts are atomic/source-bound; normal queries remain bounded and compiler-independent.
Acceptance is contingent on actual migration evidence and the existing quality gates.

## Building Blocks and Project Structure

Proposed paths, subject to coherent responsibility splits within repository structure limits:

- `domain/models/cpp/declarations.py`: identities, observations, typed declaration bodies.
- `domain/models/cpp/emission.py`: dependency requirements, planned output, source ledger.
- `domain/models/cpp/compiler_evidence.py`: project-owned profile/result records.
- `domain/ports/compiler_validation.py`: optional validation contract without concrete tools.
- `domain/services/generation/declaration_lowering.py`: evidence-to-declaration conversion.
- `domain/services/generation/declaration_scheduling.py`: legal declaration scheduling.
- `infrastructure/compiler/clang_validation.py`: bounded process execution and normalization.
- `application/generators/`: orchestration integrating repaired publication and the port.
- Mirrored tests and exact migration sites appear in [tasks](tasks.md).

Create package `__init__.py` files with their first modules. Domain dependencies remain standard
library and domain contracts only. The composition root owns adapter construction. Existing
`TypeReference`, `TypeScope`, family planning, publisher, and graph algorithms are reused.

## Runtime View

The source-bound query layer yields observations. Lowering resolves declarations while retaining
all contributing evidence. Requirements express availability and completeness independently.
Scheduling produces a legal emission plan or a reasoned diagnostic. Rendering writes bytes and
an identity-to-output ledger. Optional validation sends those artifacts to a named compiler
profile and joins normalized observations back through the ledger.

Compiler AST nodes never become persistent domain objects. DWARF source facts remain authoritative
for recovered identity/layout; compiler-synthesized declarations are additive observations with
their own origin. A validation disagreement is a finding, not permission to rewrite source facts.

## Migration Sequence

1. Inventory Feature 022's repaired baseline and residual blockers. Execute the bounded
   [research prompt](research-prompt.md); decide the first compiler profile and supported AST fields.
2. Add immutable declarations and adapt aliases/enums first. Test identity and unknown/conflicting
   evidence before adding emission behavior. Preserve exact unaffected bytes.
3. Move template signatures, method identity, and structured declarators to the model. Remove
   migrated string-based policy with its callers; do not retain two competing semantic paths.
4. Move requirements/ownership/scheduling to an emission plan. Introduce the source ledger at
   publication so diagnostics and compiler observations share identity.
5. Add optional Clang validation and normalized observations. Implement timeout, truncation,
   unavailable-tool and unsupported-schema results before treating successful output as evidence.
6. Run synthetic C++/DWARF differential checks and bounded real cases, then the complete corpus,
   fresh/warm modes, repository gates, and matched performance comparisons.

Each migration must be independently reviewable. A Feature 022 blocker may justify a targeted
prototype before full repair acceptance, but does not bypass corpus or performance gates.

## Research and Adoption Gate

Start with a subprocess because it isolates native versions and avoids a runtime extension.
AST extraction must be bounded by the small validation translation unit or evidence-based
filtering; indiscriminate full-corpus AST JSON loading is prohibited. Retain raw outputs externally
with size/hash metadata and normalize only supported fields.

Evaluate libclang and LibTooling against the same cases. Read LLDB's lazy type completion and
declaration-context handling as design evidence. Adopt native tooling only if its added capability
is demonstrated and licensing, Windows packaging, pinning, resource cost, and maintenance are
acceptable. LLVM IR/Rellic, syntax-only parsers, and new graph libraries do not solve this feature's
core semantic model. [Research](research.md) records the rationale and authority limits.

## Quality, Risks, and Completion

All Feature 022 acceptance dimensions remain mandatory. A pinned host Clang profile supplements
MSVC; neither proves PS4 ABI fidelity. Differential fixtures compare representable semantics,
not unavailable comments/macros or exact original source syntax. Unsupported DWARF producer forms
remain explicit. Measure validation separately from ordinary generation.

Principal risks are compiler schema drift, synthesized facts mistaken for evidence, excessive AST
memory, accidental target assumptions, and permanent dual implementations. Typed normalized
records, strict statuses, bounded fixture extraction, profile identities, and removal tasks address
those risks. No complexity exception or dependency promotion is granted by this plan.
