<!--
Sync Impact Report
- Version change: template -> 1.0.0
- Modified principles: replaced all illustrative principles with five DDON reconstruction principles
- Added sections: Evidence and Artifact Constraints; Development Workflow and Quality Gates
- Removed sections: illustrative template guidance and unresolved placeholder text
- Follow-up TODOs: select the target C++ standard and compiler proxy in the first header feature
-->

# DDON DWARF Reconstructor Constitution

## Core Principles

### I. Evidence Fidelity

The system MUST distinguish facts recovered from ELF, DWARF, assembly, and external
authority from inferred or synthesized content. It MUST preserve qualified names,
DIE/CU offsets, source locations, sizes, alignments, field offsets, inheritance
attributes, declaration kinds, and deterministic ordering whenever the evidence
provides them. Unsupported or conflicting evidence MUST remain visible as a
diagnostic; it MUST NOT be silently replaced with a guessed declaration.

The first acceptance tier is an ABI-oriented, compilable header reconstruction.
Exact original comments, macros, formatting, and source constructs that are not
represented in the available evidence are explicitly outside that tier.

### II. Source-Bound Durable Artifacts

Every reusable index, cache, report, export, and generated header metadata record
MUST identify its source input and output-affecting producer, schema, and
configuration versions. Writers MUST publish artifacts atomically and preserve the
last valid artifact until a replacement has been validated. A same-path source
replacement MUST NOT reuse stale offsets or derived declarations.

Runtime artifacts remain local and rebuildable, but rebuildable does not mean
temporary. Routine cleanup MUST preserve validated source-bound artifacts. Purge,
repair, and rebuild operations MUST be explicit and narrowly targeted.

### III. Determinism and Performance

The implementation MUST produce stable output ordering and byte-identical results
for equivalent fresh-process and warm-cache runs. Output-affecting work MUST NOT
depend on unordered set or dictionary traversal. The implementation MUST avoid
repeated ELF hashing, repeated full-DIE scans, whole-dump materialization, and
unbounded in-memory intermediates. Expensive bootstrap work is acceptable when it
creates a validated durable artifact that makes later lookups fast.

Performance claims MUST name the input, cold or warm state, process boundary, and
measurement method. A timeout or cache hit MUST NOT be reported as successful
evidence extraction without recording the limitation.

### IV. Layered and Focused Design

Application orchestration, domain evidence models and services, and infrastructure
adapters MUST remain separated. New behavior MUST use the nearest existing
abstraction and package-relative imports. Parsers MUST preserve evidence; domain
services MUST express reconstruction rules; renderers MUST consume structured
models rather than re-parsing presentation strings. New abstractions are justified
only when they remove real duplication, isolate a changing boundary, or make a
contract independently testable.

### V. Validation Before Expansion

Every behavior change MUST have a focused validation at the narrowest useful tier:
unit tests for deterministic logic, integration tests for DWARF and artifact
boundaries, compiler checks for generated C++, and explicit opt-in real-asset or
performance tests for the PS4 corpus. Assembly evidence is initially a validation
input for DWARF-derived declarations and layouts; it MUST NOT invent declarations
without an explicit later contract.

Tests MUST cover negative, incomplete, duplicate-definition, and ambiguity cases.
Generated headers MUST be checked for compilability and dependency closure where
the selected compiler is a valid proxy. Real ELF files, expanded dumps, and
proprietary tools MUST be supplied through explicit local paths and MUST NOT be
committed.

## Evidence and Artifact Constraints

- Regular CPython 3.14.6 and `uv` are the supported runtime and dependency workflow.
- `uv run ddon-dwarf-reconstructor` is the canonical executable entry point.
- `AGENTS.md` is the operational repository contract; client-specific adapters
  MUST not duplicate or contradict it.
- The PS4 `02020005` ELF and compressed LLVM DWARF dump are immutable local inputs.
- Symbol caches, SQLite indexes, source catalogs, reports, and exports MUST be
  source-bound and atomically published.
- Generated headers are derived evidence products, not recovered original source.
- Assembly reports from the pinned Orbis producer remain independently reproducible
  and joinable through explicit evidence identifiers.

## Development Workflow and Quality Gates

1. Establish or update the feature specification before cross-module behavior
	changes. Record non-goals, evidence provenance, uncertainty, and acceptance
	checks.
2. Resolve ambiguities before implementation. Plans and tasks MUST name exact
	source and test paths and distinguish unit, integration, compiler, and real-asset
	validation.
3. Implement the smallest coherent slice, then run its focused check before
	expanding scope.
4. Before completion, run the relevant unit tests, `uvx ruff check --no-fix
	src tests`, `uvx ruff format --check src tests`, and `uv run mypy src`.
5. Documentation MUST be updated when commands, configuration, public contracts,
	artifact lifecycle, or supported behavior changes. Documentation MUST describe
	verified behavior rather than historical claims.
6. Cleanup commands MUST remove transient tool output only. Durable artifacts and
	research evidence require an explicit retention or purge decision.

## Governance

This constitution defines non-negotiable project principles. `AGENTS.md` supplies
operational details and must remain consistent with it; Spec Kit feature artifacts
define scoped behavior and may add stricter acceptance criteria but may not weaken
these principles.

Amendments MUST update the Sync Impact Report, version, and last-amended date.
Versioning follows semantic intent: MAJOR for incompatible principle changes, MINOR
for new or materially expanded principles, and PATCH for clarifications. A change
that affects source identity, evidence semantics, output determinism, or generated
C++ validity requires a focused regression test and documentation update.

Every implementation review MUST check evidence provenance, artifact safety,
determinism, performance assumptions, validation coverage, and documentation
consistency. Deferred work MUST be recorded in the relevant Spec Kit task or
feature artifact rather than hidden in generated output.

**Version**: 1.0.0 | **Ratified**: 2026-08-01 | **Last Amended**: 2026-08-01
