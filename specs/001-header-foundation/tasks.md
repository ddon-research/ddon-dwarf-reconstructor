# Tasks: ABI-Oriented Header Foundation

**Input**: Design documents from `specs/001-header-foundation/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/`, and `quickstart.md`

**Implementation status**: Baseline and artifact-index tasks marked complete were
implemented before task generation and validated with focused tests.

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
- [ ] T023 [US1] Add MSVC x64 C++23 header checks under `tests/application/generators/`, using `VsDevCmd.bat -arch=x64` and recording missing DDON closure types separately from syntax failures.

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
- [ ] T028 [US2] Benchmark cold index construction, warm lookup, negative lookup, and batch closure in `tests/performance/` without deleting durable artifacts.

**Checkpoint**: Repeated valid runs are byte-identical, source replacement rejects
stale artifacts, and repair/purge remain explicit and targeted.

## Phase 5: User Story 3 - Validate declarations with assembly evidence (Priority: P3)

**Goal**: Join Orbis evidence to recovered declarations as an independent validation
stream without silently synthesizing source.

**Independent Test**: Run validation on matching and intentionally conflicting
assembly/DWARF fixtures and inspect deterministic diagnostics.

- [ ] T029 [P] [US3] Define a validation contract in `specs/001-header-foundation/contracts/assembly-validation.md` for method ownership, ranges, vtable signals, and member-offset hypotheses.
- [ ] T030 [US3] Implement an assembly/header validation service beside `src/ddon_dwarf_reconstructor/infrastructure/orbis_objdump.py` and `src/ddon_dwarf_reconstructor/application/exporters/`.
- [ ] T031 [US3] Emit stable evidence-linked disagreements in `src/ddon_dwarf_reconstructor/application/exporters/knowledge_exporter.py` without modifying declarations from assembly alone.
- [ ] T032 [US3] Add matching/conflicting fixture tests in `tests/infrastructure/test_orbis_objdump.py` and `tests/application/exporters/`.

**Checkpoint**: Assembly validation reports every seeded disagreement with both
contributing evidence identifiers and leaves the header facts traceable.

## Phase 6: Polish and Cross-Cutting Concerns

- [ ] T033 [P] Reconcile stale CLI, timeout, test-count, and workflow claims in `README.md`, the
  architecture and runtime-flow explanations, the testing reference, the site index, and
  `tests/README.md`.
- [ ] T034 [P] Reduce duplicated policy in `CLAUDE.md` and `.github/copilot-instructions.md` so `AGENTS.md` remains canonical and remove unavailable-tool references.
- [ ] T035 Replace destructive `clean-all` behavior with transient-only cleanup in `justfile` and retain explicit artifact maintenance recipes.
- [ ] T036 Extend `.gitignore` for root caches, SQLite journals/temporary sidecars, Nuitka outputs, and runtime logs without hiding curated fixtures.
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
- [ ] T047 [US3] Add an evidence-availability record to the IDA comparison report distinguishing pseudo-header declarations from unavailable method-body pseudocode and control-flow evidence.
- [ ] T048 [US1] Propagate complete, declaration-only, partial, unresolved, and conflicting completeness through the current parser and generation services; block declaration-only bases and by-value dependencies with deterministic diagnostics. Add unit coverage in `tests/domain/services/parsing/` and `tests/domain/services/generation/`.
- [ ] T049 [US1] Replace name-only dependency and registry identity with qualified, containing-scope-safe keys in `src/ddon_dwarf_reconstructor/domain/models/dwarf/` and the generation services; preserve nested names such as `cOmControl::InputLot`. Add parser and renderer regressions under `tests/domain/services/`.
- [ ] T050 [US1] Close aggregate and multi-file dependency publication in `src/ddon_dwarf_reconstructor/application/generators/` and the generation services: deduplicate shared framework declarations, include cross-file base/by-value dependencies, and make same-basename filenames collision-safe. Add an aggregate translation-unit regression under `tests/application/generators/` and update file-registry/generator tests.
- [ ] T051 [US1] Render structured declarators and templates from type-chain evidence in `src/ddon_dwarf_reconstructor/domain/services/parsing/type_resolver.py` and the generation services, covering qualifiers, arrays, function pointers, pointer-to-member forms, multi-parameter and non-type templates, and unresolved bounds/references. Add focused cases under `tests/domain/services/parsing/` and `tests/domain/services/generation/`.
- [ ] T052 [US1] Make MSVC validation truthful in the checkout-local `tools/sonar/` reporting layer with tests under `tests/tools/`: propagate every per-translation-unit exit code, compile and report `compile_tutorial.cpp`, capture stdout/stderr, record compiler/version/flags/object status, report aggregate status separately, and classify C4201 explicitly. Treat `output/msvc-header-validation-20260801/compile_stubs.cmd` and its current files as read-only evidence; do not edit generated output.
- [ ] T053 [US3] Extend the IDA comparison report in `src/ddon_dwarf_reconstructor/application/exporters/knowledge_exporter.py` and `tests/application/exporters/` with evidence-availability metadata for pseudo-header declarations, layout/assembly facts, calling conventions, vtable slots, IDA-only methods, and unavailable method-body pseudocode; distinguish unavailable evidence from a mismatch.

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
  parallel with T048-T052 once the comparison artifact shape is fixed.
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
