# Tasks: ABI-Oriented Header Foundation

**Input**: Design documents from `specs/001-header-foundation/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/`, and `quickstart.md`

**Implementation status**: Baseline and artifact-index tasks marked complete were
implemented before task generation and validated with focused tests.

## Backlog reconciliation (2026-08-16)

The 31 unchecked tasks are intentionally retained as open evidence or implementation work. They
are no longer independent duplicate owners:

| Open group | Canonical boundary | Reconciliation |
| --- | --- | --- |
| T016--T022 | Header policy and deterministic rendering | T016 owns duplicate-definition policy; T017 owns qualified identity; T018 owns type-chain policy; T019--T022 cover rendering, traversal, closure, and regression evidence. T048--T051 are the corresponding completeness, identity migration, aggregate-publication, and renderer-coverage follow-ups, not alternate policy implementations. |
| T023 and T052 | Truthful MSVC evidence | T052 is the single reporting implementation: per-unit exit codes, compiler metadata, captured diagnostics, object status, warning classification, and separate aggregate status. T023 remains the MSVC-specific acceptance fixture and consumes that report. |
| T026--T028 | Cache lifecycle and measurement | Fresh-process reuse, warm-cache reuse, stale/corrupt repair, and cold/warm measurements remain separate acceptance evidence; passing unit tests alone does not close them. |
| T029--T032 | Header/assembly evidence contract | This contract owns method ownership, ranges, layout hypotheses, and evidence-linked disagreements without changing headers. |
| T047 and T053 | IDA availability | T047 owns the availability vocabulary and report facts; T053 integrates that record into export consumers. IDA remains post-generation evidence only. |
| T073--T085 | Implementation validator | These tasks own the source-bound Doris validator and its relocation/NID/ABI/CFI/effect/compiler dimensions; they must not introduce a second header/IDA validation adapter. |
| T033--T040 | Convergence and retention | Documentation, contributor instructions, transient cleanup, retention classification, legacy review, and final evidence remain open until their named artifacts are synchronized. |
| T086--T088 | PS4 gate closure | Instruction effects, bounded Orbis tool acceptance, and static parity are sequential gates. Unknown, conflicting, unavailable, or live-unobserved evidence remains non-promotable. |

The current real-asset record and the serving/validator record are the authority for observed
counts. Historical output is retained and is not deleted or silently reclassified by this task
normalization.

### Gate-convergence disposition (2026-08-16)

- T052 has one canonical checkout-local implementation in `tools/sonar/validate_header_bundle.py`:
  it reports per-unit exit/object/stdout/stderr/compiler metadata and a separate aggregate result.
  Its focused tests pass, but the task remains unchecked until a fresh external MSVC run produces
  the current schema-2 report; the historical 2,760-unit acceptance is not rewritten.
- T086 now has focused coverage for mnemonic aliases, width normalization, conditional joins,
  return-immediate cleanup, callee-saved preservation, and CFI gaps. The task remains unchecked
  pending representative source-bound acceptance; unknown or conflicting paths remain partial or
  failed.
- T087 was attempted on the bounded 1,037-method `rLayout` report after the T086 slice. Doris
  context was complete, but ABI was partial for all methods, so method-specific assembler/object
  acceptance was `not_observed`; the external report and exact SDK identity are recorded in the
  dated acceptance and measured-evidence records. The gate is not complete.
- T088 now requires the normalized byte/CFG/external-edge/effect fields plus relocation, NID, and
  ABI/CFI dimensions before parity can be observed. The bounded report remains failed/partial and
  no `target-object-equivalent` result is promoted. Live PS4 behavior remains `not_observed`.

## Phase 1: Setup

- [x] T001 Initialize Spec Kit 0.15.1 in `.specify/` with Copilot skills under `.github/skills/`.
- [x] T002 Replace the placeholder constitution in `.specify/memory/constitution.md` with project evidence and artifact principles.
- [x] T003 Create `specs/001-header-foundation/spec.md` and `specs/001-header-foundation/checklists/requirements.md`.
- [x] T004 Create `specs/001-header-foundation/research.md`, `data-model.md`, `quickstart.md`, and `contracts/cli-and-artifacts.md`.

## Phase 2: Foundational Baseline

**Purpose**: Make the existing executable path and durable index contract coherent
before changing the evidence model or renderer.

- [x] T005 Repair the `LazyTypeResolver` imports and context-manager signature in `src/ddon_dwarf_reconstructor/application/generators/dwarf_generator.py`.
- [x] T006 Implement explicit, environment, and sibling dump discovery in `src/ddon_dwarf_reconstructor/application/generators/dwarf_generator.py`.
- [x] T007 Bind `LazyDwarfIndexService` to the ELF source path in `src/ddon_dwarf_reconstructor/application/generators/dwarf_generator.py`.
- [x] T008 Replace whole-dump buffering with the streaming SQLite sidecar contract in `src/ddon_dwarf_reconstructor/infrastructure/zstd_dump_parser.py`.
- [x] T009 Reconcile inspect, repair, rebuild, and exact-confirmation purge operations in `src/ddon_dwarf_reconstructor/artifact_cli.py`.
- [x] T010 [P] Add same-path source replacement coverage to `tests/domain/services/test_lazy_dwarf_index_service.py` and `tests/infrastructure/test_artifacts.py`.
- [x] T011 Remove the competing `pytest.ini` and align the active test configuration with `pyproject.toml`; local/CI quality parity remains a follow-up.

**Checkpoint**: Generator and artifact-index focused tests pass. Existing full-suite
and static-quality failures remain visible and are not hidden by configuration.

## Phase 3: User Story 1 - Generate a compilable ABI header (Priority: P1)

**Goal**: Generate deterministic, evidence-preserving declarations for a selected
class and its layout closure.

**Independent Test**: Parse synthetic and selected real DIE fixtures, generate a
header, compile it with the selected host compiler, and compare layout/provenance
assertions with the source evidence.

- [x] T012 [P] [US1] Extend `ClassInfo` in `src/ddon_dwarf_reconstructor/domain/models/dwarf/class_info.py` with qualified identity, aggregate kind, completeness, and diagnostics.
- [x] T013 [P] [US1] Extend `MemberInfo` in `src/ddon_dwarf_reconstructor/domain/models/dwarf/member_info.py` with access, qualifiers, bitfield width/offset, and raw location evidence.
- [x] T014 [P] [US1] Extend `MethodInfo` and parameter models in `src/ddon_dwarf_reconstructor/domain/models/dwarf/method_info.py` and `parameter_info.py` with access, cv/ref/noexcept, virtuality, and declaration-state evidence.
- [x] T015 [US1] Parse the new evidence fields in `src/ddon_dwarf_reconstructor/domain/services/parsing/class_parser.py` and add focused fixtures under `tests/domain/services/parsing/`.
- [ ] T016 [US1] Centralize deterministic duplicate-definition selection across `src/ddon_dwarf_reconstructor/domain/services/definition_selection.py`, `class_parser.py`, `lazy_dwarf_index_service.py`, and `zstd_dump_parser.py`.
- [ ] T017 [US1] Replace name-only dependency keys with qualified/scope-safe identities in `src/ddon_dwarf_reconstructor/domain/services/generation/hierarchy_builder.py` and `dependency_extractor.py`.
- [ ] T018 [US1] Implement structured type-chain rendering for arrays, qualifiers, function pointers, pointer-to-member types, and unresolved references in `src/ddon_dwarf_reconstructor/domain/services/parsing/type_resolver.py` and `src/ddon_dwarf_reconstructor/domain/services/generation/header_generator.py`.
- [ ] T019 [US1] Render aggregate kinds, access sections, inheritance attributes, templates, and deterministic declarations in `src/ddon_dwarf_reconstructor/domain/services/generation/header_generator.py` (aggregate/access/qualifier subset implemented; templates remain).
- [ ] T020 [US1] Make dependency traversal stable and layout-aware in `src/ddon_dwarf_reconstructor/domain/services/generation/hierarchy_builder.py` and add ordering tests in `tests/domain/services/generation/test_hierarchy_builder.py`.
- [ ] T021 [US1] Repair include closure, basename collision handling, and per-file rendering in `src/ddon_dwarf_reconstructor/application/generators/dwarf_generator.py`, `file_registry.py`, and `header_generator.py`.
- [ ] T022 [US1] Add synthetic evidence and header regression cases for namespaces, unions/enums, access, bitfields, templates, arrays, function pointers, and duplicate definitions under `tests/application/generators/`, `tests/domain/services/parsing/`, and `tests/domain/services/generation/`.
- [ ] T023 [US1] Add the MSVC x64 C++23 acceptance fixture under `tests/application/generators/`, using `VsDevCmd.bat -arch=x64` and consuming the canonical truthful report from T052; do not create a second compiler-reporting path.

**Checkpoint**: User Story 1 generates deterministic headers with explicit evidence
and diagnostics. The five representative standalone probes compile under the
selected compiler; aggregate-bundle acceptance remains blocked until shared
declarations, multi-file closure, and truthful reporting are implemented.

## Phase 4: User Story 2 - Reuse validated evidence deterministically (Priority: P2)

**Goal**: Make header and symbol artifacts safely reusable across fresh processes and
source relocations without stale output.

**Independent Test**: Generate a bundle twice in fresh processes, compare bytes, then
replace the input at the same path and verify invalidation and atomic replacement.

- [x] T024 [P] [US2] Bind durable symbol/cache artifacts to source identity in `src/ddon_dwarf_reconstructor/infrastructure/artifacts.py`, `src/ddon_dwarf_reconstructor/domain/repositories/cache/`, and the lazy-index source port.
- [x] T025 [US2] Route generated headers through atomic publication and manifest validation in `src/ddon_dwarf_reconstructor/main.py` and `src/ddon_dwarf_reconstructor/infrastructure/header_output.py`.
- [ ] T026 [US2] Add deterministic fresh-process and warm-cache tests in `tests/domain/repositories/cache/`, `tests/infrastructure/test_artifacts.py`, and `tests/application/generators/`.
- [ ] T027 [US2] Add artifact status and repair regression tests for corrupt, stale, migrated, and valid indexes in `tests/test_artifact_cli.py` and `tests/infrastructure/test_zstd_dump_parser.py`.
- [ ] T028 [US2] Benchmark cold index construction, warm lookup, negative lookup, and batch closure in `tests/performance/` without deleting durable artifacts; use the reusable runner/history contract in [`specs/016-performance-profiling`](../016-performance-profiling/spec.md) once the explicit cold-index evidence is retained.

**Checkpoint**: Repeated valid runs are byte-identical, source replacement rejects
stale artifacts, and repair/purge remain explicit and targeted.

## Phase 5: User Story 3 - Validate declarations with assembly evidence (Priority: P3)

**Goal**: Join Orbis evidence to recovered declarations as an independent validation
stream without silently synthesizing source.

**Independent Test**: Run validation on matching and intentionally conflicting
assembly/DWARF fixtures and inspect deterministic diagnostics.

- [ ] T029 [P] [US3] Define the canonical header/assembly evidence contract in `specs/001-header-foundation/contracts/assembly-validation.md` for method ownership, ranges, vtable signals, member-offset hypotheses, unavailable evidence, and conflicts.
- [ ] T030 [US3] Implement the bounded assembly/header validation service beside `src/ddon_dwarf_reconstructor/infrastructure/orbis_objdump.py` and `src/ddon_dwarf_reconstructor/application/exporters/`; it must consume the canonical contract and never synthesize declarations.
- [ ] T031 [US3] Emit stable evidence-linked disagreements in `src/ddon_dwarf_reconstructor/application/exporters/knowledge_exporter.py` without modifying declarations from assembly alone or duplicating the T073--T085 implementation-validator dimensions.
- [ ] T032 [US3] Add matching, conflicting, unavailable, and partial fixture tests in `tests/infrastructure/test_orbis_objdump.py` and `tests/application/exporters/`.

**Checkpoint**: Assembly validation reports every seeded disagreement with both
contributing evidence identifiers and leaves the header facts traceable.

## Phase 6: Polish and Cross-Cutting Concerns

- [ ] T033 [P] Reconcile stale CLI, timeout, test-count, and workflow claims in `README.md`, the
  architecture and runtime-flow explanations, the testing reference, the site index, and
  `tests/README.md`.
- [ ] T034 [P] Reduce duplicated policy in `CLAUDE.md` and `.github/copilot-instructions.md` so `AGENTS.md` remains canonical and remove unavailable-tool references.
- [ ] T035 Replace destructive `clean-all` behavior with transient-only cleanup in `justfile` and retain explicit artifact maintenance recipes.
- [x] T036 Extend `.gitignore` for root caches, SQLite journals/temporary sidecars, Nuitka outputs, and runtime logs without hiding curated fixtures.
- [ ] T037 Create a canonical artifact retention manifest for `output/` and classify duplicate snapshots before deleting any historical evidence.
- [ ] T038 Review `count_cus.py`, `test_declarations.py`, PEP 735 dependency groups, generated headers, and repeated `output/t045-*` through `output/t072-*` bundles before removal or archival.
- [x] T039 Verify Visual Studio Community 2026 x64 MSVC `19.51.36252.0` with `vswhere.exe`, record its C++23/ABI limitations, and prepare the sample verification bundle in `output/msvc-header-validation-20260801/`.
- [ ] T040 Run `uv run just test-unit`, `uv run just check`, focused integration tests, and explicit real-asset checks; record remaining gaps in `/speckit-converge` output.

## Phase 7: Verification Adaptation

- [x] T041 [US1] Decode simple PS4 `DW_OP_constu` vtable locations in `src/ddon_dwarf_reconstructor/domain/services/parsing/class_parser_methods.py` and cover them under `tests/domain/services/parsing/`.
- [x] T042 [US1] Generate and compile `rTextureMemory`, `rTexture`, and `rTutorialDialogMessage` with the MSVC wrapper in `output/msvc-header-validation-20260801/`, then classify every compiler diagnostic.
- [x] T043 [US3] Generate `cSetInfoOmBreakTarget` and `rLayout` from the warm source-bound index and compare recoverable facts against `resources/sample-ida-dump-cSetInfoOmBreakTarget.h` and `resources/sample-ida-dump-rLayout.h`.
- [x] T044 [US3] Record the sample generation, compilation, IDA comparison, and vtable-slot results in `specs/001-header-foundation/` without committing runtime outputs.
- [x] T045 [US1] Preserve containing-type scope and nested class definitions in `src/ddon_dwarf_reconstructor/domain/models/dwarf/` and `class_parser.py`, then render legal nested template arguments for `rTutorialDialogMessage`.
- [x] T046 [US1] Build complete base and by-value dependency closure for standalone headers in `hierarchy_builder.py`, `dependency_extractor.py`, and `header_generator.py`; add regression coverage for `rTexture`, `cSetInfoOmBreakTarget`, and `rLayout` compilation.
- [ ] T047 [US3] Add an evidence-availability record to the IDA comparison report distinguishing pseudo-header declarations from unavailable method-body pseudocode and control-flow evidence. The generated-header follow-up now provides a separate source-bound implementation/assembly report, but IDA comparison publication remains open.
- [x] T054 [US3] Add the post-header implementation discovery chain with method DIE/CU identity, all specification/abstract-origin candidates, validated code ranges, explicit evidence states, and optional Orbis instruction extraction. Preserve the canonical header bundle and publish reports atomically under a separate implementation directory.
- [x] T055 [US3] Move implementation discovery behind the committed header publication barrier in `src/ddon_dwarf_reconstructor/main.py` and preserve header bytes when the follow-up fails or times out.
- [x] T056 [US3] Add `--emit-implementation-sources` and the source-bound per-method publisher in `src/ddon_dwarf_reconstructor/cli.py` and `src/ddon_dwarf_reconstructor/infrastructure/implementation_output.py`; reject emission without `--extract-assembly`.
- [x] T057 [US3] Extend `OrbisReference`, `OrbisToolInvocation`, instruction provenance, independent profile caches, and schema-2.4/parser-v6 report serialization in `src/ddon_dwarf_reconstructor/domain/models/disassembly.py`, `src/ddon_dwarf_reconstructor/infrastructure/orbis_objdump.py`, and `orbis_objdump_parsing.py`.
- [x] T058 [US3] Centralize definition-signature rendering and emit guarded GNU/Clang `.cpp` scaffolds only for unique matched methods; preserve all raw evidence and ineligible candidates in the canonical index.
- [x] T059 [US3] Add barrier, profile, parser, signature, source-eligibility, deterministic-ID, atomic-publication, and header non-regression tests under `tests/`.
- [x] T060 [US3] Run the complete source-bound `rLayout` acceptance with the durable analytical store, Doris SQL port, and Orbis SDK; retain flags, cold/warm state, output hashes, method counts, unavailable profiles, and remaining uncertainty outside source control. See `acceptance-rLayout-assembly-20260815.md`; the collected result is explicitly partial because the matched Orbis profile set is incomplete.
- [x] T061 [US3] Consolidate implementation evidence serialization into schema `3.2`: instruction-owned references, one exact method-range text field, SCE relocation projection, generic artifact descriptors, structured limitations, and compact target-aware LLVM comparison metadata. The superseded `canonical-cpp` value is retained only in historical acceptance notes.
- [x] T062 [US3] Replace redundant disassembly, reference, and notes emission with a minimal atomic source-bundle manifest; the later canonical-assembly correction supersedes the historical `.cpp` scaffold view and retires stale bundles on successful publication.
- [x] T063 [US3] Add regression coverage for canonical evidence parity, compact scaffold rendering/escaping, minimal manifest integrity, stale-bundle retirement, duplicate IDs, and rollback preservation.
- [x] T064 [US3] Re-run the real `rLayout` acceptance with the canonical profile and record the new report/manifest hashes, output counts, unchanged header hash, and remaining Orbis/compiler uncertainty.
- [x] T065 [US3] Split standard and dynamic Orbis relocation invocations, add the bounded SCE dynamic-tag/RELA reader and source/tool/parser-bound JSONL cache, and cover table geometry, signed addends, unknown codes, truncation, and stable IDs.
- [x] T066 [US3] Add the opt-in LLVM `llvm-readobj` JSON structural cross-check, preserve unknown numeric SCE tags, and retain exact command/output metadata without changing Orbis instruction authority.
- [x] T067 [US3] Update the CLI, architecture, external-tool evidence, data-model, contract, research, and acceptance documentation for the dual-authority relocation boundary.
- [x] T068 [US3] Refresh the full real `rLayout` publisher acceptance under report schema `3.2`, recording SCE counts, LLVM hashes/diagnostics, all split profile statuses, and unchanged header/source hashes through the explicitly mapped Doris SQL port; see `acceptance-rLayout-assembly-20260815.md`.
- [x] T069 [US3] Reproduce the useful SDK6500/n267 Orbis definitions in typed source-provenance-bound form, including SCE tags, target facts, page sizes, relocation 40, and the absence of official `PT_SCE_RELRO`.
- [x] T070 [US3] Add opt-in LLVM `llvm-objdump` capability probing and independently cached `x86_64-scei-ps4` method-range slices with additive report comparison summaries; keep `llvm-readobj` generic and exclude `llvm-tli-checker` from ELF extraction.
- [x] T071 [US3] Add target/profile/cache/report regression tests for exact triple flags, partial/unavailable slices, SDK constants, source identity hashes, header-first behavior, byte parity, and no synthesized declarations.
- [x] T072 [US3] Update CLI, README, architecture, external-tool, PS4 knowledge-base, feature contracts, research, plan, data model, and acceptance documentation for the target-aware LLVM boundary and SDK definition provenance.
- [x] T073 [US3] Add schema-4.0 source-bound implementation-validation models and the read-only
  `artifacts validate-implementation` workflow with explicit original-address/load-base policy,
  source/report/store identity binding, and atomic external publication.
- [x] T074 [US3] Add PT_LOAD image mapping, pure standard/SCE relocation evaluation, overflow and
  target-byte checks, opaque NID/module-library evidence, and explicit source-bound NID database
  resolution without importing loader mutation or SDK-incomplete names.
- [x] T075 [US3] Extend analytical-store location/CFI queries and method context packets for
  object pointers, artificial/hidden parameters, parameter locations, frame base, and CFI;
  add conservative register/flags/memory/call/stack-effect analysis with fail-closed statuses.
- [x] T076 [US3] Keep C++ translation out of the core generator and emit canonical exact-byte
  `.s`/`.o` artifacts through Orbis assembler acceptance; retain bounded `.raw.asm` evidence and
  per-method `implementation-context/1.0` packets; retain Orbis clang probe and readelf
  target-object metadata as separate validation evidence.
- [x] T077 [US3] Add relocation, NID, ABI/CFI, safety, compiler/object, context-packet, and
  non-promotion regression fixtures; document GhidraOrbis, SocraticBliss, and SDK 8.0 concepts,
  commits, paths, licenses, and authority boundaries.
- [x] T077a [US3] Define the Doris-backed implementation evidence model over typed DIE, attribute,
  reference, range, location, and frame families; prohibit direct Parquet/JSONL reads in the
  validator and push CFI overlap predicates into Doris.
- [x] T078 [US3] Run the complete source-bound `02020005` validator from the complete analytical
  store, publish per-dimension counts and retained external artifacts, and keep live behavioral
  equivalence `not_observed`/`blocked` unless a PS4 execution environment is supplied. The
  bounded `rLayout` pilot and the 1,150-method Season 2 run now publish atomic failed reports
  after the batching implementation; ABI, compiler, parity, and live behavior remain independent
  non-promoted dimensions.
- [x] T079 [US3] Capability-filter the SDK-invalid `-t -T` and `-R` profiles, remove redundant
  source-intermixed/debug/full-DWARF profile execution from normal generation, remove arbitrary
  default objdump timeouts, and regenerate the real `rLayout` bundle with 26 canonical `.s`/`.o`
  pairs and zero generated `.cpp` placeholders.
- [x] T080 [US3] Publish clean per-method assembly bundles with schema-`4.2` reports, schema-`3.1`
  manifests, bounded `.raw.asm` evidence, canonical `.s` compiler inputs, accepted `.o` objects,
  and deterministic `implementation-context/1.0` packets. Keep Doris as the runtime analytical
  read path and thin timeout/profile diagnostics.
- [x] T081 [US3] Re-run the real `rLayout` generation against the complete Doris publication and
  record `.raw.asm`/`.s`/`.o`/`.context.json` counts, hashes, and tool acceptance in the acceptance
  record; do not promote static parity or live behavior from artifact presence alone. The same
  clean-bundle and non-promotion checks were then rerun for all 289 Season 2 roots in
  `acceptance-season2-assembly-20260816.md`.
- [x] T082 [US3] Replace per-method Doris context hydration and full relocation/NID tuple rescans
  in the implementation validator with bounded Doris method-context batches and reusable
  address/relocation-ID indexes. Add deterministic query, source-binding, context-view, and
  non-regression coverage in `tests/infrastructure/analytical/` and
  `tests/infrastructure/test_implementation_indexes.py`.
- [x] T083 [US3] Run the retained `rLayout` pilot, then the complete 1,150-method Season 2 static
  validator after the pilot published atomically. Compare bounded batch counts and independent evidence
  statuses with the retained baseline; the pilot completed in approximately 28.6 seconds and the
  full run in approximately 85.8 seconds without an arbitrary timeout. Retain only the atomic
  reports and structured evidence needed for follow-up.
- [x] T084 [US3] Preserve decoded Doris location expressions and the recovered ABI-facts map in
  validation context packets; add regressions proving frame-base/parameter cues are not reduced to
  `null` and that the source-bound packet remains deterministic.
- [x] T085 [US3] Remove per-tool stdout/stderr files from implementation validation, expose any
  compiler/linker timeout as an explicit caller policy, and retain only concise status, tool,
  configured-limit, timing, and output-hash evidence. The default has no tool timeout, and
  documented-invalid SDK profiles are not re-run.
- [ ] T086 [US3] Close common x86-64 instruction-effect gaps (mnemonic aliases, conditional paths,
  return-immediate stack cleanup, and CFI boundary joins) without promoting unknown or conflicting
  evidence.
- [ ] T087 [US3] Run bounded representative Orbis clang/as/readelf/objdump acceptance after ABI and
  effect closure, capture reproducible tool/object metadata, and expand only after the bounded gate
  is complete.
- [ ] T088 [US3] Close static parity over normalized bytes, CFG/branches, calls/external edges,
  NIDs, ABI/CFI/effects, and accepted target objects; keep live behavioral equivalence separate.
- [ ] T048 [US1] Propagate complete, declaration-only, partial, unresolved, and conflicting completeness through the current parser and generation services; block declaration-only bases and by-value dependencies with deterministic diagnostics. Add unit coverage in `tests/domain/services/parsing/` and `tests/domain/services/generation/`.
- [ ] T049 [US1] Replace name-only dependency and registry identity with qualified, containing-scope-safe keys in `src/ddon_dwarf_reconstructor/domain/models/dwarf/` and the generation services; preserve nested names such as `cOmControl::InputLot`. Add parser and renderer regressions under `tests/domain/services/`.
- [ ] T050 [US1] Close aggregate and multi-file dependency publication in `src/ddon_dwarf_reconstructor/application/generators/` and the generation services: deduplicate shared framework declarations, include cross-file base/by-value dependencies, and make same-basename filenames collision-safe. Add an aggregate translation-unit regression under `tests/application/generators/` and update file-registry/generator tests.
- [ ] T051 [US1] Render structured declarators and templates from type-chain evidence in `src/ddon_dwarf_reconstructor/domain/services/parsing/type_resolver.py` and the generation services, covering qualifiers, arrays, function pointers, pointer-to-member forms, multi-parameter and non-type templates, and unresolved bounds/references. Add focused cases under `tests/domain/services/parsing/` and `tests/domain/services/generation/`.
- [ ] T052 [US1] Make MSVC validation truthful in the checkout-local `tools/sonar/` reporting layer with tests under `tests/tools/`: propagate every per-translation-unit exit code, compile and report `compile_tutorial.cpp`, capture bounded stdout/stderr diagnostics, record compiler path/version/flags and object status, report aggregate status separately from standalone status, and classify C4201 explicitly. Treat `output/msvc-header-validation-20260801/compile_stubs.cmd` and its current files as read-only evidence; do not edit generated output.
- [ ] T053 [US3] Integrate the canonical IDA evidence-availability record into the comparison report in `src/ddon_dwarf_reconstructor/application/exporters/knowledge_exporter.py` and `tests/application/exporters/`, covering pseudo-header declarations, layout/assembly facts, calling conventions, vtable slots, IDA-only methods, and unavailable method-body pseudocode; distinguish unavailable evidence from a mismatch.

## Dependencies and Execution Order

### Phase Dependencies

- Setup is complete.
- Foundational tasks T010 and T011 are complete. T045 and T046 are complete only
  for their delivered nested-scope and standalone structural-closure fixes; they do
  not establish aggregate-bundle acceptance. T047 remains open, and T048-T052 are
  required to close the remaining User Story 1 acceptance gaps.
- User Story 1 must complete before User Story 2 because cache identity depends on
  the final structured header model and renderer configuration. T048 and T049 can
  proceed after the current model/parser work; T050 and T051 depend on those identity
  and type-chain contracts; T052 is required for the MSVC acceptance checkpoint.
- User Story 3 depends on the evidence identifiers and diagnostics established by
  User Story 1. T047 and T053 own IDA evidence availability and can proceed in
  parallel with T048-T052 once the comparison artifact shape is fixed. T082 was the
  implementation prerequisite for the now-observed full validator evidence in T078/T083.
- Polish tasks depend on the affected story contracts and implementation.

### Parallel Opportunities

- T012, T013, and T014 can proceed in parallel because they own separate model files.
- T024 and T029 can proceed in parallel after the corresponding foundational contracts.
- T048, T049, and T053 can proceed in parallel after the evidence and model contracts;
  T050, T051, and T052 consume their results and should be validated independently.
- Documentation cleanup T033/T034 and ignore/cleanup policy T035/T036 can proceed in
  parallel with implementation once their current behavior is known.

## MVP Strategy

The MVP is User Story 1 after foundational tasks T010 and T011: a trustworthy,
deterministic, evidence-preserving standalone header path with explicit completeness
diagnostics. T045 and T046 deliver nested-scope and standalone structural closure;
T048-T052 are required before aggregate compilation can be called complete. User
Story 2 then hardens repeatability and artifact lifecycle. User Story 3 adds assembly
and IDA evidence availability without expanding the first feature into method-body
reconstruction.

## Notes

Every task names an exact path and a validation target. Real ELF, compressed dumps,
proprietary tools, generated headers, logs, and caches remain local and are never
added to feature artifacts or source control.
