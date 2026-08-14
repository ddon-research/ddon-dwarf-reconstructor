# Local analytical DWARF warehouse

This Compose project is an explicit local benchmark dependency. It keeps Doris
metadata, BE storage, and source-bound Parquet inputs outside source control.

The Doris 4.1.3 images are pinned by immutable amd64 digest in `compose.yaml` and
[`images.lock.json`](images.lock.json). Registry metadata, image pulls, a healthy daemon, and
native fixture load were observed on 2026-08-05. The complete source-bound Season 2 generation
and per-header MSVC closure audit were observed on 2026-08-10; IDA/Sonar evidence and comparison
with the unavailable historical approved header remain separate boundaries.

The default bind mounts are repository-local ignored paths under
`output/analytical-dwarf/warehouse` for Doris metadata, storage, and logs. The source-bound
Parquet store under `output/analytical-dwarf/main` remains on the host: the loader reads it and
uploads bounded batches through Doris Stream Load, so it does not need to be mounted into either
container. Override the individual `DDON_DORIS_*` variables only when the replacement path is on
a local fixed disk; do not use the portable E: drive. `%TEMP%\ddon-analytical-dwarf` is reserved
for disposable diagnostic runs and is not the default durable warehouse.

For a long producer run, use `--checkpoint-every-cus N` only when diagnostic snapshots are
needed. Checkpoints rotate Parquet parts and preserve `checkpoint.json` after an interruption;
inspect them with `artifacts inspect-dwarf-store <checkpoint.json> --allow-incomplete`. They are
partial evidence and are not valid Doris load or runtime-generation inputs.

For a serving publication, inspect a complete manifest, load it into Doris, and wait for the
command to report a `complete` source registry with reconciled family counts. `--dry-run` only
plans DDL/load operations and does not make the manifest available to generation:

```powershell
uv run ddon-dwarf-reconstructor artifacts inspect-dwarf-store <manifest.json>
uv run ddon-dwarf-reconstructor artifacts load-doris <manifest.json>
```

After publication, `generate` and `export-knowledge` query Doris only. They do not read the
Parquet files or JSONL audit rows directly, and they fail closed if the registry is missing,
stale, incomplete, or count-mismatched.

```powershell
docker compose --file ops/analytical-dwarf/compose.yaml config --quiet
docker compose --file ops/analytical-dwarf/compose.yaml up -d
docker compose --file ops/analytical-dwarf/compose.yaml ps --all
```

The container ports remain Doris's canonical `8030`/`9030`/`8040` ports, but the workstation
side of the mappings can be changed when Windows reserves a local port range. For example, the
following keeps the same FE/BE services and serving profile while exposing the FE on alternate
host ports:

```powershell
$env:DDON_DORIS_HTTP_HOST_PORT = '18030'
$env:DDON_DORIS_SQL_HOST_PORT = '19030'
$env:DDON_DORIS_HTTP_URL = 'http://127.0.0.1:18030'
$env:DDON_DORIS_SQL_PORT = '19030'
docker compose --file ops/analytical-dwarf/compose.yaml up -d
```

Use the same host-side values for the application configuration and health checks. This is a
transport remap only; it is not a different Doris backend or a serving-policy variant.

The analytical CLI uses `DDON_DORIS_HTTP_URL`, `DDON_DORIS_STREAM_LOAD_URL`,
`DDON_DORIS_SQL_HOST`, `DDON_DORIS_SQL_PORT`, `DDON_DORIS_DATABASE`,
`DDON_DORIS_USER`, and `DDON_DORIS_PASSWORD` for connection settings. The Flight benchmark additionally
accepts `DDON_DORIS_FLIGHT_SQL_HOST`, `DDON_DORIS_FLIGHT_SQL_PORT`,
`DDON_DORIS_FLIGHT_SQL_URI`, `DDON_DORIS_FLIGHT_SQL_FE_PUBLIC_HOST`,
`DDON_DORIS_FLIGHT_SQL_PUBLIC_HOST`,
`DDON_DORIS_FLIGHT_SQL_PUBLIC_PORT`, `DDON_DORIS_FLIGHT_SQL_MAX_MESSAGE_SIZE`,
`DDON_DORIS_FLIGHT_SQL_QUERY_TIMEOUT_SECONDS`, and
`DDON_DORIS_FLIGHT_SQL_FETCH_TIMEOUT_SECONDS`. The local Compose
baseline maps stream load to `http://127.0.0.1:8040`; set the stream-load variable explicitly
when using another BE endpoint. `DDON_DORIS_STREAM_LOAD_WORKERS` defaults to `1` for a
reproducible baseline; set it explicitly (for example, `4`) when benchmarking concurrent,
independently labeled Parquet loads on a full corpus. Do not place credentials in the repository
or in benchmark artifacts.

The canonical serving policy is now fixed in normal generation: lazy reference prefetch, the
decoded-serving attribute projection, `DDON_DORIS_CHILD_TAG_FILTER=all`, and
`DDON_DORIS_HYDRATION_SCOPE=global`. The source/name lookup is the automatically maintained
`dwarf_records_opt_name_b8` table. Raw attribute-value columns remain stored in the canonical
attribute family; the serving projection narrows the generation fetch and is covered by the full
Season 2 exactness run. The `unit` hydration scope was measured and rejected because it multiplies
source-bound query fan-out. Legacy policy environment variables are ignored for the canonical
variant; non-canonical benchmark variants may still set them inside their isolated child process.

The Compose file does not enable Arrow Flight SQL by default. Doris documents that service as
experimental and requires distinct FE and BE `arrow_flight_sql_port` settings; enable it only in
the explicit overlay, with ports, rendered-Compose hash, startup logs, and endpoint checks recorded
as external evidence. MySQL protocol plus PyMySQL remains the supported DDL/Stream Load path.

The opt-in Flight SQL loop is:

```powershell
uv sync --group flight-sql --locked
docker compose --file ops/analytical-dwarf/compose.yaml --file ops/analytical-dwarf/compose.flight.yaml config --quiet
docker compose --file ops/analytical-dwarf/compose.yaml --file ops/analytical-dwarf/compose.flight.yaml up -d
uv run --group flight-sql ddon-dwarf-reconstructor performance check-doris-flight `
  --output "$env:TEMP/ddon-analytical-dwarf/analytical-flight/doris-flight-preflight.json"
uv run --group flight-sql ddon-dwarf-reconstructor performance benchmark-doris-flight `
  --store-manifest output/analytical-dwarf/main/store-4236f598acc8f158/manifest.json `
  --output-dir "$env:TEMP/ddon-analytical-dwarf/analytical-flight" `
  --allow-unparameterized-flight-fallback --reused-connections-only
```

The overlay is `compose.flight.yaml`; the base `compose.yaml` remains unchanged. It maps FE Flight
to host port `8070`, BE Flight to `8050`, and sets the BE `public_host` to
`127.0.0.1` for the host-side client. For a remote deployment or proxy, set
`DDON_DORIS_FLIGHT_SQL_PUBLIC_HOST` and `DDON_DORIS_FLIGHT_SQL_PUBLIC_PORT` to the externally
routable BE address before running the preflight; the same values are applied to the BE
`public_host` and `arrow_flight_sql_proxy_port` settings. The check records per-file and rendered-Compose
SHA-256 values, tests FE and advertised BE TCP reachability, and searches the bounded FE/BE startup
logs for Flight markers. A Flight FE connection is not sufficient when Doris returns an unreachable
BE endpoint for `DoGet`. `DDON_DORIS_FLIGHT_SQL_FE_PUBLIC_HOST` records an additional FE socket
check, but the current Doris producer builds FE-local result locations from the FE process-local
address; it is therefore not a rewrite of the returned Flight `Location`.

The benchmark report is written outside source control. It separates execute/GetFlightInfo,
fetch/DoGet, and Python conversion/reduction timing, compares PyMySQL rows with ADBC rows,
`fetch_arrow_table()`, streamed `fetch_record_batch()`, and an Arrow-native reducer, and runs the
single-row, array, 36-query, derived-aggregation, and N+1/set-based hydration shapes. Derived
child-tag/name counts also run Doris `GROUP BY` with the per-query
`SET_VAR(enable_parallel_result_sink=true)` hint for a measured comparison. A missing listener or
failed BE route remains `blocked`/`not_observed`. The explicit fallback flag is benchmark-only:
it renders supported qmark values as checked SQL literals after Doris 4.1.3 reports
`acceptPutPreparedStatementQuery unimplemented`, marks the report `partial`, and does not alter the
default MySQL/DDL/Stream Load path. The current complete reused-only report is
`$env:TEMP/ddon-analytical-dwarf/analytical-flight/full-fallback-reused-v3/doris-flight-report.json`;
its strict parity is 54/76 because PyMySQL exposes Doris BOOLEAN values as `int` while Arrow
exposes them as `bool`.

For structured SQL, profile, and tablet evidence, use the locally compiled Apache Doris CLI
when available. On this Windows workstation it is outside the repository at
`D:\doris-cli\target\release\doriscli.exe`:

```powershell
$env:DORIS_HOST = '127.0.0.1'
$env:DORIS_USER = 'root'
$env:DORIS_PORT = '9030'
$env:DORIS_HTTP_PORT = '8030'
& D:\doris-cli\target\release\doriscli.exe auth status --format json
```

The npm wrapper is not a Windows executable; build the CLI from its checked-out Rust source or
use the repository's Python loader when the external binary is unavailable.

The current-data benchmark keeps PyMySQL as the measured execution path and uses the CLI only for
diagnostics. Run it against the already complete manifest when the live publication is present:

```powershell
uv run ddon-dwarf-reconstructor performance benchmark-doris-current <ELF> `
  --store-manifest <complete-manifest.json> `
  --output-dir $env:TEMP/ddon-analytical-dwarf/current-doris-benchmark `
  --doris-cli D:\doris-cli\target\release\doriscli.exe
```

The external `doris-diagnostics/doris-diagnostics.json` report is schema `1.2` evidence: every
distinct suite SQL has `EXPLAIN` and `EXPLAIN VERBOSE`, and every cold/warm execution has its own
query ID plus raw/full profile paths, hashes, fetch timing, and server summary. CLI failures fall
back to PyMySQL for plans and FE HTTP profile endpoints; attempts and missing/evicted/timeout/
FE-mismatch states remain explicit. Add `--trace-generation-queries` to capture the actual Doris
queries made by each generation child in bounded redacted JSONL; profiles are retained for one
query per shape and slow executions up to the configured cap. Trace profile failures are `partial`,
and a paired untraced/traced run is required before using traced wall time. Cache/session settings
are not changed implicitly.

## Optimization evidence

The Compose baseline deliberately keeps optimization variables visible. Native tables use
`DUPLICATE KEY`, source-first/offset keys and unit bucketing, Bloom filters for source/offset
equality, and inverted indexes for names across the fourteen lossless/derived families. After a
full load, compare `EXPLAIN` and no-cache/warm profiles. The current loader submits `ANALYZE TABLE`
by default with selective key/filter/order/name/target/parent/resolution columns and a maximum
4,194,304-row sample per family; set `DDON_DORIS_ANALYZE_WAIT_SECONDS` to a positive value for a
promoted build so every requested job reaches terminal success. The loader can retain raw `SHOW
TABLE STATS`, `SHOW COLUMN STATS`, `SHOW ANALYZE`, `SHOW AUTO ANALYZE`, and
`__internal_schema.column_statistics` evidence when `DDON_DORIS_CAPTURE_STATISTICS_EVIDENCE=1`.
Do not infer selectivity from the tiny fixture, where all tablets can be touched. Materialized
views and alternate load methods remain measured variants only.

Run the controlled optimization matrix only against a complete source-bound publication:

```powershell
uv run ddon-dwarf-reconstructor performance benchmark-doris-optimization <ELF> `
  --store-manifest <complete-manifest.json> `
  --output-dir $env:TEMP/ddon-analytical-dwarf/doris-optimization `
  --candidate canonical `
  --control-symbol MtObject --control-symbol rLayout `
  --doris-cli D:\doris-cli\target\release\doriscli.exe
```

The command defaults to three cold/five warm controls and one cold/three warm exhaustive
`rAIFSM` screening repetitions. Candidate lookup tables are source-bound auxiliary tables, created
only with `--provision-candidate`; supported candidates are source/name buckets 2/4/8, a
trace-gated target-offset method table, and a trace-gated DIE-offset locator. Physical/runtime
rows (indexes, buckets, V3/LZ4, pipeline parallelism, SQL cache, and Stream Load workers) are
matrix entries until a separate provisioning path supplies their measured evidence. The report's
typed `DorisServingVariant` and `DorisOptimizationReport` retain DDL/configuration hashes,
complete row counts, query observations, cold/warm output hashes, load/statistics/tablet evidence,
and rejected/not-applicable decisions. `EXPLAIN` or scan reduction alone never promotes a variant;
exact ordered parity and confirmatory representative-workload p50/p95 improvement are required.

The Parquet contract stores nonnegative DWARF integers as exact `DECIMAL(20,0)` values rather
than `UINT64`. Native Doris maps those columns to `LARGEINT`. Keep this physical type when adding
a family or a new analytical reader.

PyArrow is pinned at `25.0.0`; the local concept and API reference is
`D:\PyArrow-25.0-python-docs`. The producer uses explicit schemas per family, bounded
`ParquetWriter` row groups, and a hard row cap before `Table.from_pylist()` conversion. Dataset
readers must use the layout-specific typed Hive partition schema, column projection, and source/CU
filters; use `to_batches()` for large scans. Arrow memory-pool counters are useful telemetry but do
not replace process RSS measurements, and `memory_map` is not a resident-memory bound for compressed
Parquet. JSONL backfill uses the same bounded sink and manifest writer/layout settings as direct
materialization.

The relevant primary guidance is Doris's [POC checklist](https://doris.apache.org/docs/4.x/getting-started/before-you-start-the-poc/),
[schema and index optimization](https://doris.apache.org/docs/4.x/query-acceleration/tuning/tuning-plan/schema-and-index-optimization/),
[statistics](https://doris.apache.org/docs/4.x/query-acceleration/optimization-technology-principle/statistics/),
[query profiles](https://doris.apache.org/docs/4.x/query-acceleration/query-profile/), and
[load overview](https://doris.apache.org/docs/4.x/data-operate/import/load-manual/). For live
clarifications, consult the corresponding pages in `D:\Apache-Doris-version-4.x-docs` before
relying on CLI output.

For statistics evidence, do not use `information_schema.statistics` or
`information_schema.column_statistics`: Doris documents these compatibility views as empty. Use
`SHOW TABLE STATS`, `SHOW COLUMN STATS`, `SHOW ANALYZE`, `SHOW AUTO ANALYZE`, and
`__internal_schema.column_statistics` instead.

## Historical v9 serving result (rejected canonical store)

The complete v9 source-bound store was loaded into `dwarf_full_v9_20260806` on 2026-08-06:
596,944,504 rows across 413 closed Zstandard Parquet files, 14 native family tables, zero
filtered Stream Load rows, and zero failed statistics jobs. The all-table CLI health sweep found
only `NORMAL` tablets; the largest table is `full_attribute` at 2,591.3 MB with skew 1.2.

Native Doris is the serving backend. The source/CU/DIE lookup prunes to one of 16 DIE tablets.
The historical v9 name-only projection was an explicitly provisioned experiment and is retained
below only as historical routing evidence. It is not the current serving contract: the promoted
v1.1 loader creates and refreshes the source-bound `dwarf_records_opt_name_b8` lookup table, and
normal generation binds it without an environment switch.

Use the repository `performance profile-dwarf-store` command for cProfile/Scalene process evidence
and `doriscli sql --profile`, `profile get`, `profile diff`, `EXPLAIN`, and `tablet --detail` for
Doris conclusions. Runtime performance comparisons use only this native path and the prior live
lookup baseline; Parquet files are input artifacts, not a competing runtime engine.

## Promoted main store and serving boundary

The promoted v1.1 source-bound store is retained under the durable repository-local path
`output/analytical-dwarf/main/store-4236f598acc8f158`. Its manifest records all 2,305 CUs,
597,338,011 rows, 1,452 closed Zstandard Parquet files, zero parser diagnostics, and complete
payload validation. The source-bound SHA-256 begins with `4236f598acc8f158`; use the manifest as
the authoritative identity rather than a run label or a Temp directory name.

The supported Doris configuration defaults to database `dwarf`. The versioned `dwarf_full_v27_*`
and `dwarf_full_v28_*` databases in the evidence ledger are retained serving measurements, not
the durable store identity. Current serving evidence reconciles all fourteen manifest family
counts plus the source-bound b8 lookup table, has terminal selective statistics for the active
lookup columns, and has healthy tablets. The full Season 2 generation run is now observed; the
per-header MSVC syntax and closure gate is now observed and clean. IDA/Sonar checks and byte
comparison with the unavailable historical approved header remain separate acceptance gates.

For name-only serving, the canonical loader creates and refreshes the source-bound
`dwarf_records_opt_name_b8` table from the canonical index. The promoted interaction benchmark
confirmed ordered parity and reduced the heavy exhaustive workload; b2 and b4 remain
comparison-only. `DDON_DORIS_DEFINITION_LOOKUP_TABLE` is reserved for isolated non-canonical
benchmark variants, while Native Doris remains the default serving backend.

The full Season 2 header-generation run completed on 2026-08-10 against source SHA-256
`4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0`. Because the local command
runner has a bounded execution window, the 289 roots were published in four external batches
under `C:\Users\morph\AppData\Local\Temp\ddon-analytical-dwarf\season2-msvc-fix2-20260810-batch-001`
through `...-batch-004`: 289/289 symbols, 2,759 generated headers, zero generation failures, and
zero manifest/header-integrity errors. The final compiler-closure staging input adds the explicit
`MtStream.h` dependency discovered during audit and contains 2,760 headers.

The approved real-header baseline is currently missing, so this operational result does not yet
authorize byte-stable header parity or the 110%-of-baseline runtime claim. The generic full-store
Parquet query harness timed out and is not a store failure; use the bounded query contract and
the Doris CLI profiles for further serving work. The corrected source-bound rLayout knowledge
export from the historical v27 evaluation is complete with 1,155 nodes, 2,078 relationships,
and no diagnostics. Its classifier-backed closure policy preserves real missing-aggregate
failures while accepting transparent primitive, enum, and declaration-only targets. The historical
v9/v27/v28 paths and database names remain useful evidence references, but must not be used as
current durable-path examples.

The final external MSVC audit input is
`C:\Users\morph\AppData\Local\Temp\ddon-analytical-dwarf\season2-msvc-fix4-20260810-input`.
It contains 289 bundles and 2,760 headers; MSVC `14.51.36231` passed every header independently
with no timeout or error. The corrected causes were missing nested-base closure edges, unqualified
nested base names, class-versus-template forward declarations, and namespace-root discovery.
The final tree contains no not-found or unresolved-type placeholders. Warning-only `C4099`,
`C4201`, and `C4309` diagnostics remain recorded in the external validation report at
`C:\Users\morph\AppData\Local\Temp\ddon-analytical-dwarf\msvc-season2-fix4-20260810\msvc-header-validation.json`.

## Current live-Doris benchmark evidence

The 2026-08-09 current-data run reused
`output/analytical-dwarf/main/store-4236f598acc8f158/manifest.json` and the live `dwarf` database.
It did not regenerate the analytical store or run Stream Load/DDL. The report is retained outside
source control at
`C:\Users\morph\AppData\Local\Temp\ddon-analytical-dwarf\current-doris-route-20260809\current-doris-benchmark.json`.

Run it with the existing publication:

```powershell
uv run ddon-dwarf-reconstructor performance benchmark-doris-current <ELF> `
  --store-manifest <complete-manifest.json> `
  --output-dir $env:TEMP/ddon-analytical-dwarf/current-doris-benchmark `
  --control-symbol MtObject --control-symbol rLayout `
  --control-iterations 1 --query-iterations 3 --aifsm-iterations 1 `
  --control-timeout-seconds 900 --aifsm-timeout-seconds 7200
```

The observed current runs were `MtObject` 111.694/79.477 s cold/warm, `rLayout` 236.416/213.274
s cold/warm, and exhaustive/full-hierarchy `rAIFSM` 347.064 s with 11 headers. The bounded
definition query remains first-definition behavior; it is not a complete `rAIFSM` hierarchy
benchmark. Raw Doris profiles and the fourteen-table state sweep are in
`C:\Users\morph\AppData\Local\Temp\ddon-analytical-dwarf\current-doris-route-20260809\doris-state`.

The current profile evidence shows the canonical index lookup touching all eight index tablets
and reading 145.55 MB for `rLayout` and 194.81 MB for `rAIFSM`, despite returning 145 and 343 rows.
The inverted index and Bloom filters are active and filtering rows, so adding another index is not
justified by this evidence alone. The automatic analyze history includes four earlier memory-limit
failures, while all fourteen retained manual analyze jobs are `FINISHED`; inspect the raw history
before treating statistics freshness as uniformly healthy.

### Actual optimization decision

The complete-store evaluation was run on 2026-08-09/10 under
`$env:TEMP/ddon-analytical-dwarf`. The query-level screen found a source/unit-bound 512-key batch
was `34.1x` faster than sequential attribute calls with exact row parity. The generator now uses
bounded batch hydration for DIE metadata, attributes, child frontiers, reference targets, and
child-tag counts, and caches line programs per compilation unit.

The prior canonical `eager/full/all` run completed exact exhaustive/full-hierarchy `rAIFSM` with
warm p50/p95 of `19.121/19.127 s` (`n=3`); all 11 headers matched the approved bundle. The
promoted combined path completed the same exact workload at `16.1152/16.1187 s` warm p50/p95.
The physical family design remains `DUPLICATE KEY`, source-first keys, current buckets, one
partition, V2/ZSTD, indexes, and replication one. Canonical loading additionally creates and
refreshes the b8 lookup table; the registry still carries only the fourteen-family counts plus
additive serving-variant identity metadata.

Lazy reference prefetch was exact and reduced traced queries from 754 to 680, including reference
prefetch calls from 154 to 108. The decoded-serving attribute projection reduced traced attribute
execute time from `7.786 s` to `5.737 s` and warm p95 RSS by `15.1%`. Their combined use with b8
cleared the end-to-end gate; these three behaviors are now the canonical generation defaults. The
targeted child-tag filter preserved exact output but regressed warm p50 by `10.5%` and was
rejected. b2 and b4 lookup tables, grouped child-tag aggregation, and method-target provisioning
remain comparison-only or unobserved.

The combined `combined-positive-below-gate` batch activated the three positive standalone
families together: lazy reference prefetch, decoded-serving attribute projection, and name lookup
buckets 2/4/8, with b8 active. Three cold and five warm exhaustive `rAIFSM` runs preserved the
approved 11-file bundle and measured `16.1152/16.1187 s` warm p50/p95 versus
`19.1208/19.1271 s` canonical (`15.7%` faster at both quantiles). Warm p95 RSS fell from
`164,102,144` to `136,142,848` bytes, and active auxiliary storage increased by `7.23%`.
An explicit selective analysis of the active b8 key/filter columns then produced two manual
`FINISHED` jobs with zero failed subjobs; older automatic-analysis failures remain historical
context. The b8 table is now created and refreshed by the canonical loader. b2 and b4 are
comparison-only alternatives; raw values remain retained in the canonical attribute table for
evidence consumers.

All traced FE profiles were `partial` because the returned profile text did not contain the
requested query ID, and tracing exceeded the 5% wall-time budget; traced wall time is attribution-
only. Index/Bloom removal, bucket/storage/session changes, and Stream Load worker comparisons
remain `not_observed`, not inferred from `EXPLAIN`. The benchmark is a reusable, change-triggered
one-shot regression/promotion command, not a continuously running service.
