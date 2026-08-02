# Feature Specification: ABI-Oriented Header Foundation

**Feature Branch**: `001-header-foundation`

**Created**: 2026-08-01

**Status**: Draft

**Input**: Establish a trustworthy first header-reconstruction tier from PS4 ELF
DWARF evidence, with deterministic source-bound artifacts and assembly validation.

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.

  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Generate a compilable ABI header (Priority: P1)

As a reverse engineer, I want to select a type from a PS4 ELF and receive a
compilable C++ header that preserves the recoverable layout and declaration facts,
so I can use the result as a reliable basis for analysis and later source recovery.

**Why this priority**: A trustworthy header is the first usable artifact and
provides the contract that later assembly and method-reconstruction work depends on.

**Independent Test**: Run generation against a curated DWARF fixture containing one
aggregate, one nested type, and one inheritance relationship; compile the resulting
header and compare its recorded size, alignment, offsets, and provenance with the
fixture evidence.

**Acceptance Scenarios**:

1. **Given** a complete type definition and its referenced layout types, **When**
  the type is generated, **Then** the output contains valid C++ declarations in a
  deterministic order and records the source DIE/CU evidence.
2. **Given** an incomplete or unsupported type form, **When** the type is generated,
  **Then** the output remains syntactically valid where possible and exposes an
  explicit diagnostic instead of silently emitting a guessed type.
3. **Given** the verified MSVC x64 environment, **When** a generated sample header is
  compiled as C++23, **Then** each standalone translation-unit result records its
  exit code and diagnostics, and an aggregate translation-unit result is reported
  separately rather than being inferred from the standalone results.
4. **Given** an aggregate of generated headers, **When** shared declarations or
  cross-file dependencies prevent compilation, **Then** the aggregate remains a
  failed acceptance dimension with a deterministic closure/rendering diagnostic;
  five passing standalone probes MUST NOT be reported as an aggregate pass.

---

### User Story 2 - Reuse validated evidence deterministically (Priority: P2)

As a reverse engineer processing many types, I want validated indexes and caches to
be reused only for the same source and configuration, so repeated analysis is fast
without risking stale offsets or changed declarations.

**Why this priority**: The PS4 dump is very large and repeated full scans are
impractical; correctness requires that speedups never change the evidence source.

**Independent Test**: Build a sidecar and header cache from a fixture, run the same
lookup in a fresh process, then replace the source at the same path and verify that
the old result is rejected and the new result is rebuilt.

**Acceptance Scenarios**:

1. **Given** an existing valid sidecar, **When** a warm lookup is repeated, **Then**
  the compressed dump is not reopened and the result is byte-identical.
2. **Given** a source with only metadata timestamp changes, **When** a lookup runs,
  **Then** the valid sidecar remains reusable.
3. **Given** different source content at the same path, **When** a lookup runs,
  **Then** stale offsets are rejected and a replacement is published atomically.

---

### User Story 3 - Validate declarations with assembly evidence (Priority: P3)

As a reverse engineer, I want assembly reports to validate recovered method and
layout hypotheses, so disagreements are visible before I rely on a reconstructed
header.

**Why this priority**: Assembly can confirm or challenge DWARF-derived facts, but it
must remain evidence rather than an unmarked source of invented declarations.

**Independent Test**: Pair a bounded disassembly fixture with a generated header,
run validation, and assert that matching facts pass while conflicting method ranges,
ownership, or member-offset hypotheses produce traceable diagnostics.

**Acceptance Scenarios**:

1. **Given** matching DWARF and assembly evidence, **When** validation runs, **Then**
  the result records the evidence identifiers and reports no false disagreement.
2. **Given** conflicting evidence, **When** validation runs, **Then** the conflict is
  reported with both sources and the header is not silently rewritten.
3. **Given** a local IDA pseudo-header for a comparison anchor, **When** the generated
  declarations are compared, **Then** recoverable facts are classified as matching,
  conflicting, or unavailable, while IDA-only presentation details remain separate.

---

[Add more user stories as needed, each with an assigned priority]

### Edge Cases

- The requested symbol has only forward declarations or no complete DIE.
- Multiple CUs contain definitions with different sizes or nested-type completeness.
- A by-value dependency is unavailable while a pointer-only dependency is present.
- Two source paths contain the same basename and would otherwise collide as headers.
- A compressed dump or SQLite sidecar is truncated, corrupt, or bound to another source.
- A declaration contains an array, bitfield, template parameter, function pointer, or
  qualifier that cannot be represented safely by the current type renderer.
- A selected definition is declaration-only, partial, unresolved, or conflicting and
  a base or by-value dependency cannot be emitted as a complete definition.
- The host compiler is not a faithful proxy for a PS4-specific ABI rule.
- Assembly names are stripped, indirect, ambiguous, or do not map one-to-one to DIEs.
- MSVC rejects a generated header because a framework type is absent from the test
  closure even though the recovered field itself is supported.
- A virtual method uses a DWARF location expression other than the supported simple
  `DW_OP_constu` form.
- The available IDA artifact is a pseudo-header without method-body pseudocode.

## Requirements *(mandatory)*

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right functional requirements.
-->

### Functional Requirements

- **FR-001**: The system MUST generate a C++ header for a selected complete or
  partially recoverable type from the supplied ELF/DWARF evidence.
- **FR-002**: The generated header MUST preserve recoverable type kind, qualified
  identity, inheritance, member layout, method signatures, source locations, and
  DIE/CU offsets in structured evidence and metadata.
- **FR-003**: The system MUST distinguish complete definitions, declarations,
  unresolved references, and conflicting definitions in its output diagnostics.
- **FR-004**: By-value layout dependencies MUST be resolved to complete definitions
  or reported as unresolved; pointer/reference-only dependencies MAY use legal
  forward declarations.
- **FR-005**: Header output MUST use stable ordering and MUST report standalone and
  aggregate compilation independently. A representative corpus is not accepted as
  compilable when its aggregate translation unit has a nonzero exit code.
- **FR-006**: Single-file and multi-file output MUST produce collision-safe names,
  deduplicated shared declarations, and a valid cross-file dependency/include closure.
- **FR-007**: Reusable symbol, dump, and header artifacts MUST be bound to source
  identity plus producer/schema/configuration identity.
- **FR-008**: Artifact publication MUST be atomic and MUST preserve the last valid
  artifact if a replacement build fails.
- **FR-009**: Compressed dump indexing MUST make one streaming pass and MUST NOT
  materialize the complete expanded dump in memory.
- **FR-010**: The system MUST expose explicit inspect, repair, rebuild, and narrowly
  confirmed purge operations for durable dump indexes.
- **FR-011**: Assembly validation MUST consume independently identified reports and
  record matching or conflicting evidence without inventing declarations.
- **FR-012**: Exact original comments, macros, formatting, method bodies, and source
  constructs absent from the evidence MUST be labeled out of scope for this feature.
- **FR-013**: The verification workflow MUST support the installed MSVC x64 toolchain
  discovered through `vswhere.exe` and MUST record compiler version, language
  standard, flags, object status, stdout, stderr, and exit code for every standalone
  translation unit and for the aggregate translation unit separately. Warnings such
  as C4201 MUST be classified explicitly rather than silently treated as success.
- **FR-014**: The sample workflow MUST record at least three random non-template
  resource candidates plus the IDA anchors `cSetInfoOmBreakTarget` and `rLayout`.
- **FR-015**: IDA cross-checks MUST compare recoverable class kind, inheritance,
  member names/types/offsets, sizes, method names/signatures, and virtual slots;
  calling-convention spelling, global symbol names, comments, and unavailable
  framework definitions MUST be classified separately.
- **FR-016**: The parser MUST preserve simple PS4 `DW_OP_constu` vtable locations as
  their decoded slot values and MUST leave unsupported expressions unresolved.
- **FR-017**: Completeness status MUST propagate from selected DIE definitions through
  dependency traversal and rendering. A declaration-only, partial, unresolved, or
  conflicting base or by-value dependency MUST produce a deterministic blocking
  diagnostic; it MUST NOT be rendered as an empty guessed definition or presented as
  compilable.
- **FR-018**: Nested classes and template specializations MUST retain containing
  scope and MUST render as legal C++ declarations; qualified nested names MUST NOT
  be emitted as undeclared template arguments.
- **FR-019**: The verification workflow MUST report when IDA method-body pseudocode
  is unavailable and MUST NOT claim behavioral or body-level agreement from
  pseudo-header declarations alone.

### Key Entities *(include if feature involves data)*

- **Evidence Source**: An immutable ELF, compressed DWARF dump, or bounded assembly
  report identified by content and producer metadata.
- **Recovered Type**: A qualified C++ aggregate or related declaration with layout,
  signature, source, completeness, and provenance facts.
- **Artifact Index**: A reusable lookup product mapping evidence identities to DIE,
  CU, definition, and implementation records.
- **Header Bundle**: One or more generated headers plus deterministic metadata and
  diagnostics for the requested closure.
- **Validation Diagnostic**: A structured explanation of missing, conflicting, or
  unsupported evidence linked to the affected entity and source identifiers.

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

- **SC-001**: Every supported representative standalone translation unit compiles
  successfully, and the aggregate translation unit also exits successfully before
  the representative corpus is reported as a complete compiler pass. Any nonzero
  result is retained with a blocking diagnostic instead of being masked by standalone
  success.
- **SC-002**: Two fresh-process runs over identical evidence produce byte-identical
  headers, manifests, and diagnostics for every representative fixture.
- **SC-003**: A warm class or method lookup reuses the validated sidecar without
  reopening the compressed dump, and a changed source at the same path never reuses
  the previous offset mapping.
- **SC-004**: A complete streaming index pass uses bounded parser state rather than
  retaining the expanded dump as one in-memory string.
- **SC-005**: Every generated declaration and dependency in the representative corpus
  can be traced to at least one DIE/CU and completeness state, or to an explicit
  unresolved, conflicting, unsupported, or unavailable-evidence diagnostic.
- **SC-006**: Assembly validation reports 100% of seeded fixture disagreements with
  both the affected header fact and the contributing evidence identifiers.
- **SC-007**: The verified sample run records generation, per-translation-unit MSVC
  exit code, compiler flags, object status, captured stdout/stderr, and aggregate
  status for three random resource candidates plus both IDA anchors, with no
  unclassified compiler or comparison outcome.
- **SC-008**: For each IDA anchor, every compared recoverable fact is classified as
  matching, conflicting, or unavailable with a source reference; no presentation-only
  difference is reported as an ABI contradiction.
- **SC-009**: Virtual methods in the sample DWARF with simple `DW_OP_constu` locations
  retain their decoded nonzero slots where the evidence contains them.
- **SC-010**: The sample report classifies standalone and aggregate compilation
  failures into missing closure, invalid rendering, duplicate declaration, or
  unavailable external evidence. A duplicate-declaration explanation remains a
  hypothesis until the corresponding compiler diagnostics are captured.
- **SC-011**: No IDA pseudo-header comparison is reported as a method-body or control-
  flow validation when pseudocode artifacts are absent.
- **SC-012**: Declaration-only, partial, unresolved, and conflicting states propagate
  into deterministic diagnostics that identify the affected type/dependency and state
  whether compilation is blocked.

## Current Verification Baseline

The verified MSVC/IDA run establishes the following current state:

- MSVC x64 `19.51.36252.0` and a C++23 compiler probe pass.
- Three random candidates and two IDA anchors generate successfully from the warm
  source-bound DWARF index.
- Isolated declaration checks pass for `rTexture`/`rTextureMemory`,
  `cSetInfoOmBreakTarget`, and `rLayout` when missing external definitions are
  supplied as explicit stubs.
- Five standalone generated probe translation units pass with MSVC x64: `rTexture`,
  `rTextureMemory`, `cSetInfoOmBreakTarget`, `rLayout`, and
  `rTutorialDialogMessage`. T045 emits the nested `cDialogPage` definition and legal
  `MtTypedArray` template declaration; T046 supplies the required standalone base,
  by-value, nested-pointer, enum, and structural template closure.
- The aggregate multi-header translation unit exits with code 2. This is a separate
  current failure and means the representative corpus is not yet an aggregate pass.
  Generated headers contain repeated shared declarations, making duplicate
  declaration handling the current root-cause hypothesis. Raw compiler stderr was
  not retained, so no C2011 diagnostic is confirmed and the hypothesis MUST NOT be
  documented as a captured compiler error.
- `cSetInfoOmBreakTarget` recoverable facts match the IDA pseudo-header and DWARF,
  including `mBreakHitNum` at offset 112 and decoded virtual slots.
- `rLayout` size, base, enum, and main field facts match available evidence; nested
  `SetInfo` and `SetInfoBuffer` declarations compile, with two MSVC C4201 warnings
  for recovered nameless unions.
- The current wrapper does not retain a complete per-translation-unit report with
  stdout/stderr, compiler flags, object status, and an explicit `compile_tutorial.cpp`
  row. T052 is required before the MSVC result can be called fully auditable; C4201
  acceptance remains an explicit classification decision.
- The repository has IDA pseudo-headers but no IDA method-body pseudocode, so
  behavioral and body-level reconstruction is not yet evaluated.

## Assumptions

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right assumptions based on reasonable defaults
  chosen when the feature description did not specify certain details.
-->

- The first users are maintainers and reverse engineers who can provide explicit
  local paths to PS4 ELF, DWARF dump, and optional Orbis tools.
- The first acceptance tier is ABI-oriented and compilable; source-faithful comments,
  macros, formatting, and method bodies require later evidence or features.
- The existing Python, DWARF, artifact, and Orbis components are retained where their
  contracts can be made coherent rather than replaced wholesale.
- MSVC x64 19.51.36252.0 is available through Visual Studio Community 2026 and is the
  current declaration-compilation gate; its Windows ABI is not proof of every PS4
  proprietary compiler/layout rule.
- The companion `ddon-hook` CMake project is a toolchain reference only; its existing
  MinGW/Ninja cache is not reused for this verification, while its C++23 and MSVC
  warning conventions are recorded.
- Real game binaries and expanded dumps remain local and opt-in; fixtures represent
  their structure without embedding those assets in the repository.
