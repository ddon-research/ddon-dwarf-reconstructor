# Tasks: DWARF 2-4 Correctness Audit

## Evidence and index

- [x] T001 Inspect repository instructions, existing specification artifacts, real local ELF/dump
  paths, worktree changes, and retained sidecars. Validation: read-only inventory.
- [x] T002 Verify PS4 ELF CU versions/producers and PS3 comparison versions/producers. Validation:
  explicit all-CU local evidence plus checked-in header records.
- [x] T003 Add paragraph/table-aware semantic index and deterministic JSON/Markdown publication.
  Validation tier: nested unit, integration, and check.
- [x] T004 Add explicit ELF and compressed LLVM-dump evidence commands. Validation tier: focused
  unit tests and explicit local evidence.

## Parser and relationship correctness

- [x] T005 Decode ULEB128 `DW_OP_plus_uconst`/`DW_OP_constu` operands, including byte blocks and
  offset zero. Validation tier: parser unit/regression tests.
- [x] T006 Preserve volatile/restrict type qualifiers and range-based method evidence. Validation
  tier: parser unit/regression tests.
- [x] T007 Resolve reference targets before comparing offsets and preserve specification versus
  abstract-origin semantics. Validation tier: core/parser unit tests and documentation review.
- [x] T008 Remove the incorrect `DW_AT_containing_type` class-authority claim and test the updated
  manifest contract. Validation tier: authority unit/regression tests.

## Documentation and client loop

- [x] T009 Update README, architecture, generation flow, tag analysis, testing, LLVM notes, and
  the DWARF knowledge base with confirmed facts and remaining uncertainty.
- [x] T010 Update AGENTS, Copilot, Python, and Claude instructions with evidence-first goal loop,
  current 600/500/75/10 structure limits, and new commands.
- [x] T011 Add the goal workflow guide and this Spec Kit feature with exact paths and validation
  tiers.

## Handoff validation

- [x] T012 Run focused tests, `uv run just test-unit`, `uv run just check`, and `uv run just test`.
- [x] T013 Run nested `just test`, `just check`, and `just test-official` when official-source
  prerequisites are available; record skipped external prerequisites explicitly.
- [ ] T014 Run the final real-header/MSVC/Orbis loop-back with explicit compiler and disassembly
  paths; this remains an external acceptance prerequisite, not a parser-completion claim. Current
  blocker: `output/msvc-header-validation-20260801/compile_msvc.cmd` is absent, although the
  documented Orbis executable is available.
