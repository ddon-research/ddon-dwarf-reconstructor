# Feature Specification: DWARF 2-4 Correctness Audit and Goal Workflow

**Status**: Implemented with explicit real-asset and MSVC follow-up boundaries

## Goal

Make the DDON reconstruction loop evidence-backed for the DWARF2-4 vocabulary and the identified
PS4/PS3 producers. The workflow must verify producer/version facts, expose searchable normative
relationships, repair parser errors where the specification proves a different interpretation, and
leave unavailable original-C++ behavior as explicit uncertainty.

## Requirements

- **DCA-001**: The repository MUST provide a read-only all-CU ELF evidence command reporting ELF
  identity, DWARF versions, CU count, producer values, language counts, and debug sections.
- **DCA-002**: The repository MUST provide a bounded-memory streaming LLVM-dump evidence command
  reporting CU versions and producer values without retaining the expanded dump.
- **DCA-003**: The specification project MUST publish a deterministic semantic index derived from
  the canonical DWARF2/3/4 artifacts, including vocabulary, attribute encodings, form descriptions,
  and tag applicability. Paragraph-form DWARF2 tables MUST be represented in the index.
- **DCA-004**: Reference-valued attributes MUST be compared through resolved target DIE offsets;
  CU-relative forms MUST NOT be treated as absolute offsets.
- **DCA-005**: Location-expression and type-qualifier handling MUST preserve ULEB128 operands and
  all qualifiers classified by the parser, including volatile and restrict.
- **DCA-006**: `DW_AT_containing_type`, `DW_AT_specification`, and `DW_AT_abstract_origin` MUST
  retain their normative relationship distinctions in code, tests, manifests, and documentation.
- **DCA-007**: The goal-oriented workflow MUST name outcome, evidence, constraints, boundaries,
  iteration action, and blocked condition, and MUST separate confirmed, approximate, blocked, and
  unresolved results.
- **DCA-008**: Documentation and Copilot/Codex/Python/Claude instructions MUST identify the
  validated PS4 baseline as DWARF4 and the PS3 comparison baseline as DWARF2.

## Non-goals

- Treating the DWARF specification as a runtime Python dependency.
- Claiming complete support for every DWARF2-4 tag, form, operation, language, or vendor extension.
- Making proprietary ELF/dump inputs, generated headers, SQLite sidecars, or MSVC installations
  part of default CI.
- Inferring original C++ behavior from declarations-only DIEs or generated header stubs.

## Acceptance

- The explicit PS4 ELF evidence reports 2,305 CUs, all version 4, and the single PS4 Clang producer.
- The PS3 comparison evidence reports a uniform DWARF2 producer baseline.
- The semantic index validates and records the `DW_AT_containing_type` applicability distinction and
  DWARF4 `DW_AT_high_pc` constant class.
- Focused parser/reference/evidence tests pass, followed by root `test-unit`, `check`, and `test`.
- Nested specification `test`, `test-official` when the official source build is available, and
  `check` are recorded separately.
- Real header generation, Orbis disassembly comparison, and MSVC loop-back checks remain explicit
  acceptance evidence and are not silently represented as complete here.
