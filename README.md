# DDON DWARF Reconstructor

Reconstructs deterministic C++ class definitions from DWARF debug information in ELF files for
Dragon's Dogma Online research and modding.

## Features

- Complete type dependency and inheritance resolution across compilation units.
- PS4 DWARF 3/4 and PS3 DWARF 2 platform detection.
- Deterministic multi-file or legacy single-file header generation.
- Persistent source-bound symbol caches and streaming compressed-DWARF indexes.
- Knowledge-graph exports with explicit producer and Orbis evidence provenance.
- Typed CLI, locked uv dependencies, Ruff, Pyrefly, deptry, and just automation.

## Requirements and setup

- Regular CPython 3.14.6.
- `uv`.
- An ELF file with DWARF debug information for generation.

```text
uv sync --python 3.14.6
uv run just test-unit
```

The committed `[tool.pyrefly]` sections are the curated result of the Pyrefly migration. If a
fresh checkout reports a legacy editor mode, run `uv run pyrefly init` once against its
`pyproject.toml`, then retain the explicit project configuration and use the recommended Pyrefly
VS Code extension. Normal validation is `uv run just type-check`.

The standalone specification pipeline has its own dependency boundary:

```text
uv sync --directory tools/dwarf_spec_pipeline --python 3.14.6
uv run --directory tools/dwarf_spec_pipeline just check
```

## CLI usage

The packaged `ddon-dwarf-reconstructor` command is canonical. Symbols are supplied by repeating
`--symbol` or by using `--symbols-file`; comma-separated symbol values are no longer accepted.

```text
# One or more headers
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf --symbol MtObject
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf --symbol MtObject --symbol rLayout

# Full hierarchy and exhaustive root lookup
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf \
  --symbol rLayout --full-hierarchy --exhaustive

# Batch processing
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf \
  --symbols-file resources/season2-resources.txt --full-hierarchy

# Dump-assisted lookup
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf \
  --symbol rLayout --exhaustive \
  --dwarf-dump D:/research/DDON-binaries/DDOORBIS.elf.llvmdwarfdump.zst \
  --dwarf-index output/real-dump-index/DDOORBIS.elf.index.sqlite3

# Knowledge export
uv run ddon-dwarf-reconstructor export-knowledge resources/DDOORBIS.elf \
  --symbol rLayout --output-dir output/rLayout --build-id ps4-02020005 \
  --orbis-objdump 'D:/SCE/ORBIS SDKs/8.000/host_tools/bin/orbis-objdump.exe'
```

Use `uv run ddon-dwarf-reconstructor --help` or a command’s `--help` for the complete typed
interface. `--output`, `--verbose`, `--full-hierarchy`, `--single-file`, `--exhaustive`,
`--dwarf-dump`, `--dwarf-index`, and `--resolve-param-names` remain generation options.

## Durable artifact operations

Artifact maintenance is grouped under the root command and is intentionally explicit:

```powershell
uv run ddon-dwarf-reconstructor artifacts inspect `
  --elf resources/DDOORBIS.elf `
  --dwarf-dump D:/research/DDON-binaries/DDOORBIS.elf.llvmdwarfdump.zst `
  --dump-index output/real-dump-index/DDOORBIS.elf.index.sqlite3

uv run ddon-dwarf-reconstructor artifacts verify-source resources/DDOORBIS.elf
uv run ddon-dwarf-reconstructor artifacts repair-dump-index D:/research/DDON-binaries/dump.zst
uv run ddon-dwarf-reconstructor artifacts rebuild-dump-index D:/research/DDON-binaries/dump.zst
uv run ddon-dwarf-reconstructor artifacts repair-catalog
```

`purge-dump-index` requires `--confirm-index-path` containing the exact resolved sidecar path.
Repair, rebuild, and purge operations never broaden their target beyond the explicitly selected
artifact. The former `ddon-dwarf-artifacts` executable is intentionally removed.

## DWARF dump and cache behavior

The first dump-assisted exhaustive lookup can build a durable SQLite sidecar from the compressed
dump in one streaming pass. Subsequent fresh processes reuse source-bound indexes and symbol
caches. Preserve these artifacts locally; routine cleanup must not delete validated indexes or
exports. The full PS4 dump is more than 30 GB expanded, so real-asset work is opt-in and should use
the local acceptance paths documented in [TESTING.md](docs/TESTING.md).

## Development automation

`just` is the single task-runner source of truth. Every recipe invokes tools through the project’s
locked uv environment:

```text
uv run just                 # list recipes
uv run just sync
uv lock --check
uv run just test-unit       # fast tests
uv run just test            # non-performance suite
uv run just check           # Ruff, Pyrefly, deptry, structure, boundaries
uv run just coverage        # coverage thresholds and reports
uv run just package         # wheel and sdist
uv run just native-build    # optional Nuitka executable
uv run just spec-check      # nested project checks
```

The normal change loop is:

```text
uv run just test-unit
uv run just check
uv run just test
```

The root Pyrefly configuration checks `src` and operational `scripts`; the nested project checks
its own `src`. Pyrefly is authoritative for typing, deptry validates dependency declarations, and
focused Prospector diagnostics remain a non-blocking audit.

## Architecture and testing

- [Architecture](docs/ARCHITECTURE.md)
- [Component diagram](docs/COMPONENT_DIAGRAM.md)
- [Generation flows](docs/GENERATION_FLOWS.md)
- [Testing and acceptance tiers](docs/TESTING.md)
- [DWARF tag analysis](docs/DWARF_TAG_ANALYSIS.md)
- [DWARF specification pipeline](tools/dwarf_spec_pipeline/README.md)

Generated headers and evidence bundles are wire-format contracts. Validate them with exact
byte-level output manifests across fresh and warm processes. Real ELF, compressed dumps, compiler
validation, and performance tests require explicit local paths and never commit proprietary inputs
or generated runtime artifacts.

## License

GPLv3-or-later; see [LICENSE](LICENSE).
