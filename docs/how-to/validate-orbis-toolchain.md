# Validate local Orbis CPU and ABI evidence

Use this workflow when a validation run needs repeatable evidence from the local Orbis SDK.
It is deliberately source-bound and offline: SDK outputs, compiler probe files, and performance
results belong in an external directory, never in the repository.

## Scope and prerequisites

The promoted host-tool contract is SDK `12.000`, selected by an explicit `--sdk-root`, then
`ORBIS_SDK_ROOT`, then the local default `D:\SCE\ORBIS SDKs\12.000`. SDK `8.000` remains an
explicit historical comparison profile. A run that combines recognized SDK 8 and SDK 12 tools
fails closed. This selection identifies the host tools; it does not prove that the target ELF was
built with SDK 12.

The reviewed local documentation is recorded by the contract without copying proprietary text:

```text
D:\SCE\ORBIS\documentation\chm\en\extracted\en\System\Compiling_Linking_and_Building\CPU_Assembler-Guidelines
D:\SCE\ORBIS\documentation\chm\en\extracted\en\System\Compiling_Linking_and_Building\CPU_Compiler_ABI-Overview
D:\SCE\ORBIS\documentation\chm\en\extracted\en\System\Generating_and_Using_Dynamic_Libraries\Sysmodule-Reference\ps4-module-ids.html
D:\SCE\ORBIS\documentation\chm\en\extracted\en\System\Analysis_and_Debugging\Machine_Code_Analyzer-Overview\analyzing-assembly-code-generated-by-the-compiler.html
```

The contract records AT&T syntax, the LLVM integrated assembler default, PS4 target and PIC
defaults, CFI/aranges and stack metadata, ABI register/stack/sret/variadic/TLS rules, the
`EF_FFUNC_DATA_SECS_ENABLED` flag, and the Orbis relocation definitions. These are documented
toolchain observations, not method-level ABI or semantic closure.

## Capture tool identities and source-bound exports

Start with the bounded profile inventory and tool probe:

```powershell
uv run ddon-dwarf-reconstructor artifacts list-tool-profiles
uv run ddon-dwarf-reconstructor artifacts probe-tool `
  'D:\SCE\ORBIS SDKs\12.000\host_tools\bin\orbis-bin.exe' `
  --output-dir 'C:\Users\morph\AppData\Local\Temp\ddon-orbis-tool-probes'
```

For a named ELF, publish the six additive SDK 12 `orbis-bin` observations:

```powershell
$elf = 'D:\ddon-dwarf-reconstructor\resources\DDOORBIS.elf'
$orbisBin = 'D:\SCE\ORBIS SDKs\12.000\host_tools\bin\orbis-bin.exe'
$evidence = 'C:\Users\morph\AppData\Local\Temp\ddon-orbis-sdk12-exports'

uv run ddon-dwarf-reconstructor artifacts export-tool-evidence $elf `
  --tool $orbisBin --profile orbis-bin-stack-sizes --output-dir $evidence
uv run ddon-dwarf-reconstructor artifacts export-tool-evidence $elf `
  --tool $orbisBin --profile orbis-bin-dynamic-symbols --output-dir $evidence
uv run ddon-dwarf-reconstructor artifacts export-tool-evidence $elf `
  --tool $orbisBin --profile orbis-bin-inline-relocations --output-dir $evidence
uv run ddon-dwarf-reconstructor artifacts export-tool-evidence $elf `
  --tool $orbisBin --profile orbis-bin-section-headers --output-dir $evidence
uv run ddon-dwarf-reconstructor artifacts export-tool-evidence $elf `
  --tool $orbisBin --profile orbis-bin-memory-layout --output-dir $evidence
uv run ddon-dwarf-reconstructor artifacts export-tool-evidence $elf `
  --tool $orbisBin --profile orbis-bin-file-layout --output-dir $evidence
```

The manifests bind source size/hash, tool size/hash/version, profile arguments, output size/hash,
and a confined output path. Stale, mismatched, duplicated, truncated, or path-escaping artifacts
are rejected before validation. `orbis-bin` is additive utility evidence: `orbis-objdump` remains
the canonical PS4 disassembler, and the SCE metadata reader remains authoritative for SCE RELA
and dynamic-tag interpretation.

## Retain compiler-generated ABI probes

Compile the post-optimization (`-O2`) ABI matrix with `-S` and `-c` outputs. The manifest retains
each source, command, compiler identity, assembly/object hashes, section metadata, CFI, debug
ranges, `.sce_stack_sizes`, `e_flags`, and status:

```powershell
uv run ddon-dwarf-reconstructor artifacts probe-compiler-abi `
  'D:\SCE\ORBIS SDKs\12.000\host_tools\bin\orbis-clang++.exe' `
  --orbis-readelf 'D:\SCE\ORBIS SDKs\12.000\host_tools\bin\orbis-readelf.exe' `
  --output-dir 'C:\Users\morph\AppData\Local\Temp\ddon-orbis-sdk12-probes'
```

Pass the resulting manifest to a source-bound validation run with repeated `--tool-evidence` and
`--abi-probe-manifest` options. Compiler acceptance demonstrates that the tool accepts the probe
shapes; it cannot promote a method's ABI, stack safety, or semantic equivalence.

The canonical byte-replay assembly profile remains the default. Use the opt-in `--assembly-profile
sectioned` only when validating `.text.<symbol>` layout and `EF_FFUNC_DATA_SECS_ENABLED`; it does
not change the default `.text` byte-replay contract.

The current implementation-validation report is schema `4.4`. In the bounded SDK 12 `rLayout`
acceptance, all 26 code-bearing methods retained target objects and canonical disassembly; 17
received `target_object_equivalent`, while 9 remained `not_promoted` because complete
source-bound return-type/ABI facts were unavailable. A schema-4.3 report is readable for history,
but its static-equivalence disposition is forced to `not_promoted`.

## Keep Sysmodule IDs separate from NIDs

`SysmoduleId` is the typed catalog of `sceSysmoduleLoadModule` loader constants from the local
`ps4-module-ids.html` table. It is not a dynamic library/module NID identity and is never consulted
by general NID resolution. `NidBinding.identity_kind` remains `sce_dynamic_tag`; opaque, explicit,
and community-derived NID evidence retain their own source and status.

## Optional performance-model evidence

Run `llvm-mca` only on a marked, post-compile assembly file. The result is performance-model
evidence, not ABI, correctness, or parity evidence:

```asm
# LLVM-MCA-BEGIN rLayout-load-sample
; compiler-generated instructions
# LLVM-MCA-END
```

```powershell
uv run ddon-dwarf-reconstructor performance analyze-assembly `
  'C:\Users\morph\AppData\Local\Temp\ddon-orbis-sdk12-mca\marked.s' `
  --tool 'D:\SCE\ORBIS SDKs\12.000\host_tools\bin\orbis-llvm-mca.exe' `
  --output-dir 'C:\Users\morph\AppData\Local\Temp\ddon-orbis-sdk12-mca\result' `
  --json --resource-pressure
```

The manifest records marker regions, input/tool hashes, command, tool version, output hash, and
status. Missing or overlapping markers, timeouts, truncation, and nonzero tool exits remain
explicit failures or blocked evidence.

## Repeat the 289-root disassembly parity run

The completed SDK 12 refactor acceptance is retained outside Git at
`C:\Users\morph\AppData\Local\Temp\ddon-disassembly-refactor-20260818`. Its four partitions are
73/73/73/70 roots in `baseline` and `post`; `baseline-config.json` records the source, complete
analytical-store manifest, tool identities, schema/configuration, and output policy. The strict
`disassembly-regression/1` manifests and `comparison.json` are generated only after all artifacts
are present.

The source is ELF SHA-256
`4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0`, the analytical-store
manifest is SHA-256 `bbe354bf3f838c8a1da6da501b9829a1bedf533f4834f0a4710dcbb574886078`, and the
promoted host profile is SDK `12.000` `orbis-objdump`/`orbis-as`. Both baseline and post manifests
have SHA-256 `db59e07ebaf34ccd582065223b79897b3a75bc64352343497c2f56519cda3533`; the comparison
is `matched` with zero differences. It records 289 roots, 2,745 headers, 83,754 method entries,
4,504 descriptors, 8,116 files, and 354,480,609 bytes.

The manifest comparator is intentionally stricter than a report-only comparison: it rejects missing,
extra, duplicate, truncated, path-escaping, source/tool-mismatched, or hash-mismatched artifacts,
and compares method identities, descriptors, headers, raw/canonical assembly, accepted objects,
context packets, bundles, and normalized object/relocation/NID/SCE/ABI/CFI/effects/parity facts.
Only the documented runtime-path/timing fields are normalized. SDK 8 remains historical evidence;
this run does not establish target build SDK, ABI closure, semantic equivalence, or live behavior.
