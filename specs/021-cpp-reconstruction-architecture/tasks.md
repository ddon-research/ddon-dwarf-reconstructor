# Implementation tasks

This checklist is for implementing agents. Paths are repository-relative to
`D:/ddon-dwarf-reconstructor`; task detail names the exact source/test surface. A completed
task requires retained evidence in measured-evidence.md. Following the user's explicit request
to actually implement the findings after the Doris blocker report, confirmed failure-path and
deterministic-check fixes proceed now; the subsequent continuation includes the pure domain move.
Full-corpus parity and performance acceptance remain
required; T011 is still incomplete. Do not mix the changed producer with unchanged-code samples.

## Setup and review

- [x] T001 Preserve FR-001 snapshot in `output/refactoring-evidence/021/1b10b75e751c97b1/snapshot.json`; dependencies: none; tier: artifact integrity; done: closed ZIP CRC and all file hashes match, index and patches retained.
- [x] T002 Specify FR-001 through FR-010 in `specs/021-cpp-reconstruction-architecture/spec.md`, `plan.md`, `contracts/`, and `tasks.md`; dependencies: T001; tier: Spec Kit analysis; done: approved intent and execution dependencies are explicit.
- [x] T003 Resolve F002/FR-009 in `.specify/memory/constitution.md` and `docs/roadmap/index.md`; dependencies: T002; tier: documentation; done: Prospector is blocking consistently, amendment and roadmap recorded.
- [ ] T004 Inspect FR-002 inventory in `specs/021-cpp-reconstruction-architecture/review-inventory.md`; dependencies: T002; tier: source review; done: every production/test/support subsystem has source-inspected disposition, callers, state owner, tests, and finding/task links.
- [x] T005 Audit FR-007 tooling in `pyproject.toml`, `.prospector.yml`, `justfile`, `tests/quality/test_architecture.py`, `tests/support/quality/check_structure.py`, `tests/support/quality/check_coverage.py`, and `tests/conftest.py`; dependencies: T002; tier: quality diagnostics; done: additive no-fix rule inventory and effective duplicate settings retained, selected changes justified individually, and F040 full-SHA workflow provenance is enforced with positive and deliberate-failure tests.
- [x] T006 Audit FR-002 supporting contracts in `.github/workflows/`, `ops/`, `tools/documentation/`, `tools/sonar/`, and `tools/dwarf_spec_pipeline/`; dependencies: T002; tier: source/remote evidence; done: source/configuration inspection is recorded for each inventoried supporting file, compose/docs/compiler boundaries are explicit, and remote GitHub settings/proposal evidence is retained before workflow changes; no unavailable remote setting is claimed as enabled.

## US1: unchanged-code baseline and equivalence

- [x] T010 [US1] Verify FR-003 environment using `src/ddon_dwarf_reconstructor/artifact_cli.py`, `infrastructure/analytical/session.py`, and `infrastructure/performance/runner.py`; dependencies: T001; tier: real asset/tool preflight; evidence: `output/refactoring-evidence/021/1b10b75e751c97b1/doris-recovery-20260909-2016/`; done: source/store/Doris and tool profiles validated, the recovered C: service is healthy, the deterministic `ops/analytical-dwarf/preflight.ps1` checks digest/access/headroom/drive policy, and external raw evidence is retained.
- [ ] T011 [US1] Capture FR-003/FR-008 workload matrix through `src/ddon_dwarf_reconstructor/infrastructure/performance/runner.py`, `domain/models/performance.py`, and `infrastructure/performance/history.py`; dependencies: T010; tier: real asset/performance; done: 3 isolated cold and 5 warm samples for each profile, unchanged-code parity established, no missing-output ambiguity.
- [x] T020 [US1] Characterize FR-004/F007 current flat output in `tests/infrastructure/test_disassembly_refactor_helpers.py`, `tests/infrastructure/test_disassembly_output_equivalence.py`, and `tests/infrastructure/test_symbol_output.py`; dependencies: T011 (retained repeated rLayout evidence used while the full matrix remains open); tier: unit/regression; evidence: `measured-evidence.md`; done: missing/extra/changed files, roots, offsets, statuses, hashes, unknown fields, invalid publisher hashes, context-disabled inventories, and normalization violations fail.
- [x] T021 [US1] Extend FR-004 regression support in `src/ddon_dwarf_reconstructor/infrastructure/disassembly_regression.py` and `src/ddon_dwarf_reconstructor/infrastructure/disassembly_output_equivalence.py`; dependencies: T020; tier: unit/integration/real asset; tests: `tests/infrastructure/test_disassembly_output_equivalence.py`; evidence: `measured-evidence.md`; done: current flat output inventories validate publisher-declared hashes against physical files and compare byte artifacts separately from structurally normalized reports/manifests with an explicit allowlist; full matrix and compiler acceptance remain T060/T022.
- [x] T022 [US1] Validate FR-004 header compiler evidence via `tools/sonar/validate_header_bundle.py` and `tools/sonar/msvc_validation/`; dependencies: T011; tier: explicit compiler; evidence: `output/acceptance-candidate/season2-msvc/msvc-header-validation.json`; done: standalone MSVC results for all 898 generated Season 2 headers retained separately (435 passed, 463 syntax/type failures, 0 timeouts/unobserved) from exact bytes and optional Orbis/aggregate evidence.

## US2: characterized architectural slices

- [x] T030 [US2] Implement F003/FR-005 extraction from `src/ddon_dwarf_reconstructor/infrastructure/implementation_parity.py`, `implementation_effects.py`, and `implementation_effects_support.py` into `domain/models/cpp_reconstruction/control_flow.py`, `domain/services/cpp_reconstruction/control_flow.py`, and `instruction_effects.py`; dependencies: T004,T021; tier: unit/integration/real asset; tests: mirror under `tests/domain/services/cpp_reconstruction/` and preserve `tests/infrastructure/test_implementation_effects_t086.py`; done: characterized policy moved without an AST or fixture behavior change; full real-asset parity remains part of T060.
- [x] T031 [US2] Implement F004/FR-005 split in `src/ddon_dwarf_reconstructor/infrastructure/implementation_abi_facts.py`, `domain/models/cpp_reconstruction/abi.py`, and `domain/services/cpp_reconstruction/abi.py`; dependencies: T030; tier: unit/regression; tests: `tests/domain/services/cpp_reconstruction/test_abi.py` and `tests/infrastructure/test_implementation_validation_gate.py`; done: acquisition/classification separated with pointer, qualifiers, aggregate, cycle, partial reference, and offset-zero characterization; real compiler/ABI authority remains outside this deterministic gate.
- [x] T032 [US2] Implement F005/FR-006 bounded tool execution in `src/ddon_dwarf_reconstructor/infrastructure/toolchain_process.py`, `implementation_toolchain.py`, `implementation_assembler.py`, `implementation_linker.py`, `implementation_object_metadata.py`, and `implementation_abi_probe_manifest.py`; dependencies: T004,T021; tier: unit/integration/tool; tests: `tests/infrastructure/test_toolchain_process.py`, `test_implementation_assembly.py`, `test_implementation_linker.py`, and validation-path tests; done: bounded capture/version probing, finite timeout metadata, per-run/profile identity caching, truncation rejection, status/provenance preservation, and cleanup are covered.
- [x] T033 [US2] Review FR-005 orchestration extractions in `src/ddon_dwarf_reconstructor/application/generators/dwarf_implementation.py`, `infrastructure/symbol_output.py`, and `infrastructure/composition.py`; dependencies: T030,T032; tier: unit/integration; tests: `tests/application/generators/test_dwarf_implementation.py`, `tests/infrastructure/test_symbol_output.py`, `tests/infrastructure/test_composition.py`; evidence: `measured-evidence.md` and `research.md`; done: cohesive request/port boundaries are retained, composition-root wiring is characterized, and an explicit rejection records why another split or compatibility shim would reduce cohesion without evidence.
- [ ] T034 [US2] Implement accepted FR-002/FR-006 analytical/header/cache/knowledge findings recorded by T004; dependencies: T004,T021; tier: finding-specific unit/integration/real asset; exact source/test paths: each finding must add a numbered task here before editing; done: no accepted finding lacks implementation or external blocker, canonical source/query/artifact contracts preserved.
- [ ] T035 [US2] Implement accepted FR-002 nested/support findings recorded by T006; dependencies: T006,T021; tier: nested/packaging/quality; exact source/test paths: add a numbered task here per accepted finding before editing; done: all accepted supporting findings addressed without guessing capability or modifying unavailable remote settings.

## US3: deterministic checks, documentation, and acceptance

- [x] T040 [US3] Implement F006/FR-007 coverage enforcement in `tests/support/quality/check_coverage.py` and `tests/quality/test_check_coverage.py`; dependencies: T005,T021; tier: unit/coverage; done: empty groups reject, moved high-risk paths count, 80% line and 70% branch group thresholds retained.
- [x] T041 [US3] Extend FR-007 dependency rules in `tests/quality/test_architecture.py` and configure individually justified rules in `pyproject.toml`/`.prospector.yml`; dependencies: T005,T030; tier: quality/unit; done: import-direction and call-level process rules have passing and deliberate-failure controls, with no empty selectors or duplicate AST policy; broader review closure remains T004/T005.
- [x] T050 [US3] Synchronize FR-009 `docs/explanation/architecture/`, `docs/reference/`, `docs/how-to/`, `docs/knowledge-base/testing/`, `zensical.toml`, and generated API through `tools/documentation/generate_api_reference.py`; dependencies: T030-T041; tier: docs-api/docs-check; done: component ownership, CU-qualified context, action provenance, blocked acceptance boundaries, roadmap, README, and current deterministic evidence agree with source and Feature 021; `docs-api-check` and `docs-check` pass (365 modules, 17 Mermaid diagrams, 69 Markdown files).
- [ ] T060 [US3] Run FR-004/FR-008 acceptance through `justfile`, `tools/dwarf_spec_pipeline/justfile`, and the retained T011 runner requests; dependencies: T022,T030-T050; tier: full required root/nested/real asset/performance; done: exact parity, per-pair 110% bound, coverage/audit and applicable compiler/package checks pass.
- [ ] T070 [US3] Derive FR-010 lessons in `specs/021-cpp-reconstruction-architecture/lessons-learned.md`, update `AGENTS.md` and relevant `.github/instructions/` adapters; dependencies: T060; tier: source/evidence/docs review; done: each rule cites an observed outcome and an enforceable boundary.
- [ ] T071 [US3] Converge FR-009/FR-010 in `specs/021-cpp-reconstruction-architecture/handoff.md`, `measured-evidence.md`, and `tasks.md`; dependencies: T070; tier: Spec Kit convergence; done: no unaccounted work, claims match evidence, remaining external blockers named.

## Execution discipline

- [x] T042 [US3] Repair F008/FR-007 inherited lint intent in `src/ddon_dwarf_reconstructor/core/dwarf.py`, `infrastructure/analytical/doris_method_context.py`, `infrastructure/analytical/doris_models.py`, `infrastructure/analytical/jsonl_store.py`, `infrastructure/analytical/jsonl_views.py`, `infrastructure/implementation_effects_support.py`, and `main.py`; dependencies: T011,T005; tier: lint/type/unit; done: narrow protocol/CLI exceptions or canonical caller removal, no broad rule disable or output change.
- [x] T080 [US2] Characterize and fix F009/F010 in `src/ddon_dwarf_reconstructor/infrastructure/toolchain_process.py` with `tests/infrastructure/test_toolchain_process.py`; dependencies: T011,T021; tier: unit/integration; done: bounded prefix reads, propagated stream errors, cleanup on timeout/failure, and no successful evidence on incomplete capture.
- [x] T081 [US2] Characterize F011 in `src/ddon_dwarf_reconstructor/infrastructure/implementation_linker.py` and `tests/infrastructure/test_implementation_validation_paths.py`, `tests/infrastructure/test_implementation_linker.py`; dependencies: T011,T021; tier: unit/adapter; done: missing/stale-output cases reproduced and separate status-correction decision recorded before altering evidence behavior.
- [x] T082 [US2] Remove F013 hash forwarding from `src/ddon_dwarf_reconstructor/core/serialization.py` and update its import callers; dependencies: T011,T021; tier: typing/unit/architecture; tests: existing content-hash and serializer tests; done: callers use canonical content_hash, serialization owns conversion only, no forwarding seam remains.

- [x] T083 [US2] Repair F018/FR-006 traversal cache ownership in `src/ddon_dwarf_reconstructor/domain/services/parsing/type_chain_traverser.py`, `class_parser.py`, `class_parser_context.py`, `class_parser_methods.py`, `class_parser_member_types.py`, `class_parser_class_info.py`, and `class_parser_children.py`; dependencies: T004,T021; tier: unit/integration/real asset; tests: `tests/domain/services/parsing/test_type_chain_traverser.py` and existing parser tests; evidence: measured-evidence.md and retained F018 reproduction; done: interleaved sources cannot share cached results, session lifetime releases DIE references, within-source reuse and exact header output remain unchanged; real-asset acceptance remains T060.

- [x] T085 [US2] Repair F014/F034/FR-006 publication ownership in `src/ddon_dwarf_reconstructor/infrastructure/artifact_io.py` and `symbol_output.py`; dependencies: T004,T021; tier: unit/integration; tests: `tests/infrastructure/test_artifacts.py` and `test_symbol_output.py`; evidence: measured-evidence.md plus retained rollback/fsync probes; done: failed writes leave no orphan temp, failed rollback preserves recoverable old bundle, chained failures remain visible, successful bytes unchanged.
- [x] T086 [US2] Repair F019/FR-006 acquisition cleanup in `src/ddon_dwarf_reconstructor/infrastructure/analytical/session.py`; dependencies: T004,T021; tier: unit/integration; tests: `tests/infrastructure/test_analytical_session.py`; evidence: measured-evidence.md and resource-ownership-failures.json; done: failed source check/index/view setup closes the acquired store and clears session references without closing unrelated stores.
- [x] T087 [US2] Characterize F016/FR-006 finite configuration in `src/ddon_dwarf_reconstructor/infrastructure/config/dwarf_config.py`, `infrastructure/analytical/doris_config.py`, and `infrastructure/analytical/doris_config_environment.py`; dependencies: T004,T021; tier: unit/configuration; tests: `tests/infrastructure/test_dwarf_config.py`, `test_analytical_doris.py`; evidence: measured-evidence.md; done: NaN/infinity cannot disable finite timeout guarantees, valid defaults and explicit zero-allowed policies remain unchanged.
- [x] T088 [US2] Consolidate F035/FR-006 path validation in `src/ddon_dwarf_reconstructor/infrastructure/symbol_output.py` using `infrastructure/artifact_io.py`; dependencies: T004,T021; tier: unit/publication; tests: `tests/infrastructure/test_symbol_output.py`; evidence: measured-evidence.md; done: contained valid paths preserve exact bytes; traversal, drive-relative, and root-relative paths are rejected before staging outside the bundle.

- [x] T098 [US2] Repair F015/FR-006 ambiguous method ownership fallback in `src/ddon_dwarf_reconstructor/infrastructure/symbol_output_methods.py`; dependencies: T004,T021; tier: unit/regression; tests: `tests/infrastructure/test_symbol_output.py`; evidence: measured-evidence.md and `contracts/validation-corrections.md`; done: exact `owner_class_key` remains authoritative, duplicate display-name and containing-class fallbacks fail closed to shared output, and canonical method IDs/header bytes are unchanged when provenance is present.
- [x] T099 [US3] Repair F024/FR-008 process-tree metric accounting in `src/ddon_dwarf_reconstructor/infrastructure/performance/runner.py`; dependencies: T004,T011; tier: unit/performance instrumentation; tests: `tests/infrastructure/test_performance_runner.py` and `tests/infrastructure/test_performance_tooling.py`; evidence: `measured-evidence.md`; done: CPU and I/O deltas include every observed process lifetime, including descendants that exit before the final sample, while the published sample schema and wall/peak metrics remain unchanged.
- [x] T100 [US2] Repair F038/FR-004 source-completeness hint handling in `src/ddon_dwarf_reconstructor/infrastructure/analytical/parquet_store_queries.py`; dependencies: T004,T021,T096; tier: unit/regression; tests: `tests/infrastructure/analytical/test_parquet_partial_evidence.py`; evidence: `measured-evidence.md`; done: the Parquet selection-cache fast path rejects explicit incomplete hints, complete hints retain the fast path, and fallback `QueryResult` status/provenance remain unchanged.
- [x] T101 [US2] Repair F039/FR-004 source/CU identity in batched method context; dependencies: T004,T021,T100; exact source paths: `src/ddon_dwarf_reconstructor/domain/models/analytical_dwarf.py`, `src/ddon_dwarf_reconstructor/infrastructure/analytical/doris_method_context.py`, `src/ddon_dwarf_reconstructor/infrastructure/analytical/doris_method_context_keys.py`, `src/ddon_dwarf_reconstructor/infrastructure/implementation_dwarf_context.py`; exact test path: `tests/infrastructure/analytical/test_doris_method_context.py`; intended behavior: carry selected implementation/declaration CU offsets with each bounded request, scope every DIE/attribute/reference/location query and in-memory lookup by `(unit_offset, die_offset)`, and return unavailable evidence for an unbound ambiguous offset; validation tier: unit/regression plus focused Pyrefly/Ruff; evidence destination: `measured-evidence.md`; completion: same-offset DIEs from different CUs cannot be mixed, source-bound requests retain existing context facts and statuses, and all required root gates pass. Implemented with 34 focused tests; root unit/check/test/coverage-ci/audit gates pass. Full-corpus parity, compiler acceptance, and performance remain T010/T011/T022/T060 evidence.
- [x] T102 [US3] Enforce F040/FR-007 full-SHA GitHub Action references in `.github/workflows/`, `.github/actions/`, and `tests/quality/test_architecture.py`; dependencies: T005,T006,T041; tier: deterministic quality/unit; exact source/test paths: `tests/quality/test_architecture.py`, `.github/workflows/*.yml`, `.github/workflows/*.yaml`, `.github/actions/**/*.yml`; intended behavior: external `uses:` references require a full 40-character commit SHA and a human-readable version comment, while repository-local action paths remain valid; evidence destination: `measured-evidence.md`; completion: current workflows pass and a deliberate unpinned fixture fails closed.
- [x] T103 [US2] Repair F041/FR-006 unbounded Sonar/MSVC preparation commands in `tools/sonar/prepare_msvc_analysis.py` by reusing `tools/sonar/msvc_validation/commands.py`; dependencies: T006,T021,T032; tier: deterministic unit/tooling; exact source/test paths: `tools/sonar/prepare_msvc_analysis.py`, `tools/sonar/msvc_validation/commands.py`, `tests/tools/sonar/test_prepare_msvc_analysis.py`; intended behavior: `vswhere`, developer-shell, and Build Wrapper invocations use a finite timeout, preserve the existing `CompletedProcess` caller contract, and fail closed with bounded command status when a process times out; evidence destination: `measured-evidence.md`; completion: focused timeout and result-adaptation tests pass, all root quality/unit/default gates pass, and no compiler acceptance claim is made without the explicit MSVC workflow.
- [x] T104 [US2] Repair F042/FR-006 unbounded Sonar/MSVC diagnostics in `tools/sonar/msvc_validation/commands.py` and propagate incomplete-output status through `tools/sonar/prepare_msvc_analysis.py` and `tools/sonar/validate_header_bundle.py`; dependencies: T103,T021,T032; tier: deterministic unit/tooling; exact source/test paths: `tools/sonar/msvc_validation/commands.py`, `tools/sonar/prepare_msvc_analysis.py`, `tools/sonar/validate_header_bundle.py`, `tests/tools/sonar/test_prepare_msvc_analysis.py`, `tests/tools/sonar/test_validate_header_bundle.py`; intended behavior: both child streams are drained without deadlock, only a fixed diagnostic prefix is retained, truncation is explicit, and preparation/compiler evidence fails closed when required output is incomplete; evidence destination: `measured-evidence.md`; completion: 30 focused tests pass, focused Ruff/Pyrefly/structure checks pass, and root unit/check/default-test/coverage-ci/audit gates pass; no current-candidate compiler acceptance is implied.
- [x] T090 [US2] Repair F026/FR-006 download ownership in `tools/dwarf_spec_pipeline/src/dwarf_spec_pipeline/source_manifest.py`; dependencies: T006,T021; tier: nested unit/integration; tests: `tools/dwarf_spec_pipeline/tests/test_sources_cli.py`; evidence: measured-evidence.md; done: download/read/write/checksum failures clean only new temporary files and preserve verified destinations; no root package import.
- [x] T091 [US2] Implement F027/FR-006 bounded converter lifecycle in `tools/dwarf_spec_pipeline/src/dwarf_spec_pipeline/converters.py` and `cli.py`; dependencies: T006,T021; tier: nested unit/integration/explicit converter; tests: `tools/dwarf_spec_pipeline/tests/test_sources_cli.py` and `test_pipeline.py`; evidence: measured-evidence.md; done: finite timeout, bounded diagnostics, staged intermediates, process cleanup, and specific chained CLI errors are covered; unavailable real converters remain explicitly blocked.
- [x] T092 [US2] Repair F028/F029/FR-004 nested integrity in `tools/dwarf_spec_pipeline/src/dwarf_spec_pipeline/validation.py`; dependencies: T006,T021; tier: nested unit/integration/official; tests: `tools/dwarf_spec_pipeline/tests/test_rendering_validation.py`, `test_pipeline.py`, and `test_official_artifacts.py`; evidence: measured-evidence.md; done: missing/extra/duplicate artifacts, path escapes, symlinks, checksums, source identities, and parser identities fail; selected-version builds validate, while official acceptance still requires all three versions.
- [x] T093 [US2] Extract F031/FR-002 document builder responsibilities in `tools/dwarf_spec_pipeline/src/dwarf_spec_pipeline/normalize.py` and `document_builder.py`; dependencies: T006,T021; tier: nested unit/integration; tests: `tools/dwarf_spec_pipeline/tests/test_normalize.py` and `test_pipeline.py`; evidence: measured-evidence.md; done: omission/heading/table/list state is explicit, source provenance and deterministic rendered fixture bytes remain unchanged, and no arbitrary module-size target was added.
- [x] T094 [US2] Characterize and repair F030/FR-004 audit publication in `tools/dwarf_spec_pipeline/src/dwarf_spec_pipeline/cli.py`, `pipeline.py`, and `semantic.py`; dependencies: T092; tier: nested unit/integration/official; tests: `tools/dwarf_spec_pipeline/tests/test_sources_cli.py`, `test_pipeline.py`, and `test_semantic.py`; evidence: measured-evidence.md; done: semantic JSON/Markdown publication stages both files and rolls back a partial replacement; explicit external audit outputs remain distinct from canonical document publication.
- [x] T095 [US2] Prepare separate behavioral acceptance decisions for F011/F022/F023/F033 in `specs/021-cpp-reconstruction-architecture/contracts/validation-corrections.md`; dependencies: T004,T011; tier: characterization and explicit acceptance; tests: existing implementation parity/assembly/publisher fixtures named by each proposal; evidence: measured-evidence.md and retained reproductions; done: F011 has an accepted freshness correction, while F022/F023/F033 have concrete reproductions and explicit deferred status decisions before any evidence-contract change.
- [x] T096 [US2] Remove F036/FR-006 repeated manifest parsing from `src/ddon_dwarf_reconstructor/infrastructure/analytical/doris.py`; dependencies: T004,T021; tier: unit/integration/producer measurement; tests: `tests/infrastructure/analytical/benchmark/test_paths.py`; evidence: measured-evidence.md and doris-load-label-probe.json; done: one validated source identity per load invocation, identical existing labels and deterministic result order, no global cache or full-store reload merely to benchmark this change.
- [x] T097 [US2] Characterize F037/FR-006 durable load label identity in `src/ddon_dwarf_reconstructor/infrastructure/analytical/doris.py` and `doris_stream_load.py`; dependencies: T004,T011; tier: unit/explicit acceptance; tests: `tests/infrastructure/analytical/benchmark/test_paths.py` and `tests/infrastructure/analytical/test_doris_load_identity.py`; evidence: `contracts/validation-corrections.md` and measured-evidence.md; done: cross-table, changed source, repeated request, and existing-label outcomes have explicit expectations and a deferred migration decision; no blind replay of append-only loads.
- [x] T105 [US2] Reconstruct template families before deduplicating headers; dependencies: T004,T021,T022; tier: unit/integration/compiler; tests: `tests/domain/services/generation/test_template_families.py`, `tests/application/generators/test_template_family_layout.py`, `tests/domain/services/parsing/test_class_parser_templates_paths.py`; evidence: `measured-evidence.md`, `output/template-family-review/20260913/msvc-comparison-report.json`; done: unified `TemplateParameter` preserving child-DIE order and provenance, AST type expression substitution (`substitute_type`, `project_template`), conservative family planning (`generic`, `explicit`, `blocked`), shared multi-root template ownership (`shared/rTbl2.h`, `shared/MtCollection.h`), 145 duplicate headers eliminated, MSVC error C2953 reduced from 2,890 to 0 (100% eliminated), failed headers reduced from 463 to 264.
- [x] T106 [US2] Mitigate MSVC C2955/C1003 cascades, member pointer indirection, and forward-declaration collisions; dependencies: T105,T022; tier: unit/integration/compiler; tests: `tests/domain/services/generation/test_header_generator_planning.py`, `tests/domain/services/generation/test_header_generator_dependency_ordering.py`, `tests/domain/services/parsing/test_template_argument_parser.py`, `tests/domain/services/parsing/test_type_resolver.py`; evidence: `measured-evidence.md`, `output/template-family-review/current-validation/msvc-header-validation.json`; done: canonical balanced delimiter template splitter, recursive nested typedef and template argument resolution, specialization forward declarations, enum class/class forward-declaration deduplication, by-value member template dependency indirection detection, typedef forward declaration filtering; passed headers increased to 580 (+91), failed headers reduced to 173 (-91), C1003 error limit cascades reduced from 195 to 16 (-91.8%).


T034 cannot close before T082,T083,T085-T088,T096 and the T097 acceptance disposition.
T035 cannot close before the applicable remote blocker dispositions even though T090-T094 are
implemented and their nested deterministic gates pass.
T050 and T060 include those child tasks through T034/T035; numerical ranges are not a waiver
for tasks added after the original checklist. T095 and T097 may close as explicitly deferred
behavior changes only when their concrete proposals and decisions are retained.

Tasks within one dependency chain run sequentially. Baseline measurements run without concurrent
heavy tests, builds, or other benchmark children. Read-only review/document authoring can proceed
while external preflight runs. No agent delegation is assumed. Every coherent production slice
runs focused tests, test-unit, check, and test before advancing. T034/T035 are review work packages,
not permission to implement unspecified changes: add exact accepted-finding tasks first.

## Implemented slices awaiting final real-asset acceptance

- T085/F014/F034: implemented temporary-write cleanup and recoverable directory rollback.
  New exact regression path: `tests/infrastructure/test_failure_ownership.py`, alongside the
  original artifact/publisher tests. Failed fsync, failed publication, and failed rollback are covered.
- T086/F019: implemented failed analytical-session acquisition cleanup and reference release
  even when store close raises; regression path: `tests/infrastructure/test_failure_ownership.py`.
- T088/F035: removed the weaker symbol path validator; publication uses `artifact_io.safe_relative_path`.
- T080/F009: implemented bounded diagnostic prefix reading, with
  `tests/infrastructure/test_toolchain_process.py`. Other process-lifecycle findings remain open.
- T040/F006: reject empty executable coverage groups and include the newly exercised publication,
  tool-process, and analytical-session modules in their high-risk groups. Future module moves still
  require coverage selector updates.
- T005/F008: restore precise N802/N803 exceptions for pyelftools-compatible protocol methods;
  extend the existing B008 CLI-file policy to `implementation_coverage_cli.py`; materialize the
  two fixed mnemonic lists; remove two unused launcher re-exports and update `tests/test_main.py`
  and `tests/test_main_paths.py` to import the canonical functions directly. Apply the required
  formatter to `infrastructure/performance/export.py`; this changes formatting only.

These implementation dispositions do not check off broader task acceptance conditions. Focused,
unit, full correctness, quality, coverage, and audit results are retained in measured-evidence.md.

T030/F003 is implemented as a behavior-preserving move: `domain/services/cpp_reconstruction/`
contains `control_flow.py`, `instruction_effects.py`, and `instruction_operands.py`;
`domain/models/cpp_reconstruction/control_flow.py` contains the existing step/join values.
`tests/domain/services/cpp_reconstruction/test_instruction_effects.py` owns the five moved pure
tests; CFI tests remain in infrastructure. T041 adds domain/application and external-module
rules with negative controls; T040 includes the reconstruction coverage group. Broader T041
reflection/call-level policy work and final real-asset acceptance remain open.

T031/F004 is implemented: `infrastructure/implementation_abi_facts.py` now exposes typed
`acquire_return_type`; `domain/models/cpp_reconstruction/abi.py` defines acquired evidence and
classification values; `domain/services/cpp_reconstruction/abi.py` owns pure ABI classification.
`implementation_dwarf_context.py` consumes typed results while preserving emitted dictionary
fields and diagnostics. New tests: `tests/domain/services/cpp_reconstruction/test_abi.py` and
`tests/infrastructure/test_implementation_abi_facts.py`. The pre-change implementation and a
371-case differential result are retained externally. Traversal is not replaced with
TypeChainTraverser; no ABI-status correction is folded into the extraction.

T087/F016 is implemented at the configuration construction boundary in `doris_config.py` and
`infrastructure/config/dwarf_config.py`. Tests in `tests/infrastructure/test_finite_timeouts.py`
cover direct construction and environment parsing. `doris_config_environment.py` needs no
parallel validation policy because the returned values pass through DorisConfig construction.
Existing positive/nonnegative policies and zero analysis wait are preserved.

T080/F010 is implemented alongside F009. `toolchain_process.py` now retains stream-writer
failures while draining child output, terminates the process before reporting the chained error,
and treats drain failures as incomplete tool evidence. `tests/infrastructure/test_toolchain_process.py`
covers the bounded read, drain failure, no-stdout-pipe cleanup, and timeout paths. The focused
tests passed; `f010-f013-test-unit.txt`, `f010-f013-check-retry.txt`, and `f010-f013-test.txt`
retain the preceding full gates.

T082/F013 is implemented. `core.serialization` owns JSON conversion only; all hash callers use
`core.content_hash`, and `tests/core/test_serialization_boundaries.py` rejects a forwarding seam.
The focused and full local gates passed with no output-contract change.

T083/F018 implementation is complete but its real-asset acceptance remains open. Each
`ClassParser` owns a `TypeChainTraverser`; caches no longer cross source sessions, and
`clear_cache()` releases cached DIE references. The integer-CU collision, parser construction,
and weak-reference release tests are in `tests/domain/services/parsing/test_type_chain_traverser.py`,
with aggregate/children parser helpers updated for the explicit dependency. Focused parser tests
passed 48 cases; the full F018 unit/check/test gates are retained as `f018-test-unit-retry.txt`,
`f018-check.txt`, and `f018-test.txt`. No full-corpus header parity claim is made until the
blocked source-bound baseline can be rerun.

T096/F036 is implemented in `infrastructure/analytical/doris.py`. The validated manifest from
plan validation is carried through execution and native file loading; direct load calls load it
once and pass the source SHA to every label calculation. `test_loader_reads_manifest_once_for_load_scoped_labels`
proves one read for three concurrent files and preserves source-bound labels and plan order.
The F036 unit/check/test gates are retained as `f036-test-unit.txt`, `f036-check-retry.txt`, and
`f036-test.txt`. F037's durable label identity remains a separate acceptance decision.

T081/F011 is implemented under the accepted decision in
`contracts/validation-corrections.md`. Linker output is staged in a temporary directory and
atomically replaced only after a successful process exit with a real output file. Failed runs
never return a stale previous `*.linked.o`, and a previous valid object remains recoverable.
Missing-output and stale-output regressions are covered in
`tests/infrastructure/test_implementation_validation_paths.py`; the existing success, timeout,
missing-tool, and rejected-input cases remain unchanged.

T032/F012 is implemented as a narrow API cleanup. `collect_object_metadata` no longer accepts
the discarded `output_dir` and `stem` arguments; `implementation_toolchain.py`,
`implementation_abi_probes.py`, and the existing malformed-object test now use the smaller
contract.

T032/F005 is now implemented across the bounded implementation-tool workflow. The shared
`toolchain_process` runner owns bounded stdout/stderr capture, finite timeout metadata, and
version observations. `ToolIdentityCache` is explicitly scoped to one toolchain run and profile,
so executable hashing/version probes are reused without becoming process-global state. Assembly,
linker, object-metadata, objdump, and ABI-probe paths use the same capture contract; truncation,
timeouts, drain failures, and tool errors remain incomplete evidence with chained diagnostics.
The focused toolchain/assembly/linker/ABI selection passed 35 tests; the subsequent full gates
passed 1,134 unit tests and 1,129 default tests, and `just check` passed. Live proprietary-tool
execution, full-corpus parity, and performance acceptance remain environmental evidence for T060.

T099/F024 is implemented at the performance-runner sampling boundary. `_ProcessAccounting` keys
observations by PID and process creation time and sums each process's first-to-last counter delta,
so short-lived descendants remain represented after they leave the live process tree. Published
`process-samples.jsonl` rows retain their existing schema; only aggregate CPU and I/O metrics use
the lifetime totals. The deterministic accounting regression is in
`tests/infrastructure/test_performance_tooling.py`; workload lifecycle tests remain in
`tests/infrastructure/test_performance_runner.py`. Full root gates and the final performance
matrix remain required before T060 can accept runtime claims.

T100/F038 is implemented at the Parquet serving selection boundary. An explicit `False`
completeness flag from the selection cache now disables the cached primary-definition offset
fast path, matching the Doris adapter's fail-closed policy; complete hints still hydrate directly.
`tests/infrastructure/analytical/test_parquet_partial_evidence.py` covers both paths and preserves
the fallback query result's status and provenance. Full root gates remain required after this
slice; no full-corpus or performance claim is made from the focused characterization alone.

T105 is implemented across the template parsing, family planning, declaration synthesis, and
header deduplication pipeline. `TemplateParameter` unifies type and value parameters with child-DIE
ordering and DWARF provenance. `TemplateFamilyPlan` conservative planning discriminates between
generic template emission and explicit specializations with base inheritance. Multi-root template
families are assigned to `shared/`, eliminating 145 duplicate headers (including 99 duplicate `rTbl2.h`
and 38 duplicate `MtCollection.h` files). In standalone MSVC compilation, `error C2953` was reduced
from 2,890 to 0 (completely eliminated), and failed headers were reduced from 463 to 264.

T106 is implemented to eliminate C2955/C1003 error cascades, member indirection detection bugs,
and forward-declaration collisions. Balanced delimiter tracking across `<>`, `()`, `[]`, and `{}`
in `template_argument_parser.py` fixed broken arity splits on function-pointer template arguments.
Recursive nested typedef collection and nested template argument resolution provide complete type
definitions. Specialization argument forward declarations eliminate cascading fatal `C1003` aborts.
Base class offsets are retained in template family signatures to prevent conflicting layout merges.
Forward-declaration deduplication now pairs `enum class` and `class`, prioritizing `enum class`.
By-value member template dependency detection strips `<...>` before checking indirection (`*`, `&`),
properly emitting `#include` statements for composite types like `cDelegate_4`. Typedef names are
excluded from forward declaration emission. Standalone MSVC compilation of all 753 Season 2 headers
increased cleanly passing headers to 580 (+91), reduced failed headers to 173 (-91), and reduced
fatal `C1003` aborts from 195 to 16 (-91.8%). Target headers `cDelegate.h`, `cpSequenceCtrl.h`,
`rStageJoint.h`, and `MtCollection.h` compile cleanly.

