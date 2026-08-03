# Binary inspection toolchain

This Compose project provides a reproducible, non-proprietary baseline for one-time ELF/DWARF
exports. The image contains GNU Binutils, LLVM, elfutils, libdwarf headers, Python, pyelftools,
`file`, and `zstd`. It deliberately does not redistribute Sony Orbis SDK binaries or attempt SELF
decryption, signing, loading, or execution.

The host-specific Orbis tools remain the PS4 ABI authority. Mount an approved SDK directory only
when an explicit local command needs it; generic tools in this image are additive cross-checks.

## Build and inspect

```powershell
docker compose -f tools/binary_toolchain/compose.yaml build
docker compose -f tools/binary_toolchain/compose.yaml run --rm binary-toolchain
docker compose -f tools/binary_toolchain/compose.yaml run --rm binary-toolchain \
  llvm-readelf --elf-output-style=JSON --file-header --program-headers --sections \
  /inputs/DDOORBIS.elf > output/toolchain/llvm-elf-metadata.json
```

The default mounts map `resources/` to `/inputs` and `output/toolchain/` to `/output`. Set
`DDON_TOOLCHAIN_INPUT_DIR` and `DDON_TOOLCHAIN_OUTPUT_DIR` to explicit absolute host paths when
using external binary locations. Keep proprietary inputs and raw outputs outside Git.

For the application-level manifest and cache policy, use the canonical host command:

```text
uv run ddon-dwarf-reconstructor artifacts list-tool-profiles
uv run ddon-dwarf-reconstructor artifacts probe-tool <path-to-tool> --output-dir output/tool-probes
uv run ddon-dwarf-reconstructor artifacts export-tool-evidence resources/DDOORBIS.elf \
  --tool <path-to-tool> --profile llvm-elf-metadata-json --output-dir output/tool-exports
```

Each export is staged and atomically published under a SHA-256 key covering the source, tool,
profile, arguments, output format, and authority. Its manifest and output are revalidated before
knowledge export. `--tool-evidence <manifest>` attaches the validated export to a knowledge
bundle as additive provenance nodes; it does not overwrite deterministic DWARF layout facts.

## ABI and tool roles

| Source | Role | Constraint |
| --- | --- | --- |
| Orbis `readelf`/`objdump`/`nm` | PS4 ABI, SCE program types, symbols, instructions | Use the matching SDK and pin the executable hash |
| LLVM | JSON ELF metadata and DWARF statistics/summary | Generic ELF interpretation; preserve unknown SCE values |
| GNU Binutils | Independent ELF/symbol cross-check | Not authoritative for Orbis-specific semantics |
| elfutils/libdwarf | Integrity and producer/reference diagnostics | Diagnostics are evidence, not reconstructed layout |
| pyelftools | In-process typed ELF/DWARF parser | Existing application parser remains the structured source |
| LIEF | Optional exploratory parser | Do not add it to the runtime path until PS4 ABI behavior is validated |
| OpenOrbis/readoelf | Reference implementation and comparison source | Record provenance; do not silently replace Orbis outputs |
| elfldr | Loader/runtime research only | Out of scope for offline inspection and never executed here |
