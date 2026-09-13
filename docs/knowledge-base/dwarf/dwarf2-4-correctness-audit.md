# DWARF 2-4 correctness audit

## Current conclusion

The available DDON platform evidence is consistent and specific:

| Artifact | Result |
| --- | --- |
| PS4 `DDOORBIS.elf` | ELF64, little-endian, `EM_X86_64`, `ELFOSABI_FREEBSD`, Sony type `0xfe10` |
| PS4 ELF DWARF units | 2,305 compilation units; all report DWARF4 |
| PS4 ELF producer | `clang version 3.5.0 (PS4 clang version 2.50.0.2333)` in all 2,305 top-level CUs |
| PS4 languages | 2,245 C++ units (`DW_LANG_C_plus_plus`) and 60 C99 units |
| PS4 LLVM text dump | Full streaming scan reports 2,305 DWARF4 CUs and the same producer in all units (183.2 s) |
| Orbis header inspection | Orbis binutils 8.00.0.398 identifies the file as `elf64-x86-64-freebsd` |
| PS3 comparison ELF | ELF64 big-endian `EM_PPC64`; all 1,092 units report DWARF2 and the SN Systems PS3 producer |

Therefore the old shorthand “PS4 DWARF3/4” was too broad as a producer claim. The runtime parser
keeps a DWARF2-4 compatibility contract, but the primary PS4 acceptance baseline is DWARF4.
DWARF3 remains specification/fixture coverage until a matching producer asset is identified.

## Normative relationships recovered from the specifications

The generated [semantic index](../dwarf-specification/generated/semantic-index.md) is derived from
the checked-in DWARF2, DWARF3, and DWARF4 JSON artifacts. It confirms:

- `DW_AT_containing_type` is a `reference` and is applicable to `DW_TAG_ptr_to_member_type`; it is
  not listed as applicable to `DW_TAG_class_type`.
- `DW_AT_specification` and `DW_AT_abstract_origin` are separate reference relationships. The
  former links an out-of-line definition to a declaration; the latter supplies omitted information
  for abstract/concrete inline instances. The parameter-name lookup intentionally uses only the
  former.
- `DW_AT_high_pc` is an `address` in DWARF2/3 and can be `address, constant` in DWARF4. A DWARF4
  constant `high_pc` is an offset from `low_pc`, not automatically an absolute address.
- `DW_AT_data_member_location` may be a block/expression or a constant depending on the version;
  expression operands must be decoded rather than treated as a one-byte offset.
- The DWARF `flag` class represents presence/absence. Attribute presence is evidence even when a
  producer uses `DW_FORM_flag_present`.

## Refactoring findings

The audit repaired these concrete issues:

1. `DW_OP_plus_uconst` location operands now decode ULEB128, including byte-block values and
   `DW_OP_constu`, instead of truncating operands at one byte.
2. General type resolution now preserves `volatile` and `restrict` qualifier DIEs, matching the
   classifier and primitive resolver.
3. Method implementation scoring accepts `DW_AT_ranges` as code-location evidence for noncontiguous
   implementations.
4. Reference matching resolves the target DIE before comparing offsets, so CU-relative
   `DW_FORM_ref4` values are not compared as if they were section-wide offsets.
5. The `rLayout` authority manifest no longer claims that `DW_AT_containing_type` proves a class
   definition. It uses direct DIE identity and structural evidence instead.
6. Explicit evidence commands were added for all-CU ELF headers/producers and streaming LLVM dump
   headers/producers. They are opt-in and do not add a full scan to ordinary generation.

## Header-to-implementation follow-up boundary

Header discovery and implementation discovery are now separate chains. A normal header run keeps
the existing `HeaderBundle` contract and does not invoke an assembly producer. An opt-in
`generate --extract-assembly` run first commits the header bundle and then performs a second,
additive traversal. All symbol requests perform one union discovery and write
`implementation-report.json` plus flat resource/shared `.asm` files below
`generated/ps4-<client-version>/` (or the explicit output root) when context generation is
enabled. These assembly artifacts are not
merged into header contents or used to promote header completeness.

The follow-up retains method DIE and CU offsets, containing-class identity, linkage names, and the
declaration-to-definition relation. It returns all source-bound `DW_AT_specification` and
`DW_AT_abstract_origin` candidates, with a bounded source scan after a complete analytical-index
miss. Code ranges use validated `DW_AT_low_pc`/`DW_AT_high_pc` pairs or materialized/decoded
`DW_AT_ranges` records. Orbis instructions are selected only for a unique function whose symbol
start exactly matches a DWARF range, or whose complete symbol range is contained by one range.
`matched`, `ambiguous`, `unsupported`, `not_observed`, `unavailable`, and `partial` remain
explicit report states.

This is assembly/disassembly evidence, not recovered C++ source or proof of inline-assembly
semantics. A method with no standalone executable range, an unresolved range base, an unavailable
Orbis executable, or competing definitions remains unobserved/unsupported rather than being
assigned a plausible body. Only unique matches receive readable evidence and, under the explicit
source-emission profile, exact-byte `.s`/`.o` artifacts; this pipeline does not emit `.cpp` files. The
read-only validator separately evaluates explicit address policy, relocation/NID evidence,
DWARF ABI/CFI context, instruction effects, Orbis target objects, and static parity. The
canonical JSON report retains raw method text, decoded bytes, references, hashes, and explicit
limitations; the optional bundle manifest only proves atomic publication. Header byte parity and
standalone compiler closure remain independent acceptance gates. CFG/external-edge parity and
live PS4 behavior remain separately reported and are not inferred from compilation.

## Reproducible commands

```text
uv run ddon-dwarf-reconstructor artifacts inspect-elf <PS4-ELF>
uv run ddon-dwarf-reconstructor artifacts inspect-dwarf-dump <LLVM-DWARF-DUMP.zst>
uv run --directory tools/dwarf_spec_pipeline dwarf-spec-pipeline audit \
  --output-dir ../../docs/knowledge-base/dwarf-specification/generated --source-root ../../src
uv run --directory tools/dwarf_spec_pipeline dwarf-spec-pipeline validate \
  --output-dir ../../docs/knowledge-base/dwarf-specification/generated
uv run just test-unit
uv run just check
uv run just test
uv run just coverage-ci
uv run just audit
```

The ELF and dump commands require explicit local paths. The dump command streams compressed text
and retains only bounded counters. Do not place the ELF, expanded dump, sidecar, generated headers,
or logs in source control.

## Remaining uncertainty and loop-back boundary

- DWARF describes compiler-produced structure and selected source metadata; it does not recover the
  unavailable original C++ behavior or prove that a generated declaration is recompilable.
- MSVC compilation and Sonar/assembly comparison remain external validation stages for final header
  stubs. A passing parser test is not behavioral proof.
- On 2026-08-03, `prepare_msvc_analysis.py` generated five standalone translation units and
  `compile_msvc.cmd`; `uv run just sonar-validate` and strict `uv run just sonar-capture` passed,
  producing a validated five-entry MSVC compilation database. The generated aggregate unit remains
  optional evidence because it reports duplicate declarations across independent header closures.
- The documented Orbis tool exists at `D:\SCE\ORBIS SDKs\8.000\host_tools\bin\orbis-objdump.exe`.
  A final assembly/disassembly comparison is still separate acceptance evidence. The local profile
  attempts retain resolved calls/branches, RIP-relative data, source discriminators, file offsets,
  and explicit `-S`/debug unavailability; they do not establish ABI or behavioral equivalence.
  Conventional Orbis relocation output is empty, the Orbis dynamic-relocation option is
  unavailable, and PS4/SCE relocation metadata is present and decoded by the source-bound
  `OrbisSceMetadataReader`. The complete SCE tables are cache evidence, not applied relocations.
- DWARF3 is indexed and tested as a compatibility vocabulary, but no identified PS4 producer asset
  in this checkout establishes a DWARF3 target baseline.
- The implementation supports the exercised producer subset, not every tag/form/operation in the
  normative specifications. Unsupported or ambiguous evidence must remain explicit rather than be
  silently promoted to a complete relationship.
- Inline instances without a unique standalone Orbis function are not yet reconstructed as source
  inline assembly. Overload/thunk/clone classification beyond unique range identity remains an
  additive follow-up, and no live PS4 Orbis extraction is claimed until a retained tool/source
  evidence manifest exists.

## Source provenance

- `resources/DDOORBIS.elf.readelf.headers.txt` and the external PS4 ELF establish ELF identity and
  section evidence.
- `resources/PS3/EBOOT.ELF.readelf.headers.txt` establishes the checked-in PS3 comparison header.
- `docs/knowledge-base/dwarf-specification/generated/dwarf{2,3,4}.json` and
  `semantic-index.json` establish the normalized specification facts.
- `src/ddon_dwarf_reconstructor/infrastructure/elf_evidence.py` and
  `zstd_dump_evidence.py` define the repeatable evidence surfaces.
- `tools/sonar/prepare_msvc_analysis.py` generates the local MSVC/Sonar translation units,
  wrapper command, input manifest, and validated compilation database.
