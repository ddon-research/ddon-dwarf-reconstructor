# Research record: DWARF 2-4 producer and relationship audit

## Confirmed

- `DDOORBIS.elf` has 2,305 CUs and every CU header is DWARF4.
- Every PS4 top-level producer is `clang version 3.5.0 (PS4 clang version 2.50.0.2333)`.
- The PS3 comparison ELF has 1,092 CUs, all DWARF2, with the SN Systems PS3 producer.
- `DW_AT_containing_type` is a reference for pointer-to-member types, not class identity.
- DWARF4 permits a constant `DW_AT_high_pc` offset; this must not be treated as an absolute address.
- A full streaming scan of the compressed PS4 LLVM dump independently reports 2,305 DWARF4 CUs
  and the same producer in all units; it completed in 183.2 seconds.

## Approximate or producer-specific

- The generated C++ headers are deterministic structural stubs. Declarations, method names, and
  offsets are evidence, not proof of original method behavior or ABI-complete recompilation.
- The parser targets the exercised producer subset. The semantic index is broader than runtime
  reconstruction and is used to identify unsupported assumptions.

## Blocked or deferred

- No identified PS4 DWARF3 producer asset is available in the current evidence set.
- MSVC compilation and final Orbis/assembly loop-back require explicit external tool paths. The
  Orbis executable is present, but `uv run just sonar-validate` currently stops because
  `output/msvc-header-validation-20260801/compile_msvc.cmd` is absent.
