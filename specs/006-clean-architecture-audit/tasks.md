# Tasks: Clean Architecture Audit and Modernization

**Input**: `spec.md`, `research.md`, and `plan.md` in this directory.

**Status**: Historical implementation and convergence complete; 2026-09-05 follow-up in progress;
Tier 3 deferred.

## Phase 1: Audit package

- [x] T001 Inventory all tracked root source, tests, nested-tool source, active
  instructions, architecture/readme documents, and Spec Kit features.
- [x] T002 Establish the root baseline with `uv run just test-unit` and
  `uv run just check`; record the test count and fallback-path diagnostics in
  `research.md`.
- [x] T003 Reproduce source-identity collision, timeout completeness,
  candidate-provenance, hexadecimal vtable, CU-header, invalid-catalog,
  same-stem-cache, and failed-context-entry cases.
- [x] T004 Update `AGENTS.md`, `.github/instructions/python.instructions.md`,
  `.github/copilot-instructions.md`, `README.md`, architecture/testing/
  generation-flow docs, and affected Spec Kit contracts to describe one
  canonical path and intentional breaking refactors.

## Phase 2: Source identity and durable artifacts

- [x] T005 Add same-size middle-replacement and malformed-root tests in
  `tests/infrastructure/test_artifacts.py`; refactor
  `src/ddon_dwarf_reconstructor/infrastructure/artifacts.py` so warm lookup
  cannot authorize stale strong identities. **Tier 1**.
- [x] T006 Replace the bounded fingerprint and unbound-cache sampling in
  `src/ddon_dwarf_reconstructor/domain/services/lazy_index_source.py` with the
  shared source-identity port; update
  `tests/domain/services/test_lazy_index_paths.py` and
  `tests/domain/services/test_lazy_dwarf_index_service.py`. **Tier 1/3**.
- [x] T007 Remove implicit historical-shape conversion and completeness
  promotion from `cache_schema.py`, `cache_persistence.py`, and
  `persistent_symbol_cache.py`; update
  `tests/domain/repositories/cache/test_multi_definition_cache.py` and
  `test_persistent_symbol_cache.py` for explicit rebuild behavior. **Tier 1**.
- [x] T008 Delete `domain/repositories/cache/header_cache.py`, route generated
  files through `infrastructure/header_output.py`, and replace the old header
  cache tests with source-bound artifact and publication coverage. **Tier 1/2**.

## Phase 3: Evidence status and parser correctness

- [x] T009 Add typed complete/partial/unavailable/timeout search results and fix
  `class_parser_scan.py` and `lazy_index_search.py`; cover positive candidates
  after timeout and mixed-CU provenance in
  `tests/domain/services/parsing/test_class_parser_scoring_fast.py`,
  `test_class_parser_scoring_exhaustive.py`, and
  `tests/domain/services/test_lazy_index_paths.py`. **Tier 1**.
- [x] T010 Normalize `DwarfCompilationUnit` headers in the adapter and remove
  dual mapping/object access in `lazy_index_lookup.py` and `lazy_index_search.py`;
  update `src/ddon_dwarf_reconstructor/core/dwarf.py` and typed fixture builders.
  **Tier 1/2**.
- [x] T011 Correct vtable expression parsing, `DW_AT_noreturn` handling, string
  decoding, enum value errors, and array/type-chain termination in
  `class_parser_methods.py`, `class_parser_aggregate_types.py`,
  `type_resolution.py`, and `array_parser.py`. Add focused tests under
  `tests/domain/services/parsing/` and include `resources/rGUI.dwarfdump` text
  coverage. **Tier 1/3**.
- [x] T012 Replace broad parser and platform fallbacks with typed diagnostics in
  `type_resolution.py`, `class_parser_class_info.py`, `file_registry.py`, and
  `infrastructure/elf_platform.py`. **Tier 1/2**.

## Phase 4: Composition and rendering

- [x] T013 Replace `DwarfGenerator` multiple inheritance and concrete session
  construction with composition; add
  partial-construction cleanup tests in
  `tests/application/generators/test_dwarf_generator_setup.py`. **Tier 1/2**.
- [x] T014 Make `patch_pyelftools_for_ps4()` idempotent and invoke it only from
  the ELF composition adapter; update `tests/utils/test_elf_patches.py`. **Tier 1**.
- [x] T015 Replace untyped settings in `infrastructure/config/dwarf_config.py`
  with validated configuration and connect the timeout setting to the use case;
  add invalid-environment coverage in `tests/infrastructure/test_dwarf_config.py`.
  **Tier 1**.
- [x] T016 Make cycles blocking diagnostics and render template arity and
  optional offsets structurally in `header_ordering.py`,
  `header_type_planning.py`, and `header_member_rendering.py`; extend
  `tests/domain/services/generation/test_header_generator_ordering.py`,
  `test_header_generator_planning.py`, and `test_header_generator_rendering.py`.
  **Tier 1/2**.
- [x] T017 Publish generated bundles through one atomic output adapter in
  `src/ddon_dwarf_reconstructor/main.py` and cover interrupted publication in
  `tests/test_main_paths.py` and the output-manifest tests. **Tier 1/2**.
- [x] T018 Remove duplicate utility modules and duplicate public method shapes;
  update imports in `src/ddon_dwarf_reconstructor/` and mirrored tests, then run
  the architecture suite. **Tier 1**.

## Phase 5: Convergence

- [x] T019 Review `tools/dwarf_spec_pipeline/src/dwarf_spec_pipeline/readers.py`
  and `source_manifest.py` for decomposition and exception-specific cleanup;
  run the nested `just check` and tests. **Tier 2**.
- [x] T020 Run `uv run just test-unit`, `uv run just check`, `uv run just test`,
  `uv run just coverage-ci`, and `uv run just audit`; record compiler and real
  PS4 tiers as deferred because they were not selected for this slice. **Tier 2/3**.
- [x] T021 Re-run the repository-wide terminology and architecture review, update
  affected README, architecture, testing, generation-flow, Python instructions,
  and Spec Kit artifacts, and close only findings backed by evidence. **Tier 1/2**.

## Phase 6: Cross-platform CI convergence

- [x] T022 Inspect all open Dependabot PR diffs, checks, and failed Actions logs with `gh`;
  record the shared correctness failure separately from the publisher permission warning.
  **Tier 1 evidence**.
- [x] T023 Refactor `SourceIdentityCatalog` and the source-identity port so relocation keeps
  the strong identity without allowing ctime-only mutation at an existing path. Add the
  ctime regression in `tests/infrastructure/test_artifacts.py`. **Tier 1**.
- [x] T024 Update AGENTS/Copilot/Python/Claude guidance, goal workflow, README, architecture,
  testing docs, Spec Kit artifacts, and the testing knowledge base with the CI and filesystem
  contracts. **Tier 1/2**.
- [x] T025 Re-run the remote PR checks after publishing the fix, resolve the stale pytest PR via
  conflict-free replacement PR #8, synchronize the nested lockfile in PR #9, and append the
  final CI evidence. **Tier 2 external handoff**.
- [x] T026 Resolve Dependabot security alert #1 for `pytest` in
  `tools/dwarf_spec_pipeline/uv.lock` by upgrading to patched 9.1.1, validate the nested lock,
  quality, and test loops, and verify that GitHub reports the alert as fixed after the dependency
  graph refresh. **Tier 2 external handoff**.

## Phase 7: Correctness-first follow-up, 2026-09-05

- [x] T027 Separate preparation from mutation in
  `src/ddon_dwarf_reconstructor/infrastructure/header_output.py`; add
  `tests/infrastructure/test_header_output.py` for existing-manifest preservation, interrupted
  replacement, and retained recovery backups. **Tier 1/2**: focused tests, `just test-unit`,
  `just test`, and `just check` pass.
- [x] T028 Persist accepted observation metadata in
  `src/ddon_dwarf_reconstructor/infrastructure/artifacts.py`; extend
  `tests/infrastructure/test_artifacts.py` and add
  `tests/infrastructure/test_source_identity_relocation.py` for repeated reuse and unchanged
  mutation guards. **Tier 1/2**: focused tests and the same root gates pass.
- [x] T029 Repair close/abort ownership and required sink typing in
  `src/ddon_dwarf_reconstructor/infrastructure/analytical/record_sink.py`, `parquet.py`, and
  `materializer.py`; test fault injection in `tests/infrastructure/test_analytical_checkpoint.py`
  and `tests/infrastructure/analytical/test_record_sink.py`. **Tier 1/2**: focused tests and root
  test/quality gates pass; coverage thresholds pass and audit reports zero diagnostics.
- [ ] T030 Make backfill staging/recovery explicit in the same analytical publisher and
  materializer; extend `tests/infrastructure/test_analytical_store.py` and
  `tests/infrastructure/test_analytical_parquet_contract.py`. **Tier 1/2**; no real-store purge.
- [ ] T031 Consolidate parsed-definition ranking and strict qualified resolution in
  `src/ddon_dwarf_reconstructor/domain/services/definition_selection.py` and
  `application/generators/symbol_definition_graph.py`; extend
  `tests/application/generators/test_symbol_definition_graph.py` and
  `tests/domain/services/test_definition_selection.py`. **Tier 1/2**.
- [ ] T032 Reuse normalized type policy in
  `src/ddon_dwarf_reconstructor/domain/services/generation/rendering/type_policy.py`,
  `application/generators/dwarf_symbol_generation.py`, and
  `application/exporters/knowledge_export_fields.py`; test builtin and unresolved evidence in
  `tests/application/exporters/test_knowledge_exporter_core.py`. **Tier 1/2**.
- [ ] T033 Extract application hierarchy preparation under
  `src/ddon_dwarf_reconstructor/application/generation/hierarchy_preparation.py`; migrate
  `application/generators/dwarf_header_support.py`, `dwarf_knowledge.py`, and
  `dwarf_implementation.py`; add `tests/application/generation/test_hierarchy_preparation.py`.
  **Tier 1/2**, after T031/T032.
- [ ] T034 Define combined export contracts in
  `src/ddon_dwarf_reconstructor/application/generation/knowledge_export_contracts.py`, update
  `specs/001-header-foundation/contracts/cli-and-artifacts.md` and
  `specs/015-ladybugdb-knowledge-graph/contracts/import-contract.md`, then migrate
  `main.py`, the knowledge exporter, and the hierarchy union to one batch. Add
  `tests/application/exporters/test_knowledge_exporter_batch.py`. **Tier 1/2**, after T033.
- [ ] T035 Add `src/ddon_dwarf_reconstructor/infrastructure/knowledge_output.py` and
  `tests/infrastructure/test_knowledge_output.py`; inject the typed publisher and remove
  application-owned final-file writes. Cover partial roots, identity conflicts, previous-bundle
  retention, and one unified schema. **Tier 1/2**, after T034 contracts.
- [ ] T036 Bind `src/ddon_dwarf_reconstructor/infrastructure/analytical/doris_registry.py`,
  `doris.py`, and `doris_store.py` to an exact manifest digest; extend
  `tests/infrastructure/analytical/test_doris_registry.py`. **Tier 1/2**; live migration remains
  separate, and legacy rows are not trusted from counts alone.
- [ ] T037 Move Typer ownership from infrastructure CLI support modules to package-root CLI
  modules; update `src/ddon_dwarf_reconstructor/artifact_cli.py`, `cli.py`, and
  `performance_cli.py` callers, plus `tests/test_artifact_cli.py`, `tests/test_cli.py`, and new
  `tests/test_performance_cli.py`. Remove aliases only after caller migration. **Tier 1/2**.
- [ ] T038 Strengthen `tests/quality/test_architecture.py`,
  `tests/support/quality/check_coverage.py`, and `tests/quality/test_check_coverage.py`; update
  affected docs and source-derived API pages. Run `just test`, `just check`, `just coverage-ci`,
  and `just audit`, recording external blockers separately. **Tier 1/2**.
