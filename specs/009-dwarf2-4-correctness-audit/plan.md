# Implementation Plan: DWARF 2-4 Correctness Audit

## Evidence baseline

The external PS4 02020005 ELF is ELF64 little-endian `EM_X86_64`, FreeBSD ABI, Sony type
`0xfe10`, with 2,305 CUs. All CU headers report DWARF4 and all top-level producers are
`clang version 3.5.0 (PS4 clang version 2.50.0.2333)`. The checked-in PS3 comparison is
PowerPC64 big-endian and uniformly DWARF2. Existing generated specification JSON/Markdown preserves
the normative sources, but the v2 attribute and applicability tables are paragraph blocks and were
not queryable through the constants list.

## Design

1. Add a standalone semantic-index builder that reads only canonical JSON documents, extracts both
   tabular and paragraph-form encodings, and publishes deterministic JSON/Markdown plus manifest
   hashes.
2. Add explicit infrastructure evidence commands. Their full scans are opt-in; normal generation
   continues to own one ELF/DWARF session and source-bound durable caches.
3. Repair expression decoding, qualifier resolution, reference-offset comparison, method range
   scoring, and build-scoped authority wording with focused regression tests.
4. Record the normative relationship decisions and goal loop in architecture, testing, knowledge
   base, Spec Kit, README, and client instruction surfaces.
5. Keep MSVC/Orbis and proprietary asset checks as explicit follow-up boundaries.

## Exact paths and validation tiers

| Slice | Production paths | Test/evidence paths | Validation |
| --- | --- | --- | --- |
| Semantic index | `tools/dwarf_spec_pipeline/src/dwarf_spec_pipeline/semantic.py`, `cli.py`, `pipeline.py`, `validation.py` | `tools/dwarf_spec_pipeline/tests/test_semantic.py`, generated `semantic-index.*` | nested unit/integration/check |
| Producer evidence | `src/ddon_dwarf_reconstructor/infrastructure/elf_evidence.py`, `zstd_dump_evidence.py`, `artifact_cli.py` | `tests/infrastructure/test_elf_evidence.py`, `test_zstd_dump_evidence.py`, explicit local assets | root unit/acceptance |
| Parser relationships | `core/dwarf.py`, `dwarf_location_parser.py`, `type_resolution.py`, `primitive_type_names.py`, `method_evidence.py`, `class_parser_method_lookup.py`, `type_authority.py` | matching parser/core/authority tests | root unit/check |
| Durable guidance | `AGENTS.md`, `.github/copilot-instructions.md`, `.github/instructions/python.instructions.md`, `CLAUDE.md`, docs, `specs/009-*` | collection and documentation review | root check/handoff |

## Risk controls

- Do not rebuild the retained real dump index unless explicitly requested; the evidence command is
  a separate streaming pass and does not delete or replace the sidecar.
- Do not use `DW_AT_containing_type` as class identity evidence. Direct DIE identity and structural
  producer facts remain authoritative for root selection.
- Keep `DW_AT_specification` and `DW_AT_abstract_origin` as distinct relationships.
- Record incomplete or unavailable MSVC/Orbis evidence as such rather than upgrading confidence.
