# External tool evidence

The reconstructor treats external inspection programs as one-time producers of durable evidence,
not as hidden runtime dependencies. A local tool is first captured with bounded `--version` and
`--help` output. A named profile then streams one output file for an immutable ELF/DWARF source.
The manifest records source identity, tool identity, profile arguments, output checksum, producer
authority, and deterministic artifact key.

## Adoption matrix

| Producer | Local/useful commands | Adopted profile | Authority | Boundary |
| --- | --- | --- | --- | --- |
| Sony Orbis 8.0 | `orbis-readelf`, `orbis-objdump`, `orbis-nm`, `orbis-addr2line` | `orbis-elf-headers`, `orbis-symbols` | PS4 ABI/SCE and symbols | Match the SDK to the target build; preserve exact target and flags |
| LLVM | `llvm-readelf`, `llvm-dwarfdump`, `llvm-debuginfo-analyzer` | `llvm-elf-metadata-json`, `llvm-dwarf-statistics`, `llvm-debug-info-summary` | Generic ELF/DWARF cross-check | Keep unknown SCE values and do not overwrite Orbis facts |
| GNU Binutils | `readelf`, `objdump`, `nm` | `gnu-elf-headers`, `gnu-symbols` | Generic ELF/symbol cross-check | GNU target naming can omit Orbis-specific ABI semantics |
| elfutils | `eu-readelf`, `eu-elflint` | `elfutils-elflint` | Generic integrity diagnostics | Diagnostics are not reconstructed layout |
| libdwarf | `dwarfdump` | `libdwarf-check-summary`, `libdwarf-check-all`, `libdwarf-producers` | DWARF integrity/producers | Summary is bounded; full output is capped and fails closed if oversized |
| pyelftools | In-process `ElfDwarfSession`/ELF evidence | Existing typed adapters | Structured parser foundation | No subprocess export; session owns normalization and handles |
| LIEF | Optional Python/C++ parser | Not in runtime dependency set | Exploratory comparison | Validate PS4 custom types/segments before adoption |
| OpenOrbis/readoelf | Reference source and Orbis ELF readers | Reference only | Comparative implementation evidence | Keep source/provenance; do not silently replace Sony output |
| elfldr | Loader/payload research | Not adopted | None for offline inspection | Never execute or ingest loader behavior in this workflow |

## Evidence contract

`ToolchainExporter` writes a versioned manifest and raw output under a content key. Reuse requires
validating the manifest schema, content key, source hash/size, output path confinement, output size,
and output SHA-256. Knowledge export accepts only complete manifests through repeated
`--tool-evidence` options. It emits additive `Tool`, `SourceArtifact`, and `Evidence` records and
retains the authority label; it does not mutate `Type`, `Field`, `Method`, producer, or source
location facts from DWARF.

Raw output is intentionally not parsed at every lookup. Index or graph ingestion should resolve
the `artifact_key` through the manifest catalog, inspect the producer-specific format, and retain
the original bytes. This keeps cold external scans separate from warm deterministic lookups and
allows an evidence producer to be replaced only by a new source/tool/profile identity.

## PS4 observations

The local PS4 ELF is ELF64 little-endian x86-64 with `ELFOSABI_FREEBSD`, Sony type `0xfe10`, and
SCE program-header values in the `0x61000000` range. Orbis `objdump -f` reports
`elf64-x86-64-freebsd`; generic LLVM/GNU readers accept the file but report generic x86-64 and
unknown/LOOS SCE values. This is why generic exports are cross-checks rather than ABI authority.

Use the goal handoff record to distinguish confirmed command output, approximate tool behavior,
blocked SDK/container prerequisites, and unresolved C++ semantics. Declarations and debug metadata
do not prove method bodies; disassembly remains a separate evidence producer.

## Validated handoff record

The PS4 `02020005` fixture has schema-1.1 exports for Orbis headers, LLVM JSON metadata, and the
libdwarf check summary. Their artifact keys are respectively
`696180705efd088147a1f83d5a4884fee9fa64bb36843610276d5fef63d42d70`,
`1a0e0536308627088e93dfffff43d1a4446b16384f92ff052bc413c3005a7182`, and
`fb52d4d01590587bc835de31ad7175714d363390a85215775115b7dff3f9b58c`. A warm rerun reused the
validated keys, and knowledge export projected all three as additive tool evidence. Raw outputs
remain under ignored local output directories and are joined by manifest key rather than copied
into every lookup.

The generic Compose image built and its LLVM JSON probe preserved `FreeBSD` OS/ABI and Sony type
`0xFE10`. This confirms container compatibility for inspection, not PS4 ABI authority; Orbis host
tools remain the matching-SDK authority.
