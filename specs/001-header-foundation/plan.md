# Implementation Plan: ABI-Oriented Header Foundation

**Branch**: `001-header-foundation` | **Date**: 2026-08-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-header-foundation/spec.md`

**Status**: Active implementation plan for the first brownfield feature.

## Summary

Restore a coherent executable baseline for evidence-preserving C++ header
reconstruction. DWARF parsing, durable artifact indexing, and Orbis assembly reports
remain separate evidence producers joined through provenance and diagnostics. The
first generated artifact is ABI-oriented and compilable where a supported compiler
is available; it does not claim to recover source comments, macros, formatting, or
method bodies.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.14+

**Primary Dependencies**: pyelftools, native `compression.zstd`, SQLite from the
standard library, pytest, and mypy. Ruff is invoked as a pinned UV tool. The pinned
Orbis objdump is optional and available only through an explicit local path.

**Storage**: Source-bound SQLite dump indexes, OS-local JSON symbol/header caches,
and deterministic JSONL/JSON evidence exports. ELF files, expanded dumps, generated
headers, logs, and caches remain local runtime artifacts.

**Testing**: `uv run pytest` with unit, integration, performance, and explicit
real-asset tiers; Ruff and mypy quality checks; compiler checks when a host C++
compiler is installed.

**Target Platform**: Windows development workstation, with PS4 x86-64 ELF/DWARF as
the primary evidence target and existing PS3 support retained.

**Project Type**: Python command-line tool and reusable parsing/generation library.

**Performance Goals**: Build a compressed-dump index with one streaming pass; warm
class and method lookups must not reopen the dump; fresh-process warm runs must reuse
validated source-bound artifacts and produce byte-identical results.

**Constraints**: Never materialize a 30+ GB expanded dump as one string; preserve
qualified names, offsets, sizes, alignments, source locations, and deterministic
ordering; publish artifacts atomically; do not commit proprietary inputs or output.

**Scale/Scope**: Thousands of compilation units and large multi-definition type
graphs from the PS4 `02020005` corpus. The feature covers header declarations,
layout evidence, artifact lifecycle, and assembly validation, not method-body
translation or full original-source recovery.

**Verified C++ Validation Environment**: Visual Studio Community 2026 `18.8.1`
with MSVC x64 compiler `19.51.36252.0`, discovered through
`C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe`. The
companion `ddon-hook` project at `C:/Users/morph/CLionProjects/ddon-hook` uses
CMake presets, VS2026 generators, C++23, and reusable MSVC warning conventions in
`cmake/CompilerWarnings.cmake`. Header verification must record whether it uses
the project C++23 setting, a reduced declaration-only standard, or explicit stubs
for unavailable DDON framework types.

**Validation Corpus**: The first run records the random candidates
`rTextureMemory`, `rTexture`, and `rTutorialDialogMessage`, plus the IDA anchors
`cSetInfoOmBreakTarget` and `rLayout`. Generated outputs are written to the local
ignored directory `output/msvc-header-validation-20260801/`. The comparison records
class kind, inheritance, sizes, fields, offsets, method signatures, and virtual slots;
IDA calling-convention spelling, globals, comments, and missing framework types are
classified separately.

**MSVC Invocation**: Load `VsDevCmd.bat -arch=x64`, compile a standalone C++23 probe
with `/std:c++latest /EHsc /W4 /Zc:__cplusplus`, then compile the generated-header
translation unit with the same flags. A failure caused by an unresolved DDON
framework dependency is a closure finding, not an automatic rejection of the
recovered field facts.

**Observed Verification Gaps**: The first five-header bundle identified missing base,
by-value, pointer-only, and nested-template closure. T045 and T046 now resolve those
cases for the standalone sample corpus with bounded structural dependency traversal;
method-signature-only references remain forward-declarable where complete definitions
are unnecessary. The repository's IDA artifacts are pseudo-headers only; method-body
and control-flow validation remains a separate later evidence phase.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Evidence fidelity**: PASS. The feature preserves evidence identifiers and keeps
  unresolved or conflicting facts diagnostic rather than guessed.
- **Source-bound artifacts**: PASS. The sidecar stores source identity, producer,
  schema, and configuration metadata and publishes replacements atomically.
- **Determinism and performance**: PASS. The sidecar scan is streaming and warm
  tests verify no dump reopen; output ordering is explicitly specified.
- **Layered design**: PASS. Changes stay within the existing application, domain,
  infrastructure, tests, and feature-artifact boundaries.
- **Validation before expansion**: PASS. Unit and artifact tests run, MSVC x64 is
  installed, the standalone C++23 probe passes, and the real sample run is recorded.
  Each of the five standalone probes compiles with exit code 0; `rLayout` retains
  only two C4201 nameless-union warnings. The aggregate multi-header translation
  unit exits with code 2, so aggregate acceptance remains open. Repeated shared
  declarations are the current root-cause hypothesis, not a confirmed compiler
  diagnostic because the raw compiler streams were not retained.

## Project Structure

### Documentation (this feature)

```text
specs/001-header-foundation/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── verification-msvc-ida-20260801.md # Evidence validation report
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
└── ddon_dwarf_reconstructor/
    ├── application/
    │   ├── exporters/
    │   └── generators/
    ├── domain/
    │   ├── models/dwarf/
    │   ├── repositories/cache/
    │   └── services/
    │       ├── generation/
    │       └── parsing/
    ├── generators/
    └── infrastructure/

tests/
├── domain/
├── generators/
├── infrastructure/
├── performance/
└── test_artifact_cli.py

.specify/
├── memory/constitution.md
├── scripts/powershell/
└── templates/
```

**Structure Decision**: Extend the existing package-relative DDD layout. Evidence
models and parsing rules remain in `domain/`; file, index, and cache adapters remain
in `infrastructure/`; orchestration remains in `application/`; tests mirror the
owning package. Spec Kit artifacts live under `specs/001-header-foundation/` and
must not contain runtime inputs or generated outputs.

## Current Verification Status

The MSVC/IDA verification report is complete for the recorded standalone probes.
T045 preserves nested class scope and emits a legal `MtTypedArray` primary-template
declaration for `rTutorialDialogMessage`; T046 adds bounded standalone base, by-value,
nested-pointer, enum, and template closure. Each of the five standalone probes
returns exit code 0, with only two C4201 nameless-union warnings in `rLayout`. The
aggregate multi-header translation unit returns exit code 2 and remains unresolved
until T048-T052 complete the completeness, scope, aggregate-closure, declarator,
and truthful validation work needed to classify the failure.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. The feature uses existing layers and adds no new deployable project.
