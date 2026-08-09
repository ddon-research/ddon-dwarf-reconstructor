# Performance command reference

The `performance` group is the canonical opt-in resource and profiler interface:

| Command | Purpose |
| --- | --- |
| `performance doctor` | Probe tools and report evidence paths |
| `performance profile <elf>` | Run a named profiler around the canonical reconstruction CLI |
| `performance compare-runtimes <elf>` | Compare regular CPython, a validated Nuitka launcher, and optional free-threaded CPython |
| `performance profile-index <dump>` | Profile a complete compressed-dump index rebuild |
| `performance benchmark-dwarf-store <elf>` | Materialize typed Parquet and collect native Doris evidence |
| `performance benchmark-doris-current <elf>` | Benchmark the existing complete manifest and live Doris path without materializing or loading |
| `performance check-doris-flight` | Check the opt-in Flight overlay, endpoints, hashes, and startup logs |
| `performance benchmark-doris-flight` | Compare PyMySQL rows with ADBC Flight SQL consumption modes |
| `performance profile-dwarf-store <elf>` | Run the analytical-store benchmark through Scalene, cProfile, or another supported profiler |
| `performance profile-materializer <elf>` | Profile an isolated bounded direct-Parquet materializer probe |
| `performance benchmark` | Run the deterministic fixture through pyperf and psutil |
| `performance history compare` | Compare compatible historical runs |
| `performance history export` | Write deterministic JSON, CSV, and Markdown |

`profile` accepts repeatable `--profiler` values: `scalene`, `scalene-libraries`, `cprofile`,
`pyinstrument`, `py-spy`, and `tracemalloc`. Use `--profiler all` for the four normal cross-check
profilers except tracemalloc. `scalene-libraries` is an explicit broad diagnostic and is not part
of `all`; request tracemalloc explicitly when Python allocation snapshots are needed. Missing tools are
recorded as `unavailable`; timeout or child failures are `partial`.

## Linux container contract

`ops/reconstructor/compose.yaml` provides the explicit Linux/amd64 profiling environment. It pins
CPython 3.14.7 and uv 0.12.3, installs the default analytical runtime plus the locked `test` and
`performance` groups into an image-local `/opt/venv`, and bind-mounts the source read-only. `/workspace/output` and
`/workspace/logs` publish normal application artifacts; `/artifacts` publishes profiler output,
DWARF cache files, history databases, and exported reports. Use a separate history database under
`/artifacts/history` so container runs cannot mutate the tracked ledger.

The normal service has no additional Linux capability. The `reconstructor-py-spy` service is
available only through the `py-spy` Compose profile and adds `SYS_PTRACE` for child-process stack
inspection. The optional `reconstructor-doris` service joins the existing analytical Compose
network; its `reconstructor-doris-py-spy` variant combines both profiles for serving-backend
profiling. A permission failure must remain a blocked or partial profiler result. Do not infer
line-level Scalene conclusions unless the retained JSON contains reconstructor source-line frames;
wrapper-only or process-only output is non-actionable evidence.
The py-spy adapter uses nonblocking 5 Hz sampling on CPython 3.14 container runs because the 100 Hz
default can let the profiler dominate the workload before it writes speedscope output. Sampling
errors remain part of the evidence and do not become exact CPU attribution.

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
`--query-existing-doris` to run the serving-backend query suite without reloading files. `--run-doris` and
`--query-existing-doris` are mutually exclusive. Add `--run-knowledge-export` to run the complete
store-backed knowledge-export workflow for the selected symbols and record output hashes; this
also remains explicit because it writes a potentially large external bundle.

### Current live-Doris benchmark

Use `benchmark-doris-current` when the complete source-bound store and its Doris publication already
exist. It validates the supplied manifest, source identity, and Doris registry, then runs the
canonical `generate` path against the live database. It does not materialize Parquet, execute
Stream Load, create tables, or change schema/index/session settings.

```powershell
uv run ddon-dwarf-reconstructor performance benchmark-doris-current <ELF> `
  --store-manifest <complete-manifest.json> `
  --output-dir $env:TEMP/ddon-analytical-dwarf/current-doris-benchmark `
  --control-symbol MtObject --control-symbol rLayout `
  --control-iterations 1 --query-iterations 3 --aifsm-iterations 1 `
  --control-timeout-seconds 900 --aifsm-timeout-seconds 7200 `
  --doris-cli D:\doris-cli\target\release\doriscli.exe
```

The report retains separate cold/warm controls for `MtObject` and `rLayout`, plus the independent
long-running `rAIFSM --full-hierarchy --exhaustive` workload. Its bounded Doris query contract is
explicitly first-definition behavior (`LIMIT 1001`) and must not be described as a complete
`rAIFSM` hierarchy benchmark. The report schema is `1.1`; its external
`doris-diagnostics/doris-diagnostics.json` records one `EXPLAIN` and one `EXPLAIN VERBOSE` per
distinct exact SQL statement, plus a raw and full server profile for every cold and warm
execution. Raw plans and profiles are stored below the same external directory with SHA-256,
normalized-plan, query-ID, session/schema, scan/tablet/cardinality/predicate, timing, memory, and
spill evidence. `doriscli` is preferred for SQL/profile retrieval; PyMySQL EXPLAIN and the FE HTTP
profile endpoints are recorded fallbacks. A missing, evicted, timeout, or FE-mismatched profile
keeps the query result but marks `doris_diagnostics` and the overall report incomplete; no stale
profile is reused.

The benchmark intentionally limits Doris explain/profile capture to the explicit suite. Generate
children are not instrumented; the independent process workload record still retains the
`MtObject`, `rLayout`, and exhaustive/full-hierarchy `rAIFSM` generation measurements. Profiling
does not implicitly enable `--no-cache` or other session tuning; cache/session state is captured
as evidence.

## Flight SQL evaluation

The implementation is isolated under
`src/ddon_dwarf_reconstructor/infrastructure/analytical/benchmark/`: shared measurement and
baseline code is in `common/`, native-Doris query workloads are in `doris/`, and the opt-in Flight
SQL adapter and experiments are in `flight_sql/`. The functional analytical package does not
export benchmark entry points; the CLI imports this explicit benchmark package instead. Dedicated
tests mirror the same hierarchy under `tests/infrastructure/analytical/benchmark/`.

`check-doris-flight` and `benchmark-doris-flight` are an optional ADBC group, not part of the
default MySQL/PyMySQL query, DDL, or Stream Load path. Install the exact candidate group with
`uv sync --group flight-sql --locked`, enable `ops/analytical-dwarf/compose.flight.yaml`, and run
the preflight first. It hashes the base/overlay and rendered Compose configuration, checks the FE
port and the advertised BE endpoint, and records bounded startup-log marker evidence. Set
`DDON_DORIS_FLIGHT_SQL_PUBLIC_HOST`/`DDON_DORIS_FLIGHT_SQL_PUBLIC_PORT` for a proxy or non-local BE
route. Set `DDON_DORIS_FLIGHT_SQL_FE_PUBLIC_HOST` to record a host-side FE socket check; Doris
4.1.3 still constructs FE-local result locations from its process-local address, so this socket
check does not prove that a returned FE-local `DoGet` location is reachable.

The benchmark keeps qmark parameters and separates execute/GetFlightInfo, fetch/DoGet, and Python
conversion/reduction timings. It measures PyMySQL `fetchall()` as the baseline, Flight row
conversion as a negative control, full Arrow tables, streamed RecordBatches, and a batch reducer.
Derived child-tag/name counts compare that client reducer with Doris `GROUP BY` under
`SET_VAR(enable_parallel_result_sink=true)`; the setting is measured, not presumed beneficial for
small results. It also compares N+1 and bounded set-based hydration for 32/128/512/2,048 candidates.
Reports are external and preserve provenance. By default the benchmark fails closed when Doris
rejects qmark parameters. The explicit diagnostic flag
`--allow-unparameterized-flight-fallback --reused-connections-only` renders only checked supported
literals, marks Flight `partial`, and is not a production path. The current complete reused-only
matrix records 54/76 strict cross-transport digest matches; the 22 mismatches are Python
`int`/`bool` representations of Doris `BOOLEAN` columns, not row/order/value differences. Point
lookups remain slower through Flight after connection reuse, while RecordBatch/reducer modes are
competitive only for larger arrays; cold connection and server-profile evidence remain separate
gates.

Use `profile-dwarf-store` for CPU attribution around that same bounded command. It invokes the
unprofiled `benchmark-dwarf-store` child through `PerformanceRunner`, so process CPU/RSS/I/O
metrics, cProfile method totals, and Scalene Python/native line and memory attribution remain
separate evidence surfaces:

```powershell
uv run ddon-dwarf-reconstructor performance profile-dwarf-store <ELF> `
  --store-manifest <complete-manifest.json> `
  --output-dir $env:TEMP/ddon-analytical-dwarf/profiled-doris-query `
  --query-existing-doris `
  --symbol rLayout --symbol MtObject --iterations 5 `
  --profiler scalene --profiler cprofile
```

Scalene/cProfile measure the Python client and orchestration only; Doris backend CPU, scanned
bytes/rows, tablet pruning, spills, and operator time must come from the matching Doris CLI
`EXPLAIN` and `profile get --full` records. Do not infer a database index change from a Python
hotspot or from a profiler run that failed to publish line attribution.

For module workloads, the Scalene adapter passes `--program-path` for the complete package source
tree (`/workspace/src/ddon_dwarf_reconstructor` in the Linux image) and excludes `scalene_target.py`,
the small wrapper that preserves `python -m` execution. This recovers package line attribution without enabling
standard-library and site-package tracing. It intentionally does not pass Scalene's
`--profile-all`; that flag is an explicit diagnostic fallback when combined with
`--profile-only /workspace/src/ddon_dwarf_reconstructor` and the wrapper exclusion. The CLI's
`--profiler all` is unrelated: it expands the repository's profiler list.

Every Scalene invocation explicitly passes `--memory-leak-detector`. The current upstream default is
also enabled, but the explicit flag makes the experimental detector part of the recorded command.
An optional `--profiler scalene-libraries` run uses `--profile-all --profile-system-libraries` with
the wrapper excluded and no package-only filter, exposing standard-library and site-package frames.
This broad profile is separate from `--profiler all` and is intended for library replacement or
algorithm comparison, not for the normal application hotspot report. Empty Scalene `leaks` maps
are reported as `scalene_leak_records=0` (“no likely leaks identified”) for that workload, not as
proof of leak freedom.

Use `--cpu-only` for a lower-size CPU-line profile. Retain the default full Scalene mode when
per-line memory evidence is required. In either mode, wrapper-only JSON is partial evidence and
cannot support a source-line action item.

Keep cProfile as an explicit deterministic cross-check even when Scalene has usable line
attribution. On the bounded Linux query, cProfile exposed 104,672 `posix.lstat` calls and 71.099 s
self time through repeated `Path.resolve()` calls; Scalene identified the surrounding application
lines and native time but did not provide the same exact call-count surface. cProfile therefore
remains useful for validating call counts and library/builtin alternatives, while Scalene remains
the primary CPU/native/memory/leak profiler.

The py-spy adapter remains useful for external live-process evidence. Use `py-spy dump --pid` for a
single in-process stack snapshot and `py-spy record` for bounded sampled traces; the latter is the
repository adapter's 5 Hz nonblocking mode. These are wall-clock/frame observations, not exact
deterministic call totals.

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
as non-actionable when the retained run reports only profiler or launcher attribution.

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

The historical comparison is report-only. On the measured warm `rLayout` workload, the regular
CPython 3.14.6 run averaged 2.062 seconds, the Nuitka 4.1.3 onefile run 2.470 seconds, and
free-threaded CPython 2.202 seconds. Nuitka reduced peak RSS but added onefile extraction I/O;
free-threaded CPython used more RSS. The current pyinstrument native extension also enables the GIL
when imported by a free-threaded interpreter. See the [runtime comparison how-to](../how-to/compare-runtimes.md) for
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
