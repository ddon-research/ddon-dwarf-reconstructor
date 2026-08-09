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

Normal generation and knowledge export require a source-bound `--dwarf-store` manifest whose
complete projection has been loaded into Doris with `artifacts load-doris`. The manifest is
produced and published explicitly before lookup; missing, stale, incomplete, unavailable, or
source/count-mismatched stores fail closed. These commands query Doris only; Parquet remains the
canonical materializer output and JSONL remains an opt-in audit/interchange projection.

For a complete local store, the repository convention is
`output/analytical-dwarf/main/store-<source-sha16>/manifest.json`. Checkpoints and bounded probes
belong under `%TEMP%\ddon-analytical-dwarf` and require explicit incomplete-evidence flags.

## Artifact subcommands

```text
inspect
verify-source
inspect-elf
inspect-dwarf-dump
materialize-dwarf
inspect-dwarf-store
load-doris
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
compare-runtimes <elf>
profile-index <dump>
benchmark-dwarf-store <elf>
profile-dwarf-store <elf>
benchmark
history compare
history export
```

See the [performance reference](performance.md) for profiler choices, metric status semantics,
raw artifact boundaries, and the v1 history schema.

`benchmark-dwarf-store` accepts `--run-knowledge-export` for explicit complete export evidence;
the command writes the generated bundle and its deterministic tree hash under the external
benchmark artifact directory. For a database already loaded from the complete manifest, combine
`--query-existing-doris` to measure serving queries without reloading the canonical files or
rescanning the full Parquet projection.

`profile-dwarf-store` wraps that same benchmark through the shared performance runner. Use
repeatable `--profiler scalene` and `--profiler cprofile` options for line/memory and method CPU
evidence before changing Doris keys, indexes, buckets, or materialized views. Add
`--profiler scalene-libraries` for an optional standard-library/site-package comparison; it is a
broad diagnostic and is not included in `--profiler all`. The child benchmark report remains
separate from the profiler manifests.
