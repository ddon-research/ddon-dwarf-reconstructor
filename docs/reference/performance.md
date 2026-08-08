# Performance command reference

The `performance` group is the canonical opt-in resource and profiler interface:

| Command | Purpose |
| --- | --- |
| `performance doctor` | Probe tools and report evidence paths |
| `performance profile <elf>` | Run a named profiler around the canonical reconstruction CLI |
| `performance compare-runtimes <elf>` | Compare regular CPython, a validated Nuitka launcher, and optional free-threaded CPython |
| `performance profile-index <dump>` | Profile a complete compressed-dump index rebuild |
| `performance benchmark-dwarf-store <elf>` | Materialize typed Parquet and collect native Doris evidence |
| `performance profile-dwarf-store <elf>` | Run the analytical-store benchmark through Scalene, cProfile, or another supported profiler |
| `performance profile-materializer <elf>` | Profile an isolated bounded direct-Parquet materializer probe |
| `performance benchmark` | Run the deterministic fixture through pyperf and psutil |
| `performance history compare` | Compare compatible historical runs |
| `performance history export` | Write deterministic JSON, CSV, and Markdown |

`profile` accepts repeatable `--profiler` values: `scalene`, `cprofile`, `pyinstrument`, `py-spy`,
and `tracemalloc`. Use `--profiler all` for the four cross-check profilers except tracemalloc;
request tracemalloc explicitly when Python allocation snapshots are needed. Missing tools are
recorded as `unavailable`; timeout or child failures are `partial`.

`profile-index` wraps `artifacts rebuild-dump-index` and records the compressed dump as the source
identity. It defaults to the low-overhead process sampler; request a profiler explicitly for a
deep index-build trace. Its sidecar and raw profile must be placed outside source control.

`benchmark-dwarf-store` materializes every CU once into the direct typed Parquet sink when no
manifest is supplied, then records counts, unresolved references, wall time, CPU/RSS/I/O metadata, artifact sizes, projection rows,
and cold/warm query observations in an external `benchmark-report.json`. The related query suite
includes CU/DIE offset lookup, parent/child traversal, inheritance, field layout, references, and
method implementation by declaration reference. Add
`--run-current-baseline` to measure the prior live pyelftools lookup path. The live baseline is
opt-in because it may perform a full scan. A baseline or backend that was not actually run is marked
`not_observed`, `unavailable`, or `blocked`; it is never silently promoted to acceptance evidence.
Doris execution is opt-in with `--run-doris`. After a complete native load, use
`--query-existing-doris --skip-file-queries` to run the same serving-backend
query suite without reloading files or repeating the full Parquet scan. `--run-doris` and
`--query-existing-doris` are mutually exclusive. Add `--run-knowledge-export` to run the complete
store-backed knowledge-export workflow for the selected symbols and record output hashes; this
also remains explicit because it writes a potentially large external bundle.

Use `profile-dwarf-store` for CPU attribution around that same bounded command. It invokes the
unprofiled `benchmark-dwarf-store` child through `PerformanceRunner`, so process CPU/RSS/I/O
metrics, cProfile method totals, and Scalene Python/native line and memory attribution remain
separate evidence surfaces:

```powershell
uv run ddon-dwarf-reconstructor performance profile-dwarf-store <ELF> `
  --store-manifest <complete-manifest.json> `
  --output-dir $env:TEMP/ddon-analytical-dwarf/profiled-doris-query `
  --query-existing-doris --skip-file-queries `
  --symbol rLayout --symbol MtObject --iterations 5 `
  --profiler scalene --profiler cprofile
```

Scalene/cProfile measure the Python client and orchestration only; Doris backend CPU, scanned
bytes/rows, tablet pruning, spills, and operator time must come from the matching Doris CLI
`EXPLAIN` and `profile get --full` records. Do not infer a database index change from a Python
hotspot or from a profiler run that failed to publish line attribution.

Use `profile-materializer` before changing Parquet batching, writer rotation, or DWARF row
conversion. It runs each requested profiler against a separate bounded target directory using the
same family layout, writer limit, and CU-boundary rotation as production:

```powershell
uv run ddon-dwarf-reconstructor performance profile-materializer <ELF> `
  --output-dir $env:TEMP/ddon-analytical-dwarf/profiled-materializer `
  --max-cus 8 --max-open-writers 16 --rotate-writers-every-cus 64 `
  --profiler cprofile --profiler scalene --profiler py-spy
```

The command is diagnostic only. Its bounded outputs are not generation, Doris, or CU-completeness
inputs; use cProfile method totals and py-spy line stacks for CPU localization, and treat Scalene
as non-actionable when Windows/CPython reports only profiler or launcher attribution.

For a long traversal that was started with `--checkpoint-every-cus N`, a diagnostic benchmark can
read the latest committed snapshot while the producer continues:

```powershell
uv run ddon-dwarf-reconstructor performance benchmark-dwarf-store <ELF> `
  --store-manifest <checkpoint.json> --allow-incomplete `
  --output-dir $env:TEMP/ddon-analytical-dwarf/checkpoint-benchmark
```

This is deliberately a partial report. It uses the checkpoint's immutable Parquet file list,
never open parts, and skips Doris. It is useful for schema/query sanity checks, not
for CU coverage or the final runtime acceptance gate.

The `performance-profile-index-traces` recipe runs the process sampler, cProfile, Scalene, and
pyinstrument as separate complete cold rebuilds under an external artifact root. Use it for the
algorithm audit; do not use profiler timings as an uninstrumented performance baseline.

`profile` accepts `--python-executable` for an alternate installed CPython and `--launcher` for a
compiled application executable. `compare-runtimes` uses both forms through the same typed runner,
records runtime implementation/version/GIL state in the manifest and SQLite row, and rejects a
Python executable that cannot import the installed project. Use the venv interpreter for a
free-threaded environment, not the bare uv-managed base interpreter.

The current comparison is report-only. On the measured warm `rLayout` workload, regular CPython
3.14.6 averaged 2.062 seconds, Nuitka 4.1.3 onefile 2.470 seconds, and free-threaded CPython
2.202 seconds. Nuitka reduced peak RSS but added onefile extraction I/O; free-threaded CPython
used more RSS. The current pyinstrument native extension also enables the GIL when imported by a
free-threaded interpreter. See the [runtime comparison how-to](../how-to/compare-runtimes.md) for
the exact setup and compatibility boundary.

## Metric contract

The process runner samples the complete child process tree with psutil. It records wall time, CPU
user/system seconds, peak RSS/VMS, read/write bytes and operation counts, sample count, and bounded
capture indicators. `tracemalloc` current/peak values are separate `traced_*` metrics and must not
be interpreted as total process RSS.

## Artifact contract

Raw profiles (`.json`, `.prof`, Speedscope), sample streams, and bounded child output live under
`DDON_PERFORMANCE_ARTIFACT_DIR` or the OS-local temporary default. On Windows the default is
`%TEMP%\ddon-dwarf-reconstructor\performance`; this keeps large real-asset evidence on the local
temporary volume rather than durable app data. Each run manifest records the external path, size,
SHA-256, tool version, format, and evidence status. The tracked database stores only summaries,
method aggregates, and checksummed references.

Scalene is run in its non-browser JSON mode. If an HTML view is needed, render the retained JSON
offline with `scalene view --html`; the profiling workflow does not enable web output or network
suggestions.

## History schema

The v1 SQLite schema is defined in the repository feature artifact
`specs/016-performance-profiling/schema.md`.
Exports are generated at:

- `resources/performance/benchmarks.sqlite3`
- `resources/performance/benchmark-history.json`
- `resources/performance/benchmark-history.csv`
- `docs/knowledge-base/performance/benchmark-history.md`

Use the exact `just` recipes for installation and repeatability; do not introduce an ad-hoc shell
wrapper or a second benchmark history store.
