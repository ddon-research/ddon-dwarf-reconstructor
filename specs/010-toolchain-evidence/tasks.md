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
