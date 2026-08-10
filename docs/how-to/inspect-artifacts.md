# Inspect durable artifacts

Artifact commands are read-only or explicitly named maintenance operations. They expose the
source catalog, symbol cache, compressed-dump index, ELF/DWARF facts, and external-tool evidence
without mixing diagnostics into JSON stdout.

```powershell
uv run ddon-dwarf-reconstructor artifacts inspect --elf resources/DDOORBIS.elf
uv run ddon-dwarf-reconstructor artifacts verify-source resources/DDOORBIS.elf
uv run ddon-dwarf-reconstructor artifacts inspect-elf resources/DDOORBIS.elf
uv run ddon-dwarf-reconstructor artifacts inspect-dwarf-dump <LLVM-DWARF-DUMP.zst>
uv run ddon-dwarf-reconstructor artifacts inspect-dwarf-store <STORE-MANIFEST.json>
uv run ddon-dwarf-reconstructor artifacts list-tool-profiles
```

Complete analytical stores normally live under
`output/analytical-dwarf/main/store-<source-sha16>/manifest.json`; inspect that manifest for
generation or serving evidence. `%TEMP%\ddon-analytical-dwarf` is reserved for checkpoints,
bounded probes, profiler output, and crash diagnostics. Temp checkpoints and bounded stores require
`--allow-incomplete` and must not be treated as complete coverage or runtime inputs.

For the local LLVM DWARF cross-check on Windows, use the MSYS2 UCRT64 profile at
`C:\msys64\ucrt64.exe`. The non-interactive equivalent keeps `MSYSTEM=UCRT64` and resolves
`llvm-dwarfdump` from `/ucrt64/bin`; it is the same UCRT64 environment launched by the profile
executable:

```powershell
$env:MSYSTEM = "UCRT64"
& C:\msys64\usr\bin\bash.exe --login -lc `
  'llvm-dwarfdump --statistics /d/ddon-dwarf-reconstructor/resources/DDOORBIS.elf'
& C:\msys64\usr\bin\bash.exe --login -lc `
  'llvm-dwarfdump --verify /d/ddon-dwarf-reconstructor/resources/DDOORBIS.elf'
& C:\msys64\usr\bin\bash.exe --login -lc `
  'llvm-dwarfdump --verify-json=/c/Users/morph/AppData/Local/Temp/ddon-analytical-dwarf/verify.json /d/ddon-dwarf-reconstructor/resources/DDOORBIS.elf'
```

Capture these outputs outside the repository and record their exit status. A verifier diagnostic
is useful evidence about the input but is not permission to discard records from the canonical
store.

For a toolchain investigation, probe first and export only a named profile:

```powershell
uv run ddon-dwarf-reconstructor artifacts probe-tool <tool> --output-dir output/tool-probes
uv run ddon-dwarf-reconstructor artifacts export-tool-evidence <elf> `
  --tool <tool> `
  --profile <profile> `
  --output-dir output/tool-exports
```

Orbis tools are authoritative for validated PS4 ABI/SCE semantics. LLVM, GNU, elfutils,
libdwarf, pyelftools, LIEF, and OpenOrbis outputs are additive until PS4 behavior is validated.
`elfldr` is loader research only and is not executed by offline ingestion.

## Repair versus rebuild

`repair-dump-index`, `repair-catalog`, and `repair-symbol-cache` are targeted recovery actions.
`rebuild-dump-index` performs a complete streaming scan and atomically publishes a new index.
`purge-dump-index` deletes one named index only after exact-path confirmation. Read the command
help before using maintenance commands against a large input.

The [durable artifact reference](../reference/artifacts.md) explains identity keys, reuse, and
publication invariants.
