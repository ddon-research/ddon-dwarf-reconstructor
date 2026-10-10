# Season 2 fidelity research and evidence audit

> **Retained Rust successor research:** These notes concern the unpublished Rust rewrite.
> They are not Python Feature 017 or acceptance evidence for this archived implementation.
> See [archive status](../../docs/reference/project-status.md).

**Date:** 2026-09-28  
**Feature:** 017-dwarf-fidelity-and-clean-cpp  
**Authority:** Rust source/reports for current behavior; identity-bound exports for comparisons; DWARF 4 standard and Python reference for format research.

## Executive conclusion

The initial feature draft identified important fidelity topics, but its baseline and several proposed fixes were not verified. Three parallel audits (generated output/source, IDA exports/oracle, and DWARF 4 extraction) found incomplete compilation, an entry-address checker mislabeled as boundary parity, and oracle matching that can produce false positives. No overall “better than IDA” claim is supported.

Keep five comparison axes separate: C++ declaration semantics, target ABI layout, function identity/ranges, DWARF annotation coverage, and method-body recovery. IDA’s header is a C-like type export; its C decompilation and IDB are separate function evidence.

## Verified current state

### Compilation and generated output

- reports/compiler_validation.json is the latest inspected report: **595 passed and 4 failed checks out of 599**. The failures are the .h and .cpp checks for cBVHGrass and rGrass. The primary parse error is class cCluster> in cBVHGrass.h, followed by an undefined cTree<rGrass::cCluster> specialization in rGrass.h.
- reports/season2_all_compiler_validation.json records 581/581 passed but predates the current output and is not current acceptance evidence.
- output_season2_all contains 303 headers and 296 .cpp files (599 files); its symbols manifest has 595 class rows. These counts describe different things. A fresh run must establish expected versus actual artifact inventory.
- The compiler report is not bound to the source ELF digest, root-list digest, generated-file digests, or complete compiler/target settings.
- The current output contains old per-resource copies alongside shared copies of some types. The renderer filters _vptr$ members and current shared/MtObject.h has no explicit vptr; some older per-resource copies still contain explicit vptr text. Test a fresh output before changing vptr policy.
- Confirmed bundle gaps include an unqualified cContentsPool under rZone and forward-only rAcquirement payload classes such as cAbilityData and cCustomSkillData. Require complete definitions according to by-value/layout/template use; do not expand every pointer target.

### Existing IDA and oracle checks

- reports/ida_boundary_parity.json reports 2,684/2,817 (95.3%) and passes its 95% threshold. The implementation compares selected DWARF low_pc entry addresses with IDA C banner starts. It does not compare high PCs, ranges, ends, or IDA chunks. The report does not retain per-method evidence.
- reports/season2_all_oracle_comparison.json records 251 passed, 14 failed, and 29 unavailable checks. IdaOracleComparator accepts a same-named member without comparing type or offset.
- Available exports include .i64, .c, .h, compressed .c/.h, ELF, LLVM DWARF dump, readelf symbols/headers, and objdump symbols/headers/disassembly. The .c has 108,492 unique function banners. Readelf has 120,884 FUNC rows and objdump has 119,698 .text function rows. Only 92,727 IDA banner addresses occur in readelf's function-address set; classify these differences rather than guessing.
- The ELF read by the parallel audit is 800,622,848 bytes with SHA-256 4236F598ACC8F15893181455ED195E39DFA4DBFDA4EEDA8B56FCBD82312C63C0. Recompute and bind exports before comparison. The objdump header refers to an IDA9.2 path while the containing directory is IDA9.3.
- The .i64 is useful for ends/chunks only if it is proven to describe the same ELF and can be read by a matching IDA runtime. The current host exposes an IDA SDK path but no IDA executable on PATH; structured database evidence is unverified.

### C++ modeling and metadata

- Existing source already handles access grouping, pure virtual = 0, some alignas, class/method source comments, and namespace blocks. These require auditing and coverage, not wholesale reimplementation.
- Namespace recovery remains incomplete: scope is not consistently propagated from DIE ancestry and some renderer paths use naming heuristics. Preserve namespace and nested-aggregate identity from actual scope components.
- EnumInfo.is_scoped is hardcoded false by extraction and the renderer emits plain enum. DW_AT_explicit is not represented in MethodInfo. Absence of DW_AT_enum_class must remain unknown. Python Feature 022 evidence shows producer-conditioned ambiguity, including suspicious flags for std::io_errc.
- DW_AT_vtable_elem_location is not retained as typed method evidence. Preserve its raw expression and source DIE before interpreting it.
- Class alignment and declaration file/line are partly extracted, but file paths reduce to basenames and line columns/declaration-vs-implementation provenance are incomplete. Local-variable extraction visits only direct children, records auto, omits type/location/scope, and does not reconstruct .cpp bodies.
- Direct low_pc/high_pc is not a complete code-range model. Audit DW_AT_ranges, specification/abstract-origin links, inline-subroutine DIEs, lexical blocks, and variable location lists.

## DWARF reference findings

Use the official DWARF 4 standard (https://dwarfstd.org/doc/DWARF4.pdf) and the Python reference at D:/ddon-dwarf-reconstructor/docs/knowledge-base/dwarf-specification/generated/dwarf4.md. The Python analytical store offers a useful census/preservation pattern for DIE ancestry, raw/decoded attributes, references, ranges, location expressions, and line rows. It is a research aid, not a Rust runtime dependency.

Prioritize candidates after a producer/CU attribute-frequency census:

1. Declaration/layout: scope ancestry, enum-scopedness, enum representation, explicit constructors, accessibility defaults, full source coordinates, artificial members, base/access/virtuality, bit offsets/widths, static members, and alignment.
2. Function identity: specification/abstract-origin links, DW_AT_ranges, range lists, inline call coordinates, and raw virtual-slot expressions.
3. Body-analysis evidence: lexical blocks, local/formal variable types, scopes, source positions, location expressions/lists, and PC-validity ranges.

Local-variable metadata does not provide source expressions or control flow. This feature captures evidence; method-body reconstruction remains a separate feature.

## Tooling and working-state evidence

- Baseline Git revision before implementation edits: 9cfb2373b207a3d4e748672a892a22272b2bc337; no Git remote is configured.
- Preserve the pre-existing dirty reports/singular_roots_findings.json, SHA-256 685945581B4059FCB1D33C3D699BAD0F163684374EA4402AA9B21BEFB9DAC3F4. It contains not_run rows and changed class counts.
- Sony Orbis compiler is available at D:/SCE/ORBIS SDKs/12.000/host_tools/bin/orbis-clang++.exe. It reports PS4 Clang 12.00.0.543, target x86_64-scei-ps4 (self-host Clang 17.0.6).
- cargo xtask doctor currently fails because cargo-nextest 0.9.145 is missing from PATH. Its crate source is cached locally; install/build the pinned tool into ignored target/tools if offline installation succeeds. Until then, cargo test --workspace --locked is a fallback, not evidence that the pinned doctor gate passed.
- Put candidate output under a new ignored target path or another external location. Never overwrite output_season2_all or the dirty report.

## Claims superseded from the initial draft

The blanket claims that all Rust output is already 100% compilable, MtObject currently has a duplicate vptr, no namespace/access/pure-virtual/alignment/provenance support exists, IDA removes methods from all exports, all pointer/template targets need complete definitions, and IDA boundaries match 1:1 are not verified. The active spec supersedes those claims; the Git diff preserves the initial draft.

