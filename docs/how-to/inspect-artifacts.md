# Inspect durable artifacts

Artifact commands are read-only or explicitly named maintenance operations. They expose the
source catalog, symbol cache, compressed-dump index, ELF/DWARF facts, and external-tool evidence
without mixing diagnostics into JSON stdout.

```powershell
uv run ddon-dwarf-reconstructor artifacts inspect --elf resources/DDOORBIS.elf
uv run ddon-dwarf-reconstructor artifacts verify-source resources/DDOORBIS.elf
uv run ddon-dwarf-reconstructor artifacts inspect-elf resources/DDOORBIS.elf
uv run ddon-dwarf-reconstructor artifacts inspect-dwarf-dump <LLVM-DWARF-DUMP.zst>
uv run ddon-dwarf-reconstructor artifacts list-tool-profiles
```

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
