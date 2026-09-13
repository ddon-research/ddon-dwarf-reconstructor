# Feature Specification: ABI-Oriented Header Foundation

**Feature Branch**: `001-header-foundation`

**Created**: 2026-08-01

**Status**: Observed-partial; header publication and host MSVC closure are complete for the
current real-asset run, while PS4 ABI, instruction-effect, NID, static-parity, and live-behavior
dimensions remain open.

**Input**: Establish a trustworthy first header-reconstruction tier from PS4 ELF
DWARF evidence, with deterministic source-bound artifacts and assembly validation.

## Current evidence boundary (2026-08-16)

The current implementation record is
[`acceptance-season2-assembly-20260816.md`](acceptance-season2-assembly-20260816.md). It covers
289 roots, 2,760 source-derived headers, independent 2,760/2,760 MSVC translation-unit passes,
and 1,150 clean source-bound assembly bundles. These observations establish deterministic
publication, host declaration/closure acceptance, and bounded artifact integrity; they do not
establish PS4 ABI/register-stack safety, complete source-bound NID-name coverage,
instruction-effect closure,
compiler transformation equivalence, static target-object equivalence, or live PS4 behavior.

The serving and validator record is
[`measured-evidence.md`](../019-analytical-dwarf-store/measured-evidence.md). Doris remains the
normal analytical runtime. IDA remains post-generation cross-validation only and cannot repair or
promote generated evidence.

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

When requested, the completed header is also the input to a separate implementation-discovery
follow-up. That follow-up must not change header bytes, header ordering, header manifests, or
header success/failure semantics. It may produce explicit method implementation and Orbis
assembly evidence states after header publication.

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

### User Story 4 - Preserve PS4 method reconstruction evidence (Priority: P3)

As a reverse engineer, I want a completed header to feed a separate Orbis evidence chain and,
only for uniquely associated methods, produce canonical assembly/object artifacts for a later
agentic C++ translation workflow while retaining all raw and structured context in one canonical
source-bound report.

**Independent Test**: Run a fixture with unique, ambiguous, indirect-call, and unavailable
methods; assert that headers and their SHA-256 remain unchanged, every candidate and consumed
profile invocation is retained, and only the unique method receives `.s`/`.o` artifacts.

**Acceptance Scenarios**:

1. **Given** a successful header bundle and `--extract-assembly`, **When** Orbis discovery times
   out or reports an unsupported profile, **Then** the header manifest remains published and the
   implementation report records the unavailable evidence.
2. **Given** `--emit-implementation-sources` without `--extract-assembly`, **When** generation is
   requested, **Then** the CLI rejects the incompatible options before generation.
3. **Given** one unique DWARF candidate, valid range, and unique Orbis function, **When** source
   emission is enabled, **Then** the bundle contains exact-byte `.s` evidence and an accepted `.o`
   when `orbis-as` is available, while raw text, bytes, references, and hashes remain in the
   canonical JSON report.
4. **Given** an ambiguous, partial, unresolved, deleted, defaulted, or unavailable method,
   **When** source emission is enabled, **Then** no C++ definition is emitted and all candidates
   and status diagnostics remain in the JSON index.
5. **Given** `--llvm-objdump` and a requested target triple, **When** a per-method slice succeeds,
   fails, times out, or is unsupported, **Then** the exact target invocation and compact
   address/byte comparison status are retained without changing Orbis output or the header bundle.

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
- **FR-006a**: Every normal `generate` request MUST execute one source-bound symbol traversal and
  publication. A single `--symbol` MUST resolve its complete dependency closure; `--symbols-file`
  and repeated `--symbol` values MUST resolve one globally deduplicated union. The route MUST
  reject `--single-file` and MUST NOT create per-root batches or `symbols/<index>-<safe-root>/`,
  `implementations/`, or `methods/<id>/` directories.
- **FR-006b**: Symbol dependency traversal MUST include method return and parameter types,
  follow declaration/specification references to complete definitions where available, and retain
  unresolved definitions as explicit diagnostics. The `rAchievement`/`MtDataReader` regression
  MUST resolve one complete `MtDataReader` definition when the source evidence provides it.
- **FR-006c**: Symbol publication MUST use `generated/ps4-<client-version>/` by default, infer one
  unambiguous eight-digit client token from the ELF filename or nearest parent path, and record
  the source/diagnostic or `unknown` fallback in `symbols.manifest.json`. The manifest MUST bind
  the input-list hash, producer/schema/configuration identity, ownership/provenance, file hashes,
  counts, per-root statuses, and unresolved/conflict diagnostics. The version directory MUST be
  atomically staged and committed with flat resource and `shared/` outputs.
- **FR-006d**: Symbol readable `.asm` exports MUST begin with semicolon-commented method/type,
  pseudo-symbol, address/range, file-offset, source-location, ABI/context, and evidence-status
  metadata. Calls MUST use `; pseudo_call: ...` and source references MUST use `; source: ...`.
  Exact-byte `.s`/`.o` artifacts remain a separate opt-in profile, and assembly availability MUST
  NOT promote header completeness.
- **FR-006e**: Generation context files, including manifests and validation/probing reports emitted
  by the generation workflow, MUST be controlled by `--generate-context`. Development defaults
  MUST enable the flag; `--no-generate-context` MUST publish only C++ headers and assembly files.
  Explicit `artifacts` validation and probing commands retain their own output contracts.
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
- **FR-020**: Header publication MUST complete before optional implementation or
  Orbis discovery starts; a follow-up failure MUST NOT prevent a valid header
  bundle and manifest from remaining published.
- **FR-021**: `--emit-implementation-sources` MUST require `--extract-assembly` and MUST emit a
  bounded original `.raw.asm` evidence file, a canonical exact-byte `.s` compiler input, a
  deterministic `.context.json` packet, and an SDK-produced `.o` only when `orbis-as` accepts the
  `.s` for a unique, complete DWARF-to-Orbis method match. `.raw.asm` MUST never be passed to the
  assembler. The core pipeline MUST NOT emit C++, empty, reference, or diagnostic placeholders.
- **FR-022**: Orbis evidence MUST retain exact profile flags, command, return status,
  tool identity, duration, stdout/stderr paths and hashes, source line/discriminator,
  file offset, relocation, direct/indirect call or branch, data reference, and
  unresolved operand evidence.
- **FR-023**: Generated `.s` MUST be a clean recompilable, exact-byte compiler input and MUST
  preserve instruction bytes without synthesizing untyped external declarations or claiming MSVC,
  ABI, clobber, stack-safety, or behavioral portability. `.raw.asm` is evidence only. C++
  translation is a later workflow and no C++ file is emitted by this pipeline.
- **FR-024**: Implementation source bundles and their JSON indexes MUST publish
  atomically, reject duplicate stable method IDs and invalid header mappings, and
  preserve all ineligible method candidates and diagnostics.
- **FR-025**: The implementation report MUST use schema `4.2` and the bundle manifest MUST use
  schema `3.1`. Artifact descriptors MUST include kind, role, content type, byte length, producer,
  relative path, and SHA-256. The report MUST serialize instruction-owned references only once,
  retain exact method-range raw text, and expose structured limitations for ABI, semantic, and
  external-declaration boundaries. Each eligible method MUST have an
  `implementation-context/1.0` packet that references, rather than duplicates, `.raw.asm`.
- **FR-026**: When `--llvm-objdump` is supplied with `--extract-assembly`, the system MUST run
  independently cached method-range slices with `x86_64-scei-ps4` by default, retain the exact
  capability probe and command evidence, and store only compact comparison summaries in the
  implementation report. LLVM failure or disagreement MUST NOT change Orbis instruction authority,
  method eligibility, header bytes, or generated assembly selection.
- **FR-027**: The generic `llvm-readobj` profile MUST remain target-neutral and record its target
  status as `not_applicable`; `llvm-tli-checker` MUST remain outside the ELF extraction path.
- **FR-028**: SDK-derived PS4 definitions MUST be typed, source-hash-bound, and preserve unknown
  numeric SCE tags and relocation codes. The runtime MUST distinguish standard `PT_GNU_RELRO` from
  the absent official `PT_SCE_RELRO` definition and MUST NOT apply relocations or synthesize
  external declarations.
- **FR-026a**: The source-bundle manifest MUST be a minimal publication envelope containing
  report/header/source identities, hashes, bundle digest, file count, and status; it MUST NOT
  duplicate method evidence or per-method indexes.
- **FR-027a**: Orbis standard-relocation (`-r`) output MAY be retained as an independent
  cross-check. The known-invalid `-R` profile and the rejected `-t -T` symbol combination MUST be
  capability-filtered before execution and documented once rather than emitted as repeated
  unavailable runtime diagnostics.
- **FR-028a**: The SCE metadata reader MUST validate `PT_SCE_DYNLIBDATA`-relative ranges and decode
  `DT_SCE_RELA` and `DT_SCE_JMPREL` 24-byte RELA entries, preserving raw fields, signed addends,
  unknown vendor values, symbol resolution status, and stable relocation IDs without applying
  relocations or synthesizing declarations. LLVM structural cross-checks MUST remain opt-in and
  additive to Orbis instruction evidence.
- **FR-029**: `artifacts validate-implementation` MUST be read-only, source-bound, and publish a
  versioned report with independent relocation, NID, ABI/CFI, instruction-safety, compiler/object,
  static-parity, and live-behavior statuses. It MUST require an explicit original-address or
  aligned load-base policy and MUST never infer a runtime base from an IDA/Ghidra default.
- **FR-030**: The validator MUST map relocation targets through PT_LOAD, use
  PT_SCE_DYNLIBDATA only for SCE metadata geometry, check alignment/coverage/overflow/target
  bytes, and preserve opaque NIDs, encoded symbols, and module/library identities. It MAY accept
  a community-derived mapping as external candidate evidence when its path/hash and provenance
  are retained. A community name MUST remain partial until its NID hash and encoded
  library/module context verify; malformed, missing, conflicting, or mismatched evidence MUST
  fail closed.
- **FR-031**: A complete analytical store MAY supply method DIE/CU identity, object-pointer and
  artificial/hidden-parameter facts, parameter/return/frame-base locations, and CFI. Missing or
  conflicting CFI MUST prevent safety promotion. The instruction analyzer MUST fail closed for
  unknown instructions, unbalanced stack paths, indirect calls, and unpreserved callee-saved
  registers.
- **FR-031a**: Implementation validation MUST obtain method-specific analytical rows through the
  source-bound Doris serving publication. The supplied manifest is a publication and source
  identity pin only; the validator MUST NOT read Parquet or JSONL rows directly or silently fall
  back to a file-backed adapter. The Doris model MUST retain the normalized typed family contract
  and push CFI range-overlap filtering to the serving engine.
- **FR-032**: The validator MUST emit canonical `.s` and `.o` artifacts only after Orbis assembler
  acceptance and MUST record bounded Orbis clang probe, compiler flags, target triple, object
  metadata, diagnostics, tool hashes, and output hashes. C++ inline-assembly wrappers remain
  unavailable unless their constraints, clobbers, returns, dialect, and compiler acceptance are
  independently derived.
- **FR-033**: target-object-equivalent MUST require observed relocation-normalized bytes, CFG,
  branch/call/external-edge identity, an observed non-conflicting NID/import/export identity
  (including community_verified where a community map supplies the name), ABI/register/stack/CFI
  effects, and accepted Orbis target objects. Live execution and behavioral equivalence MUST remain
  separately reported and `not_observed` without a PS4 execution environment.

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
- **Orbis Reference**: A resolved or unresolved call, branch, data, or relocation
  operand with raw text, address/name evidence, and resolution status.
- **Orbis Tool Invocation**: One exact profile command and its retained output,
  hashes, status, timing, and tool identity.
- **Orbis Dynamic Tag**: A numeric SCE dynamic tag, optional known name, and raw value.
- **Orbis Relocation Table/Entry**: A validated SCE table descriptor and one raw 24-byte RELA
  record with decoded `r_info`, signed addend, optional symbol name, resolution status, and
  method/instruction links.
- **Orbis Structural Cross-Check**: An optional LLVM `llvm-readobj` result with exact command,
  output hash, unknown numeric SCE tags, and an additive availability status.
- **Orbis Targeted Cross-Check**: An optional per-method `llvm-objdump` result with requested and
  effective target triple, capability status, range cache identities, and address/byte comparison
  totals; complete output remains in the external evidence cache.
- **Implementation Source Bundle**: A source-bound versioned JSON evidence index, a minimal
  publication manifest, and optional per-method exact-byte `.s`/`.o` derived views emitted after
  header commit.
- **Implementation Artifact Descriptor**: A typed derived-view kind, safe relative path, and
  content hash owned by the corresponding method record.

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
- **SC-013**: An explicitly configured timeout or failed Orbis profile leaves the previously
  committed header manifest and header bytes unchanged. Known-invalid SDK profiles are not run.
- **SC-014**: Source emission produces exactly one stable method directory per unique eligible
  match with bounded `.raw.asm`, exact-byte `.s`, and `.context.json` artifacts, plus an `.o`
  artifact only when `orbis-as` accepts the `.s`. `.raw.asm` is never assembler input. It emits no
  C++, reference, notes, empty, or unstructured diagnostic files, and emits no artifacts for every
  seeded ambiguous, partial, unsupported, unresolved, deleted, defaulted, pure-virtual, or
  unavailable method.
- **SC-015**: Two fresh source-emission runs over identical header, DWARF, ELF, and Orbis evidence
  produce byte-identical report, method IDs, artifact descriptors, `.raw.asm`/`.s`/`.o`/
  `.context.json` files, and manifests; a partial publication leaves no staging files and a
  successful report-only run retires the stale source bundle.
- **SC-016**: The canonical report preserves every decoded instruction, raw byte sequence,
  source/file-offset relationship, reference, candidate, and tool-invocation fact previously
  available from the redundant derived files.
- **SC-017**: A PS4 fixture with SCE dynamic metadata records the useful `-r` cross-check and
  capability-filtered status of unsupported SDK profiles, validates `DT_SCE_RELA`/`DT_SCE_JMPREL`
  counts from their sizes and entry size, preserves signed addends and unknown codes, and exposes
  only method-relevant relocation entries in the report while retaining the complete producer
  cache.
- **SC-018**: When `--llvm-readobj` is supplied, the exact JSON command and output hash are retained,
  unknown numeric `0x610000xx` tags remain visible, and an LLVM failure leaves the header and the
  Orbis/SCE evidence outcome unchanged.
- **SC-019**: When `--llvm-objdump` is supplied, the capability probe and every method-range command
  retain `x86_64-scei-ps4` (or the explicit requested triple), cache identity, range, output hashes,
  and comparison totals; a target profile failure leaves the header, Orbis evidence, method IDs,
  and source artifacts unchanged.
- **SC-020**: The SDK-definition identity preserves the four source-file hashes, complete useful
  SCE dynamic-tag names, relocation-40 properties, target/page-size facts, and the absence of an
  official `PT_SCE_RELRO` definition.

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
- Orbis binutils is the only instruction-decoding authority. LLVM `llvm-readobj` is an opt-in
  generic structural cross-check and LLVM `llvm-objdump` is an opt-in target-aware structural
  comparison using `x86_64-scei-ps4`; the in-repository SCE reader is the relocation authority for
  `PT_SCE_DYNLIBDATA` metadata. `llvm-tli-checker` is not part of ELF extraction.
- Conventional Orbis relocation output may be empty while SCE relocation tables are present. The
  current observed counts are 172,404 `DT_SCE_RELA` entries and 539 `DT_SCE_JMPREL` entries; the
  complete table belongs in the source-bound JSONL cache and only method-relevant rows belong in
  the implementation report.
- The SCE reader does not apply runtime relocation bases, resolve NIDs through an assumed database,
  infer ABI/register clobbers, or synthesize `extern` declarations. Optimized/inlined line mappings,
  host GNU/Clang acceptance of the Orbis dialect, and semantic equivalence remain open.
- `ps4_module_loader` and GhidraOrbis are research references only; neither is vendored or a runtime
  dependency. Their layouts must be revalidated against the target ELF and tool version.
- The accepted LLVM triple does not establish Sony ABI, relocation application, or semantic
  correctness. Host GNU/Clang acceptance of the recovered Orbis dialect and a future PS4 compiler
  validation environment remain open.
