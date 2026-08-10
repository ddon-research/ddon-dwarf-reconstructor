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
benchmark-doris-current <elf>
benchmark-doris-optimization <elf>
benchmark-doris-flight
check-doris-flight
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

`benchmark-doris-current` reuses a complete source-bound publication. The
`benchmark-doris-optimization` command adds redacted generation query tracing, typed serving-variant
identity, selective-statistics policy, and one-factor lookup/physical candidates. Runtime-only
variants such as `typed-projections`, `reference-prefetch-lazy`, and
`targeted-child-tag-filter` reuse the canonical tables; lookup candidates require explicit
`--provision-candidate`. No candidate changes the canonical fourteen-family contract. Use the
command's `--help` surface for the cold/warm repetition and profile-budget controls.

To repeat the measured interaction batch of all positive standalone candidates, use
`--candidate combined-positive-below-gate --provision-candidate`. It activates lazy reference
prefetch, the decoded-serving projection, and source/name lookup buckets 2/4/8 with b8 active;
the other buckets are provisioned as comparison-only alternatives. The measured batch is now the
promoted generation serving path. Normal canonical loading creates and refreshes
`dwarf_records_opt_name_b8`, and normal generation uses lazy prefetch and the serving projection
without environment switches. Raw attribute columns remain retained in Doris for exact evidence;
the complete Season 2 run has now validated the narrowed generation projection for all 289 roots.

For per-header compiler acceptance, run the external MSVC validator against each published bundle
root. It creates one translation unit per header and writes the structured report outside the
repository; warning-only diagnostics are retained while compiler failures are non-zero evidence:

```powershell
uv run python -m tools.sonar.validate_header_bundle `
  --input-root $env:TEMP/ddon-analytical-dwarf/season2-msvc-fix4-20260810-input `
  --validation-directory $env:TEMP/ddon-analytical-dwarf/msvc-season2-fix4-20260810
```

This validator is a change-triggered acceptance tool, not part of normal generation. A clean
compiler report proves syntax and generated-closure integrity; it does not replace source-bound
manifest checks, ordered-output hashes, or separate IDA/Sonar evidence.

The 2026-08-09/10 complete-store run measured the live generator path. Bounded source/unit-aware
hydration produced exact exhaustive `rAIFSM` output; the post-policy canonical run measured
`16.1152/16.1187 s` warm p50/p95 for the promoted combined path, versus
`19.1208/19.1271 s` for the prior canonical path. Child-frontier/reference prefetching and
line-program caching are included in the serving algorithm. The canonical fourteen-family schema,
keys, indexes, storage, and registry row contract remain unchanged; the b8 auxiliary table is
created and populated during canonical load. The targeted child-tag filter regressed warm p50 by
10.5% and is rejected. MV, index, bucket, storage-format, session, and Stream Load variants remain
`not_observed` unless their trace gate is met. This command is a reusable, change-triggered
one-shot regression/promotion tool, not a continuous service.

`DDON_DORIS_HYDRATION_SCOPE=global` is the canonical setting. A fair-path `unit` screen preserved
exact `rAIFSM` output but took `289.048 s` versus the canonical `19.121/19.127 s` warm p50/p95;
its partial trace showed 26,463 observations and is recorded as a rejected query-fan-out
candidate, not a serving default.

`check-doris-flight` is the explicit preflight for the optional Flight SQL overlay. It records
Compose-file and rendered-configuration hashes, FE/BE endpoint reachability, and bounded startup
log markers. Run it with `uv run --group flight-sql` before
`benchmark-doris-flight`; the latter compares the default PyMySQL row path with ADBC qmark queries,
Arrow table/RecordBatch consumption, a reducer, and bounded hydration batches. Neither command
changes the default MySQL/DDL/Stream Load path. Because the current Doris producer rejects prepared
statement parameter exchange, the benchmark-only
`--allow-unparameterized-flight-fallback` flag can be combined with
`--reused-connections-only` to render checked literals for a diagnostic run; its report remains
`partial` and is not a runtime fallback.
