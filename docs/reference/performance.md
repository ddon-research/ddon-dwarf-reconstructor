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
| `performance benchmark-doris-optimization <elf>` | Run the source-bound Doris baseline and one isolated optimization candidate |
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
  --control-cold-iterations 1 --control-warm-iterations 1 --query-iterations 3 `
  --aifsm-cold-iterations 0 --aifsm-iterations 1 `
  --control-timeout-seconds 900 --aifsm-timeout-seconds 7200 `
  --doris-cli D:\doris-cli\target\release\doriscli.exe
```

The report retains separate cold/warm controls for `MtObject` and `rLayout`, plus the independent
long-running `rAIFSM --full-hierarchy --exhaustive` workload. Its bounded Doris query contract is
explicitly first-definition behavior (`LIMIT 1001`) and must not be described as a complete
`rAIFSM` hierarchy benchmark. The report schema is `1.2`; its external
`doris-diagnostics/doris-diagnostics.json` records one `EXPLAIN` and one `EXPLAIN VERBOSE` per
distinct exact SQL statement, plus a raw and full server profile for every cold and warm
execution. Raw plans and profiles are stored below the same external directory with SHA-256,
normalized-plan, query-ID, session/schema, scan/tablet/cardinality/predicate, timing, memory, and
spill evidence. `doriscli` is preferred for SQL/profile retrieval; PyMySQL EXPLAIN and the FE HTTP
profile endpoints are recorded fallbacks. A missing, evicted, timeout, or FE-mismatched profile
keeps the query result but marks `doris_diagnostics` and the overall report incomplete; no stale
profile is reused.

The default benchmark intentionally limits Doris explain/profile capture to the explicit suite.
Use `--trace-generation-queries` to opt in to tracing the actual PyMySQL boundary inside every
generation child. Each child writes an external `doris-query-trace.jsonl` and compact summary;
parameter values are never retained. The tracer captures one profile per query shape and then
slow executions up to the configured bounded profile budget (`--trace-profile-threshold-ms` and
`--trace-max-profiles`). A missing, mismatched, evicted, or timed-out FE-local profile is `partial`.
Tracing is paired with an untraced run; if it adds more than 5% wall time, use it for attribution
only and exclude traced timings from performance conclusions. Profiling does not implicitly enable
`--no-cache` or other session tuning; cache/session state is captured as evidence.

### Doris optimization evaluation

Use the optimization command for the controlled one-factor matrix. It keeps the canonical
`DUPLICATE KEY`, source-first, V2/ZSTD tables in place and provisions lookup candidates only when
`--provision-candidate` is explicit. The default controls are three cold and five warm repetitions;
the heavy `rAIFSM --full-hierarchy --exhaustive` screening path is one cold and three warm runs.

```powershell
uv run ddon-dwarf-reconstructor performance benchmark-doris-optimization <ELF> `
  --store-manifest <complete-manifest.json> `
  --output-dir $env:TEMP/ddon-analytical-dwarf/doris-optimization `
  --candidate canonical `
  --control-symbol MtObject --control-symbol rLayout `
  --doris-cli D:\doris-cli\target\release\doriscli.exe
```

The matrix includes the decoded-serving attribute projection, lazy reference prefetch, bounded
hydration (512 keys), source/name lookup tables with buckets 2/4/8, trace-gated method/DIE locator
tables, index/Bloom removal, tiny-table buckets, V2/V3, ZSTD/LZ4, pipeline parallelism, SQL-cache
state, and Stream Load workers 1/2/4/8. Row store, asynchronous MV, group commit, and unrelated
complex-SQL features are retained as `not_applicable`/rejected evidence for this append-only
single-table workload. Every report carries
the typed serving variant, complete row-count evidence, cold/warm samples, query traces, output
hashes, DDL/configuration hashes, and a promotion gate. EXPLAIN-only or scan-only improvements do
not promote a candidate; confirmatory warm p50/p95 must improve a representative rAIFSM or hot
lookup by at least 10% with exact parity and no more than the existing 110% regression bound.

#### 2026-08-09 to 2026-08-10 evaluation and serving-path result

The first complete-store evaluation ran against Doris 4.1.3 and identified the dominant cost as
generation round trips rather than scan CPU. The source/unit-bound 512-key batch screen was `34.1x`
faster than sequential attribute queries with exact row parity. The serving runtime now consumes
bounded batches for DIE metadata, attributes, child frontiers, reference targets, and child-tag
counts, and caches line programs per compilation unit.

The current optimized path produced exact output from the complete source-bound publication.
`rLayout` completed in `13.195 s`. Exhaustive `rAIFSM` completed in `19.811 s`, `20.166 s`, and
`20.784 s` (`n=3`, exploratory p50/p95 `20.166/20.784 s`); all 11 header hashes matched the
approved bundle. This is about a `94.5%` reduction from the earlier `361.004 s` warm `rAIFSM` process sample,
while the canonical Doris schema, keys, buckets, storage format, indexes, and registry remained
unchanged.

A paired traced `rAIFSM` run published the same 11 headers in `39.589 s` and recorded `754` redacted
observations. The follow-up semantic trace labeled the dominant operations: 85 batched attribute
hydration queries, 154 reference-prefetch queries, 45 batched DIE hydration queries, and 138
single-DIE lookups. Every FE profile was `partial` because query IDs did not match, and tracing
added more than the 5% overhead budget, so traced wall time is excluded from performance
conclusions. A grouped child-tag `COUNT(*)` experiment reduced one bounded result from 1,970 to
602 rows and was faster in a SQL microbenchmark, but paired full runs were effectively tied with
the raw path (`21.160/21.165 s` versus `21.159/21.163 s` warm p50/p95), so it was removed.

The source/name auxiliary tables reduced global lookup scheduling to 1/2 and 1/8 tablets. Their
standalone p50 gain was roughly 10%, but p95 was roughly 5%, so the individual bucket candidates
did not clear the promotion gate. The three positive behaviors were nevertheless activated
together: lazy prefetch, the decoded-serving projection, and b8 name lookup. b8 is now the
canonical lookup table; b2 and b4 remain comparison-only. The target-DIE prefetch screen was exact
but regressed `rAIFSM` to `29.299 s` and was reverted. Physical/index/storage/session variants
remain `not_observed`; the actual trace also contained no method-target lookup shape to justify
provisioning that table.

The 2026-08-10 policy recheck used the refreshed canonical registry identity and left the fourteen
canonical family tables unchanged. The prior canonical eager/full/all `rAIFSM` result was
`19.121/19.127 s` warm p50/p95 (`n=3`) with the approved 11-file bundle hash
`0514bdb383121ebc83d8e9193ef0766c7074a4fd90f3e3d00691cea29461b243`. The measured interaction
batch is now promoted: canonical generation defaults to lazy reference prefetch, the decoded-serving
attribute projection, and the source/name b8 lookup table. Its confirmatory result was
`16.1152/16.1187 s` warm p50/p95 (`n=5`), approximately `15.7%` faster at both quantiles, with
exact output and lower warm p95 RSS. Raw attribute columns remain stored; the projection narrows
the generation fetch and is covered by the completed full Season 2 parity run. A targeted child-tag
predicate was exact but regressed warm p50 by `10.5%` and is rejected.

The next trace-confirmed candidate, `unit-bound-hydration`, was screened against the exact
canonical ELF path and complete manifest. It preserved the approved 11-header bundle hash, but
the fair untraced exhaustive `rAIFSM` run took `289.048 s` (`n=1`, exploratory) versus the
canonical `19.121/19.127 s` warm p50/p95; it is rejected and did not proceed to 3-cold/5-warm
confirmation. Its attribution trace recorded `26,463` completed observations before the
profile-fetching process was stopped: `hydrate_attributes_by_die` ran `9,262` times,
`prefetch_reference_targets` `7,579` times, and `prefetch_child_tag_counts` `9,136` times,
versus canonical counts of `85`, `154`, and `25`. The unit predicate therefore created query
fan-out rather than reducing work. The trace is partial attribution evidence; its wall time and
incomplete FE profiles are excluded from performance conclusions.

#### Combined positive-below-gate batch

The positive candidates that had shown roughly 5% or better improvement were activated together
as `combined-positive-below-gate`: lazy reference prefetch, the decoded-serving attribute
projection, and the source/name lookup alternatives b2, b4, and b8. The confirmatory report at
`C:\Users\morph\AppData\Local\Temp\ddon-analytical-dwarf\combined-positive-below-gate-confirm-20260810\doris-optimization.json`
ran three cold and five warm exhaustive `rAIFSM` repetitions with b8 active. All eight
`rAIFSM` outputs were exact and retained the approved 11-file bundle hash
`0514bdb383121ebc83d8e9193ef0766c7074a4fd90f3e3d00691cea29461b243`.

Warm p50/p95 were `16.1152/16.1187 s`, versus canonical `19.1208/19.1271 s`, or about
`15.7%` faster at both quantiles. Warm p95 RSS also fell from `164,102,144` to `136,142,848`
bytes. The active b8 auxiliary table added `399,984,557` bytes (`7.23%` over the complete
canonical table total), and its source-bound population took `14.875 s`; b2 and b4 were
provisioned only to make the bucket interaction comparison complete. This clears the end-to-end
latency and measured storage/memory gates. A follow-up selective analysis of the active b8
key/filter columns produced two manual `FINISHED` jobs (`1786278610025`, `1786278610030`) with
1,048,576-row samples and zero failed subjobs; the older automatic-analysis failures remain raw
context only. The b8 table is now part of the canonical load plan and is refreshed from the
source-bound index after the fourteen family loads. b2 and b4 remain comparison-only candidates;
the canonical fourteen-family physical model and registry row contract remain unchanged.

#### Historical full Season 2 header-generation and MSVC closure audit

The complete `resources/season2-resources.txt` suite was rerun against the source-bound manifest
on 2026-08-10 in four external generation batches under
`C:\Users\morph\AppData\Local\Temp\ddon-analytical-dwarf\season2-msvc-fix2-20260810-batch-001`
through `...-batch-004`. All 289/289 roots published with zero generation failures; the bulk run
contained 2,759 generated headers and 3,048 published files. Every declared file byte count and
SHA-256 matched, and the source SHA-256 was
`4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0`.

Each generated header was then compiled as its own translation unit with MSVC
`14.51.36231` (`/std:c++latest /EHsc /W4 /Zc:__cplusplus`). The first audit exposed two closure
defects: nested base dependencies were omitted at the hierarchy depth boundary, and a nested
template argument was forward-declared as a class instead of a template. The fixes made base
edges depth-exempt, qualified nested base names from DIE identity, and recursively preserved
template forward declarations. A separate namespace lookup defect also caused `rAcquirement` to
fall through to a not-found placeholder; namespace tags are now queried and multi-file namespace
roots render through the namespace header path.

The final composite validation input is
`C:\Users\morph\AppData\Local\Temp\ddon-analytical-dwarf\season2-msvc-fix4-20260810-input`.
It contains all 289 roots, 2,760 manifest-declared headers, and no placeholder or unresolved-type
markers. MSVC passed all 2,760/2,760 headers with no timeouts or compiler failures. The only
diagnostics were warning-only `C4099` (91), intentional anonymous struct/union `C4201` (125),
and one `C4309`; no unresolved-symbol or syntax-error codes remained. The one additional header
is the explicit `MtStream.h` closure made reachable by the nested-base fix. The raw report is
`C:\Users\morph\AppData\Local\Temp\ddon-analytical-dwarf\msvc-season2-fix4-20260810\msvc-header-validation.json`.

This closes the per-header MSVC syntax and generated-closure gate. It does not claim byte parity
with the unavailable historical approved `rLayout.h` baseline, and IDA/Sonar observations remain
separate evidence surfaces. The command and validator are reusable, change-triggered tools rather
than continuously running services: rerun them when the generator, source publication, serving
variant, or representative workload changes.

This command is a reusable, change-triggered regression/promotion tool, not a continuously running
service. The current publication has now been evaluated; rerun it when the generator path, Doris
image/configuration, source publication, candidate variant, or representative workload changes.

Candidate reports and all raw traces/profiles are external artifacts. `--no-cache` disables Doris
query cache for a session; it is not an operating-system storage-cache eviction, so cold and warm
labels remain separate and must not be conflated.

### 2026-08-13 boundary-refactor performance status

The boundary refactor retained byte-exact representative output for `rAIFSM`, `rArchive`, and
`rTexture`. The corrected batch-001 run completed 73/73 roots and 598/598 headers, and its
independent MSVC audit passed all 598 units. The full 289-root rerun remains `blocked`: two host
reboots interrupted the attempts, and the Doris FE cannot currently bind its configured 9030
endpoint because Windows excludes TCP ports 8983-9082. No incomplete output was accepted or used
as a performance workload. No matched warm p95 or peak-RSS comparison was accepted, so the
110%-of-baseline gate remains `not_observed` until the same source, runtime, backend, profile, and
cache-state workload runs to completion. The older 2026-08-09/10 measurements above remain
historical controls only.

### 2026-08-14 completed boundary-refactor acceptance

The source-bound baseline and complete post-refactor run are now observed. The final output root is
`C:\Users\morph\AppData\Local\Temp\ddon-dwarf-reconstructor-review\season2-final-source-cache-early-20260814`;
its generation log is `logs/ddon_reconstructor_17560_20260814T012907_837060+0200.jsonl` and records
289 successful roots with zero failed roots, 289 bundles, 2,745 headers, and 3,034 published files.
The 2,745 header SHA-256 values and all 289 bundle-manifest SHA-256 values match the immutable baseline at
`C:\Users\morph\AppData\Local\Temp\ddon-dwarf-reconstructor-review\baseline-33b8271`.
The normalized counts are therefore `root_count=289`, `bundle_count=289`,
`manifest_count=289`, `header_file_count=2745`, `published_file_count=3034`, and
`msvc_unit_count=2745`.

Independent MSVC validation is retained at
`C:\Users\morph\AppData\Local\Temp\ddon-dwarf-reconstructor-review\msvc-season2-final-source-cache-early-20260814\msvc-header-validation.json`.
Visual Studio MSVC `14.51.36231` passed all 2,745 translation units with zero failures and zero
timeouts. Warnings remain separate: `C4201=124` and `C4309=1`.

The cache diagnosis is also now evidence-backed. Request-scoped Doris hydration caches are
intentionally reset at each Season 2 root and were bounded during the full run; the process RSS
remained approximately 288--424 MiB as the corpus progressed. The persistent selection cache is
different: it is source/profile-bound, fingerprint-validated, and supplies deterministic
definition-selection hints. Removing it changed 15 dependency headers and 21 header payloads in
`rLayout`/`rTexture`, so that experiment was rejected for the canonical path. It is not a generic
compatibility fallback.

The final benchmark report is
`C:\Users\morph\AppData\Local\Temp\ddon-dwarf-reconstructor-review\performance-rAIFSM-final-early-3-20260814\current-doris-benchmark.json`.
After one explicit cold `rAIFSM --full-hierarchy --exhaustive` run, three warm repetitions measured
9.06, 9.06, and 9.07 seconds (p50 `9.06 s`, p95 `9.07 s`) with peak RSS at most 73.8 MiB. Every
run produced the approved bundle SHA-256
`1176bd80524391ef2d23fd99541f9a63e04566e2e8a8906dc15670a80ca7f63b`. The bounded Doris query
screen observed complete results; its largest bounded `find_definitions` query was about 13 ms cold
and 6 ms warm. Every generation child loaded the verified 58-symbol source-bound cache
`C:\Users\morph\AppData\Local\ddon-dwarf-reconstructor\DDOORBIS-beced6568432-dwarf-cache.json`.
The measured Doris cache warm-up is therefore milliseconds, while source-bound DWARF cache identity
changes which deterministic selection hints are available. An empty transient Doris query cache is
not the observed cause of the earlier apparent degradation. The final full-corpus run took about
39 minutes; root size varies substantially, so that total is not a per-root latency budget.

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
