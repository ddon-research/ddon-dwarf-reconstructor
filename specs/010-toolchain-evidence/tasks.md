# Tasks: Source-bound external tool evidence

## Tool inventory and contracts

- [x] T001 Inspect local Orbis, LLVM, GNU, libdwarf, pyelftools, LIEF, OpenOrbis, and elfldr
  surfaces, including bounded help/version output. Validation: read-only inventory.
- [x] T002 Define typed profile, output, manifest, authority, and artifact-key contracts.
  Validation: root unit/check.
- [x] T003 Implement bounded probe/export execution, source identity reuse, atomic publication,
  and fail-closed manifest loading. Validation: infrastructure unit tests.

## Ingestion and knowledge projection

- [x] T004 Add artifact CLI commands and repeatable `--tool-evidence` application wiring.
  Validation: CLI/main unit tests.
- [x] T005 Project complete exports as additive graph provenance without overwriting DWARF facts.
  Validation: exporter unit/integration tests.
- [x] T006 Add Orbis, LLVM, GNU, elfutils, libdwarf, and LLVM debug-summary profile recipes with
  explicit authority labels. Validation: profile listing and explicit local commands.

## Container and guidance

- [x] T007 Add the non-proprietary `tools/binary_toolchain` Dockerfile, Compose mounts, README,
  and root config recipe. Validation: Compose config; explicit build when available.
- [x] T008 Update AGENTS/Copilot/Python/Claude guidance, README, architecture, generation/testing
  docs, goal workflow, and knowledge-base matrix. Validation: documentation review and check.
- [x] T009 Add this Spec Kit feature with exact paths, evidence authorities, and uncertainty
  boundaries. Validation: feature review.

## Handoff validation

- [x] T010 Run the root unit/check/test/coverage/audit loop and record outcomes here. Evidence:
  446 tests passed; check and audit passed; coverage is 84.84% overall with all named high-risk
  groups above threshold; package and package-smoke also passed.
- [x] T011 Run explicit PS4 Orbis and generic LLVM/GNU/libdwarf exports, record cold/warm identity,
  and retain outputs outside source control. Evidence: schema 1.1 Orbis, LLVM JSON, and libdwarf
  summary manifests are source/tool/output-bound; warm reruns reused their keys; knowledge export
  projected three additive tool exports.
- [x] T012 Run Docker Compose config/build and nested specification checks when prerequisites are
  available; record unavailable external checks without upgrading confidence. Evidence: Compose
  config, no-cache image build, generic smoke, and direct LLVM JSON probe passed; nested test and
  check passed; nested official test skipped because its prerequisite is unavailable.

## Local Orbis CPU/ABI integration

- [x] T013 Add versioned SDK 12/SDK 8 `OrbisToolchainContract` profiles, local documentation
  provenance, promoted SDK selection, mixed-toolchain rejection, and validation schema `4.4`.
  Validation: contract serialization and SDK-selection unit tests.
- [x] T014 Add the six source-bound `orbis-bin` profiles and validator projection for external
  observations, stack sizes, dynamic-symbol counts, and fail-closed duplicate/path/hash cases.
  Validation: parser/export tests and local SDK 12 manifests.
- [x] T015 Add reusable compiler ABI probe manifests with post-optimization `-S`/`-c` retention,
  object `e_flags`/sections/CFI/stack/debug metadata, and the opt-in sectioned assembly profile.
  Validation: probe/assembly tests and the SDK 12 eight-probe run.
- [x] T016 Separate typed Sysmodule loader IDs from `NidBinding` dynamic identities and add the
  marker-gated `performance analyze-assembly` workflow. Validation: identity and `llvm-mca`
  tests plus the bounded SDK 12 performance sample.
- [x] T017 Run the complete repository `test-unit`, `check`, `test`, `coverage-ci`, `audit`, and
  documentation checks after this slice; retain unavailable real-service or full-corpus status
  explicitly in the acceptance record. Evidence: `test-unit` passed 889 tests with 7 deselected;
  `check` passed; `test` and `coverage-ci` passed 891 tests with 5 deselected; coverage was
  80.38% overall with all named high-risk groups above threshold; `audit` reported zero
  Prospector messages; `docs-api`, `docs-api-check`, and `docs-check` passed for 319 API modules.
  The SDK 12 real-asset validator published an external schema-4.3 report with six observed
  `orbis-bin` profiles, 8/8 observed ABI probes, 172,943 relocations, and 1,312 NID bindings.
  Its overall `failed` status is retained: method ABI is partial, the Doris model was
  unavailable, and one static effect/parity case remains unsupported rather than being promoted.

## SDK 12 schema-4.4 follow-up (2026-08-17)

The bounded SDK 12 gate was rerun against the source-bound `rLayout` report after instruction
effect, ABI-fact, parity, and legacy-report migration changes. The external report is schema
`4.4`; all six source-bound `orbis-bin` profiles and the retained 8/8 compiler-probe manifest
were observed. The 26 code-bearing methods retained method-specific `.s`, `.o`, and linked-object
evidence with source/tool/assembly/object hashes, `e_flags`, section layout, CFI, debug ranges,
`.sce_stack_sizes`, relocations, and canonical `orbis-objdump` output. Seventeen methods have
`target_object_equivalent` static dispositions; nine remain `not_promoted` because complete
source-bound return-type/ABI facts are unavailable. This is bounded static evidence, not runtime
or semantic equivalence, and the full Season 2 expansion remains deferred.

## Baseline-first DRY/KISS refactor (2026-08-18)

- [x] Regenerate the complete 289-root SDK 12 baseline and post-refactor outputs outside source
  control in four bounded partitions.
- [x] Replace duplicate Orbis parser/execution seams and repeated artifact/hash/publication helpers
  with pure parsers, a composed executor, shared evidence projection, and canonical I/O utilities.
- [x] Compare `disassembly-regression/1` manifests with strict identity, descriptor, content, and
  normalized-evidence equality. The external comparison reports zero differences.

The measured aggregate is 2,745 headers, 83,754 method entries, 4,504 artifact descriptors, 289
reports/source bundles, and 8,116 files. The run preserves the existing authority/status boundaries;
it does not promote method ABI, semantic equivalence, or live behavior.
