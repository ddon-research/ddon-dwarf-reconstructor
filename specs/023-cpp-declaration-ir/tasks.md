# Tasks: Incremental declaration IR and compiler validation

These are future tasks for [the specification](spec.md). Implementation starts after Feature 022
repair or a documented blocker handoff. Paths are repository-relative; proposed files are marked
new. A code slice runs focused tests plus `test-unit`, `check`, and `test`; final handoff also
requires `coverage-ci` and `audit`. No task is completed by this planning package.

## Setup and Research Gate

- [ ] T001 Reconcile Feature 022's baseline/handoff in `specs/023-cpp-declaration-ir/measured-evidence.md` and execute `research-prompt.md`; dependencies: Feature 022 T020 or its T019 evidence-backed handoff; tier: research/source/fixture evidence; done: common compiler cases, version/license/resource results and a subprocess-versus-native decision are retained without claiming a repaired corpus prematurely.
- [ ] T002 Define the supported compiler/profile/normalized-schema surface in `specs/023-cpp-declaration-ir/contracts/compiler-validation.md` and `research.md`; dependencies: T001; tier: reproducible toolchain canary; test surface: proposed `tests/infrastructure/compiler/test_clang_validation.py`; done: exact executable identity, flags, target, omissions and limits are known before dependency promotion.

## US1: One Declaration Model (P1)

- [ ] T003 [US1] Add immutable identity/observation/declaration contracts in new `src/ddon_dwarf_reconstructor/domain/models/cpp/declarations.py` and package initializer; tests: new `tests/domain/models/cpp/test_declarations.py`; dependencies: T001; tier: unit/property; cover source/CU/DIE zero, multiple observations, unknown/conflicting facts, and qualified template identity.
- [ ] T004 [US1] Add new `src/ddon_dwarf_reconstructor/domain/services/generation/declaration_lowering.py`, adapting existing `src/ddon_dwarf_reconstructor/domain/models/dwarf/type_reference.py`, `src/ddon_dwarf_reconstructor/domain/models/dwarf/type_scope.py`, and `src/ddon_dwarf_reconstructor/domain/models/dwarf/enum_info.py`; tests: new `tests/domain/services/generation/test_declaration_lowering.py`; dependencies: T003; tier: unit/integration; done: aliases/enums preserve full provenance and compiler-synthesized facts cannot overwrite DWARF evidence.
- [ ] T005 [US1] Migrate alias/enum consumers in `src/ddon_dwarf_reconstructor/domain/services/generation/alias_rendering.py` and `src/ddon_dwarf_reconstructor/domain/services/generation/header_aggregate_rendering.py`; tests: `tests/domain/services/generation/test_alias_rendering.py`, `tests/domain/services/generation/test_header_aggregate_rendering.py`, and new `tests/domain/services/generation/test_declaration_lowering.py`; dependencies: T004; tier: unit/compiler/parity; done: unaffected bytes match Feature 022, intentional differences have evidence, and superseded alias/enum semantic string policies and callers are removed.
- [ ] T006 [US1] Migrate template/method/declarator authority in `src/ddon_dwarf_reconstructor/domain/services/generation/template_families.py`, `src/ddon_dwarf_reconstructor/domain/services/generation/template_declarations.py`, `src/ddon_dwarf_reconstructor/domain/services/generation/method_signature_policy.py`, `src/ddon_dwarf_reconstructor/domain/services/generation/header_member_rendering.py`, and `src/ddon_dwarf_reconstructor/domain/services/generation/header_method_rendering.py`; tests: `tests/domain/services/generation/test_template_families.py`, `tests/domain/services/generation/test_typed_declaration_rendering.py`, and new `tests/domain/services/generation/test_declaration_lowering.py`; dependencies: T005; tier: unit/property/compiler; done: exact family identity, primary parameters and method compatibility come from typed declarations with no duplicate legacy inference.
- [ ] T007 [US1] Add requirements/emission contracts in new `src/ddon_dwarf_reconstructor/domain/models/cpp/emission.py` and scheduling in new `src/ddon_dwarf_reconstructor/domain/services/generation/declaration_scheduling.py`; tests: new `tests/domain/services/generation/test_declaration_scheduling.py`; dependencies: T006; tier: unit/property; done: reasoned availability/completeness edges and legal owner order reuse existing graph machinery, while impossible schedules return cycle witnesses.
- [ ] T008 [US1] Integrate the plan and ledger through `src/ddon_dwarf_reconstructor/application/generators/symbol_header_layout.py`, `src/ddon_dwarf_reconstructor/application/generators/symbol_header_validation.py`, and `src/ddon_dwarf_reconstructor/infrastructure/symbol_output.py`; remove superseded semantic planning from `src/ddon_dwarf_reconstructor/domain/services/generation/header_dependency_plan.py` and `src/ddon_dwarf_reconstructor/domain/services/generation/header_ordering.py`; tests: `tests/application/generators/test_dwarf_generator_multi_file.py`, `tests/infrastructure/test_symbol_output.py`, and new `tests/domain/services/generation/test_declaration_scheduling.py`; dependencies: T007; tier: integration/publication; done: every emitted event joins source identities and locations, rollback/cache versioning remain correct, no permanent alternate generator exists.

## US2: Compiler Evidence (P1)

- [ ] T009 [US2] Add new `src/ddon_dwarf_reconstructor/domain/models/cpp/compiler_evidence.py` and `src/ddon_dwarf_reconstructor/domain/ports/compiler_validation.py`; tests: new `tests/domain/models/cpp/test_compiler_evidence.py`; dependencies: T002,T003; tier: unit/contract; cover every response status, version identity, complete coverage, and rejection of transient AST IDs.
- [ ] T010 [US2] Implement bounded process invocation and normalization in new `src/ddon_dwarf_reconstructor/infrastructure/compiler/clang_validation.py` and package initializer; tests: new `tests/infrastructure/compiler/test_clang_validation.py`; dependencies: T009; tier: unit/integration/toolchain; done: absence, timeout, truncation, process failure, schema drift, unsupported fields, and ambiguous source joins are explicit; successful partial extraction cannot pass.
- [ ] T011 [US2] Wire optional validation through `src/ddon_dwarf_reconstructor/application/generators/symbol_header_validation.py` and `src/ddon_dwarf_reconstructor/infrastructure/composition.py`; tests: new `tests/application/generators/test_compiler_validation.py`; dependencies: T008,T010; tier: integration/architecture; done: ordinary generation never invokes the compiler, adapter construction stays in the composition root, and reports join input hashes and emission identities.
- [ ] T012 [US2] Extend validation orchestration in `tools/sonar/validate_header_bundle.py` with tests in `tests/tools/sonar/test_validate_header_bundle.py`; dependencies: T011; tier: compiler/integration; done: MSVC and Clang profiles remain separately reportable, selected include permutations are reproducible, target mismatch cannot masquerade as PS4 ABI evidence.

## US3: Differential Migration and Acceptance (P2)

- [ ] T013 [US3] Add small synthetic fixture sources under new `tests/fixtures/cpp/declaration_ir/` and differential tests in new `tests/integration/test_declaration_ir_roundtrip.py`; dependencies: T008,T010; tier: deterministic integration/compiler; done: C++ to DWARF to reconstruction compares representable canonical types, aliases, nested/template relationships, and explicit unsupported evidence, with all generated objects/DWARF kept outside Git.
- [ ] T014 [US3] Add declarator property/semantic checks to `tests/domain/services/generation/test_typed_declaration_rendering.py` and new `tests/domain/services/generation/test_declaration_lowering.py`; dependencies: T006,T010; tier: unit/property/compiler; done: arrays/callables/member pointers, cv/ref qualifiers, aliases and namespace-collision cases preserve semantic types beyond textual snapshots.
- [ ] T015 [US3] Audit removal of migrated policy in `src/ddon_dwarf_reconstructor/domain/services/generation/` and record exact deleted/replaced symbols in `specs/023-cpp-declaration-ir/measured-evidence.md`; dependencies: T012,T013,T014; tier: source review/architecture; tests: `tests/quality/test_architecture.py`; done: each migrated family has one semantic authority and no active legacy bypass.
- [ ] T016 [US3] Run the complete Feature 022 acceptance matrix against `resources/season2-resources.txt`, `tools/sonar/validate_header_bundle.py`, and existing output comparators; dependencies: T015; tier: full real-asset/compiler/semantic/determinism; evidence: `specs/023-cpp-declaration-ir/measured-evidence.md`; done: all 289 roots and every emitted header reconcile in fresh/warm and context modes, including inherited residual blockers.
- [ ] T017 [US3] Measure normal generation and optional validation separately using existing `justfile` performance workflows; dependencies: T016; tier: fixture/real-asset performance; evidence: `specs/023-cpp-declaration-ir/measured-evidence.md`; done: matching generation p50/p95 <=110% Feature 021 baseline, compiler CPU/RSS/output costs and bounded extraction limits separately reported.
- [ ] T018 [US3] Run final `test-unit`, `check`, `test`, `coverage-ci`, and `audit`, refresh generated API documentation, and reconcile `specs/023-cpp-declaration-ir/measured-evidence.md`, `checklists/requirements.md`, and `docs/roadmap/index.md`; dependencies: T017; tier: root quality/coverage/audit/documentation; done: all required evidence belongs to the final producer and no host success is labeled target ABI acceptance.

## Dependencies and Delivery

T001 is a gate, not a request to restart repair. Its first candidate is the
provisional `022-NESTED-BY-VALUE-001` record in Feature 022's measured evidence:
the bounded name inventory is complete, but one class DIE per spelling does not
cover all CU variants. Compare normalized typed layouts and methods for all
relevant `cArray` and `cTree` observations, including the nested specialization
absent from the name index.
T007 tests any justified declaration-event schedule; matching examples alone
must not be promoted to a generic primary body. T003 can follow T001's design
findings while T002
validates tooling. T005-T008 migrate shared consumers sequentially. After T009, T010's isolated
infrastructure work can proceed alongside domain scheduling; integration waits for both. US2 has
independent normalized-result/adapter tests, while US3's synthetic fixtures require no game asset.
Full-corpus acceptance never follows solely from those independent tests.

## Requirement Coverage

| Requirements | Tasks |
| --- | --- |
| FR-001, FR-002 | T003,T004,T005,T006 |
| FR-003 | T007,T008 |
| FR-004, FR-005 | T002,T009,T010,T011 |
| FR-006 | T012,T013,T014 |
| FR-007 | T005,T006,T008,T015 |
| FR-008 | T001,T002 |
| FR-009 | T002,T012,T016 |
| FR-010 | T008,T015,T016,T017,T018 |

SC-001 through SC-005 map respectively to T015, T013/T014, T010/T011, T016-T018, and T001/T002.
