# CLI reference

The supported entry point is:

```powershell
uv run ddon-dwarf-reconstructor [OPTIONS] COMMAND [ARGS]...
```

| Command | Purpose |
| --- | --- |
| `generate` | Generate deterministic C++ headers for one or more symbols. |
| `export-knowledge` | Export deterministic evidence as a knowledge bundle. |
| `artifacts` | Inspect and maintain source catalogs, indexes, caches, and tool evidence. |
| `performance` | Collect opt-in resource/profiler evidence and maintain benchmark history. |

## Generation and export

```powershell
uv run ddon-dwarf-reconstructor generate --help
uv run ddon-dwarf-reconstructor export-knowledge --help
```

Common inputs are an ELF path, one or more `--symbol` values or a `--symbols-file`, an optional
`--full-hierarchy`, and an output directory. Use the help surface from the locked environment for
the complete option list; this page intentionally documents stable commands rather than copying
Typer's formatting.

## Artifact subcommands

```text
inspect
verify-source
inspect-elf
inspect-dwarf-dump
list-tool-profiles
probe-tool
export-tool-evidence
repair-dump-index
rebuild-dump-index
repair-catalog
repair-symbol-cache
purge-dump-index
```

Every maintenance command has an explicit target and confirmation contract. Use
`uv run ddon-dwarf-reconstructor artifacts --help` and the individual subcommand help before
operating on a large or durable artifact.

## Performance subcommands

```text
doctor
profile <elf>
profile-index <dump>
benchmark
history compare
history export
```

See the [performance reference](performance.md) for profiler choices, metric status semantics,
raw artifact boundaries, and the v1 history schema.
