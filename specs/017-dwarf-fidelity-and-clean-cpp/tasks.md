# Implementation tasks: Season 2 fidelity readiness

> **Retained Rust successor research:** These notes concern the unpublished Rust rewrite.
> They are not Python Feature 017 or acceptance evidence for this archived implementation.
> See [archive status](../../docs/reference/project-status.md).

**Status key:** specified = not started; in_progress = current working-tree implementation; implemented = code exists but full acceptance remains; blocked = requires an unavailable external input/tool. “Implemented” never means accepted without the listed evidence.

## T001 — Bind generated output and validation evidence

- **Status:** specified
- **Source paths:** crates/reconstructor-core/src/domain/canonical_graph.rs; crates/reconstructor-cli/src/main.rs; crates/reconstructor-cli/src/batch.rs; crates/reconstructor-cli/src/validation_report.rs.
- **Test paths:** crates/reconstructor-cli/tests/command_contract_test.rs; crates/reconstructor-cli/src/batch.rs tests; crates/reconstructor-core/src/domain/canonical_graph.rs tests.
- **Work:** replace the bare symbols manifest array with a versioned document containing ELF SHA-256/build ID where available, root-list digest, producer revision/dirty state, and per-artifact paths/hashes/sizes. Add the same source/tool/configuration identity to compiler/oracle/boundary reports. Preserve the exact dirty report and never update an existing evidence file unless the user names it.
- **Validation tier:** fast contract tests; full quality gate; real-asset manifest comparison.
- **Prerequisites:** identified Season 2 ELF and root list. Hashing is explicit and recorded, not a warm-path action.

## T002 — Repair C++ template-name rendering

- **Status:** implemented; full bundle acceptance pending
- **Source path:** crates/reconstructor-core/src/generation/header_renderer.rs.
- **Test path:** crates/reconstructor-core/tests/header_contract_test.rs.
- **Work:** retain qualified template arguments while removing only the enclosing namespace from the class declaration. Do not truncate a type at a nested namespace separator inside angle brackets.
- **Validation tier:** focused header contract test, then all 599 expected translation/header checks in a fresh candidate.
- **Evidence:** focused tests and rustfmt passed in the working tree. This does not yet prove regenerated rGrass output passes.

## T003 — Make fresh output inventory authoritative

- **Status:** specified
- **Source paths:** crates/reconstructor-cli/src/main.rs; crates/reconstructor-cli/src/batch.rs; crates/reconstructor-core/src/domain/canonical_graph.rs.
- **Test paths:** crates/reconstructor-cli/tests/command_contract_test.rs; crates/reconstructor-cli/src/batch.rs tests.
- **Work:** generate to a new ignored target directory. Compare generated files with the versioned manifest; report missing, extra, duplicate, and unowned files. Do not confuse class-row count with header/implementation-file count. Make a failed/unavailable requested generation or compiler check exit nonzero.
- **Validation tier:** synthetic temp-directory test; full 289-root real-asset acceptance.
- **Prerequisites:** identified ELF and root list. Existing output_season2_all is preserved as historical evidence.

## T004 — Restore scope and dependency completeness

- **Status:** specified
- **Source paths:** crates/reconstructor-storage/src/dwarf_extractor.rs; crates/reconstructor-storage/src/type_resolver.rs; crates/reconstructor-core/src/domain/type_scope.rs; crates/reconstructor-core/src/domain/canonical_graph.rs; crates/reconstructor-core/src/generation/dependency_collector.rs; crates/reconstructor-core/src/generation/header_renderer.rs.
- **Test paths:** crates/reconstructor-storage/tests/dwarf_extraction_test.rs; crates/reconstructor-storage/tests/synthetic_fixture_test.rs; crates/reconstructor-core/tests/type_contract_test.rs; crates/reconstructor-core/tests/scheduler_contract_test.rs.
- **Work:** preserve namespace and nested-type DIE ancestry rather than guessing from names. Ensure nZone::cContentsPool stays qualified. Require full definitions when a class layout/by-value/template use requires them; allow forward declarations for pointer/reference-only uses. Deduplicate shared ownership and ensure a fresh output contains no stale per-root copies.
- **Validation tier:** deterministic synthetic fixtures; full bundle manifest and compiler acceptance.
- **Prerequisite:** use the rAcquirement payload and cContentsPool target DIEs from the identified ELF.

## T005 — Validate declarations against target ABI

- **Status:** specified
- **Source paths:** crates/reconstructor-storage/src/dwarf_extractor.rs; crates/reconstructor-core/src/domain/member_info.rs; crates/reconstructor-core/src/generation/member_renderer.rs; crates/reconstructor-core/src/generation/header_renderer.rs; crates/reconstructor-tools/src/compiler.rs.
- **Test paths:** crates/reconstructor-storage/tests/dwarf_extraction_test.rs; crates/reconstructor-core/src/generation/header_renderer_tests.rs; crates/reconstructor-tools/tests/compiler_feedback_test.rs.
- **Work:** preserve and audit current access/pure-virtual/alignment rendering. Correct default accessibility, artificial-member/vptr treatment, base virtuality, bitfield offset semantics, static/anonymous aggregate layout, and source declaration coordinates only where a fixture or target comparison demonstrates a defect.
- **Validation tier:** synthetic layout tests plus Orbis Clang sizeof/alignof/offsetof probe for a stratified cohort including MtObject, cResource, rZone, rAcquirement, nested polymorphic classes, and bitfields.
- **Prerequisite:** Sony Orbis Clang SDK; installed at D:/SCE/ORBIS SDKs/12.000 on the current host.

## T006 — Make IDA oracle comparison reject false matches

- **Status:** in_progress
- **Source path:** crates/reconstructor-tools/src/oracle.rs.
- **Test path:** crates/reconstructor-tools/tests/oracle_test.rs.
- **Work:** compare normalized member names and types plus offsets/sizes/bit widths when present; compare bases and available class size/alignment. Ambiguous or absent IDA evidence is unavailable, never a match. Report metric denominators and exclusions.
- **Validation tier:** focused comparator tests including deliberate same-name/wrong-type and same-name/wrong-offset failures; run compare-oracle on the identified export and fresh bundle.
- **Prerequisite:** matching IDA header export identity. The old report is not acceptance evidence.

## T007 — Extend boundary evidence without claiming unmeasured parity

- **Status:** specified
- **Source paths:** crates/reconstructor-tools/src/oracle.rs; crates/reconstructor-cli/src/validation_flow.rs; crates/reconstructor-cli/src/validation_report.rs; crates/reconstructor-cli/src/args.rs; xtask/src/main.rs.
- **Test paths:** crates/reconstructor-tools/tests/oracle_test.rs; crates/reconstructor-cli/tests/command_contract_test.rs; xtask/src/tests.rs.
- **Work:** retain check-boundary, distinguish start-address overlap from exact ranges, and report per-method matches and exclusions. Parse direct ranges and DW_AT_ranges when implemented. Reconcile readelf/objdump symbols and normalize load addresses. Add an IDAPython export script for structured IDB starts/ends/chunks/prototypes only if the exact IDA runtime and input database are available; otherwise mark that evidence unavailable.
- **Validation tier:** synthetic range/alias/thunk tests; named real-asset reports with all mismatches classified.
- **Prerequisites:** exact ELF and export hashes; matching IDB/runtime for IDA chunk evidence. No universal percentage threshold is accepted before the denominator is measured.

## T008 — Preserve enum, explicit, and vtable evidence

- **Status:** in_progress
- **Source paths:** crates/reconstructor-core/src/domain/enum_info.rs; crates/reconstructor-core/src/domain/method_info.rs; crates/reconstructor-storage/src/dwarf_extractor.rs; crates/reconstructor-core/src/generation/header_renderer.rs; crates/reconstructor-core/src/generation/member_renderer.rs.
- **Test paths:** crates/reconstructor-storage/tests/synthetic_fixture_test.rs; crates/reconstructor-core/tests/type_contract_test.rs; crates/reconstructor-core/tests/explicit_method_contract_test.rs; crates/reconstructor-core/src/generation/header_renderer_tests.rs.
- **Work:** preserve enum scopedness as Scoped, Unscoped, or Unknown; emit only a declaration justified by known evidence, or produce an explicit blocking diagnostic for unknown declarations. Do not infer scopedness from DW_AT_type. Preserve explicit on constructors/conversion operators. Add raw DW_AT_vtable_elem_location expression evidence before any ABI-specific slot interpretation.
- **Validation tier:** synthetic absent/true/false and explicit-constructor fixtures; target DWARF census; Orbis layout/vtable cross-check.
- **Prerequisite:** source-bound target ELF and a producer/CU attribute census.

## T009 — Preserve function ranges and body-analysis evidence

- **Status:** specified
- **Source paths:** crates/reconstructor-storage/src/dwarf_index.rs; crates/reconstructor-storage/src/method_resolver.rs; crates/reconstructor-core/src/domain/method_info.rs; crates/reconstructor-core/src/domain/type_reference.rs; crates/reconstructor-tools/src/oracle.rs.
- **Test paths:** crates/reconstructor-storage/tests/dwarf_extraction_test.rs; crates/reconstructor-storage/tests/synthetic_fixture_test.rs; crates/reconstructor-tools/tests/oracle_test.rs.
- **Work:** represent multiple code ranges, specification/abstract-origin relationships, inline-subroutine call coordinates, lexical scopes, exact local/formal types, and location expressions/lists with PC validity. Report optimized-out/unavailable states explicitly. Do not render these records as recovered method source.
- **Validation tier:** synthetic DIE/range/location fixtures; census on the Python analytical store and identified Rust ELF; compare selected identities against IDA.
- **Prerequisites:** Python analytical store is a read-only research input; Rust runtime must remain Python-independent.

## T010 — Correct feature documents and evidence trail

- **Status:** in_progress
- **Source paths:** specs/017-dwarf-fidelity-and-clean-cpp/spec.md; specs/017-dwarf-fidelity-and-clean-cpp/plan.md; specs/017-dwarf-fidelity-and-clean-cpp/research.md; specs/017-dwarf-fidelity-and-clean-cpp/tasks.md; specs/017-dwarf-fidelity-and-clean-cpp/measured-evidence.md.
- **Test paths:** documentation link/build checks through cargo xtask docs-check and cargo xtask check.
- **Work:** replace superseded assertions, maintain the initial audit claims as historical evidence, link every acceptance claim to a source/report, and classify each outcome as verified, unavailable, failed, or not run.
- **Validation tier:** docs-check, then full check.
- **Prerequisites:** none for authored feature docs.

## T011 — Readiness gate before method-body work

- **Status:** specified
- **Paths:** all implementation sources above and specs/017-dwarf-fidelity-and-clean-cpp/measured-evidence.md.
- **Work:** complete a fresh 289-root generation; reconcile manifest/file inventories; compile every expected .h/.cpp with Orbis Clang; validate the chosen ABI cohort; run identity-bound oracle/boundary comparisons; publish separate five-axis scorecard. Any unavailable external check stays unavailable and blocks claims that depend on it. Do not start method-body reconstruction within this feature.
- **Validation tier:** full local tests/check/coverage/package smoke where tools allow; explicit proprietary-input acceptance; external IDA database run if available.
- **Prerequisites:** Orbis SDK (available), pinned Rust tools, identified inputs, and matching IDA database/runtime for structured function ranges.

