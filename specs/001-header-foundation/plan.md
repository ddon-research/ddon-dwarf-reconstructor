# Implementation Plan: ABI-Oriented Header Foundation

**Branch**: `001-header-foundation` | **Date**: 2026-08-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-header-foundation/spec.md`

**Status**: Active implementation plan for the first brownfield feature.

## Summary

Restore a coherent executable baseline for evidence-preserving C++ header
reconstruction. DWARF parsing, durable artifact indexing, and the dual-authority PS4
assembly/relocation evidence chain remain separate producers joined through provenance and
diagnostics. The
first generated implementation artifact is canonical exact-byte assembly/object evidence for a
later agentic C++ translation workflow. The implementation report is the single canonical
evidence index; the bundle also publishes bounded raw assembly and a deterministic AI context
packet. The core pipeline does not emit C++ or empty placeholders
or claim to recover source comments, macros, formatting, or behavior.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: CPython 3.14.7

**Primary Dependencies**: pyelftools, native `compression.zstd`, SQLite from the
standard library, Typer, pytest, Pyrefly, deptry, and Ruff. Matching Orbis binutils and
LLVM 22.1.8 `llvm-readobj`, and optional LLVM 22.1.8 `llvm-objdump` are local tools supplied
through explicit paths;
the in-repository SCE reader has no external runtime dependency.

**Storage**: Doris is the normal analytical read path over the one-time source-bound
Parquet-to-Doris publication. JSONL and Parquet are producer/load or audit artifacts only;
runtime generation and validation never open them. ELF files, expanded dumps, generated headers,
logs, and caches remain local runtime artifacts.

**Testing**: `uv run just` recipes with unit, integration, performance, and explicit
real-asset tiers; Ruff, Pyrefly, and deptry quality checks; compiler checks when a
host C++ compiler is installed.

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
graphs from the PS4 `02020005` corpus. The feature covers header declarations, layout
evidence, artifact lifecycle, and source-bound method/assembly evidence; it does not
claim method-body translation or full original-source recovery.

**PS4 Evidence Authorities**: Orbis binutils is authoritative for PS4 x86-64 instruction
decoding, demangling, and textual disassembly. LLVM `llvm-readobj` is an opt-in generic
ELF/DWARF structural cross-check; LLVM `llvm-objdump` is an opt-in target-aware per-method
cross-check using `x86_64-scei-ps4`. `OrbisSceMetadataReader` decodes SCE dynamic tags and
24-byte RELA tables relative to `PT_SCE_DYNLIBDATA`, retaining complete JSONL cache evidence
and projecting only method-relevant entries to the implementation report. It never applies
runtime relocations or synthesizes external declarations.

**SDK Definition Boundary**: Typed definitions are reproduced from SDK6500/n267 source files with
recorded hashes. The SDK defines `PT_SCE_DYNLIBDATA`, `PT_SCE_PROCPARAM`, `PT_SCE_COMMENT`,
`PT_SCE_LIBVERSION`, standard `PT_GNU_RELRO`, and relocation code 40
`R_X86_64_ORBIS_GOTPCREL_LOAD`; it does not define `PT_SCE_RELRO`. Unknown tags and relocation
codes remain numeric.

**Current Relocation Boundary**: On the target ELF, conventional Orbis `-r` output is empty,
and SCE metadata is observed with 172,404 `DT_SCE_RELA` entries plus 539 `DT_SCE_JMPREL`
entries. This is an evidence-status distinction, not a conclusion that the ELF has no
relocations. Known-invalid SDK profiles are capability-filtered and documented rather than
retried. The implementation-discovery report is schema `4.2`; the read-only validation report
is schema 4.1 for the current NID evidence fields (historical 4.0 reports remain retained
evidence). It keeps
relocation, NID, ABI/CFI, instruction safety, compiler/object, static parity, and live-behavior
statuses independent, and uses bounded Doris context batches plus address-indexed relocation/NID
evidence. The complete-corpus validator now publishes an atomic failed report with these
independent dimensions; no timeout is used as a substitute for completion evidence.

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

## Follow-up implementation plan: bounded static validation

The next best step is to make the existing static validator a repeatable Doris workload before
attempting another full Season 2 run. The validator must preserve the current evidence boundary:
ELF/DWARF and Doris drive production; IDA is a read-only post-generation completeness audit; and
accepted `.s`/`.o` artifacts do not imply ABI or semantic equivalence.

The first implementation slice is complete. `DorisImplementationEvidenceModel` now prefetches
method, parameter, object-pointer target, location, and CFI rows through bounded Doris family
queries, reconstructs a read-only context view, and emits one aggregate query diagnostic. The
validator builds reusable address-indexed relocation and relocation-ID/NID indexes once per run.
This keeps Parquet and JSONL out of the runtime path and removes the prior per-method context and
full-tuple rescan pattern. Focused tests and the full unit gate observed this code path; they are
implementation evidence. The subsequent pilot and full real-ELF validation are recorded in the
acceptance and analytical-store evidence pages.

The next execution sequence is:

1. Run a retained `rLayout` validator pilot with the complete Doris manifest and explicit SDK
   tools. Compare query count, elapsed time, report completeness, and independent statuses with
   the retained baseline. Do not configure an arbitrary timeout.
2. If the pilot publishes an atomic report, run the 1,150-method Season 2 validator with the same
   source, manifest, load-address policy, tool identities, and configuration. Publish only the
   complete aggregate report and concise counts; keep intermediate diagnostics disposable.
3. Investigate each remaining non-observed or conflicting dimension separately. Promote static
   `target-object-equivalent` only after relocation-normalized bytes, CFG/edges, NID identities,
   ABI/CFI/effect evidence, and accepted Orbis target objects all agree. Live behavior remains
   `not_observed` without a PS4 execution environment.

T082, the implementation prerequisite, and T083/T078, the real-asset pilot and full report
publication, are now observed. The resulting static report is still failed because ABI, compiler,
and semantic-parity gates are not closed.

### Next implementation tranche: context fidelity and evidence gates

The next work is deliberately narrower than another full-corpus rerun:

1. **Context fidelity (implemented):** preserve typed Doris location expressions in transformation
   cues and copy the recovered ABI-facts map into each validation context packet. A bounded live
   Doris probe and focused regressions now confirm frame-base and parameter expressions are not
   serialized as `null`.
2. **Diagnostic policy (implemented):** implementation validation no longer retains per-tool
   stdout/stderr files. `--tool-timeout-seconds` is an explicit caller option; the default has no
   tool timeout. Evidence retains tool identity, output hashes, and concise status plus timeout
   stage/timing/limit metadata when a timeout is actually imposed. The already documented SDK
   capability limitations do not trigger new invocations.
3. **Instruction-effect closure:** improve common x86-64 mnemonic normalization and stack-return
   modeling, then compare effects at CFI-covered boundaries. Unknown instructions, unresolved
   paths, and conflicting CFI remain non-promotable.
4. **Target acceptance and parity:** once the method-specific ABI/effect gate is complete, run
   Orbis clang/as/readelf/objdump on a bounded representative set, then expand to the full
   source-bound corpus. Promote static parity only after bytes, CFG/edges, NIDs, ABI/CFI/effects,
   and accepted target objects agree.

The existing full Season 2 report remains the batching baseline. It predates the context-fidelity
serializer correction and must not be silently relabeled as evidence for the corrected packet
contents. No broad rerun is justified until the diagnostic policy and the bounded representative
gate are ready. The older header-closure tasks T048-T053 remain separate open work and are not
closed by the implementation-validation optimization.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. The feature uses existing layers and adds no new deployable project.
