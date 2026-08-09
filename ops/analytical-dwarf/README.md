# Local analytical DWARF warehouse

This Compose project is an explicit local benchmark dependency. It keeps Doris
metadata, BE storage, and source-bound Parquet inputs outside source control.

The Doris 4.1.3 images are pinned by immutable amd64 digest in `compose.yaml` and
[`images.lock.json`](images.lock.json). Registry metadata, image pulls, a healthy daemon,
native fixture load were observed on 2026-08-05. Full-corpus load, cold/warm benchmark, and
runtime-parity evidence remain required for final service acceptance.

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

The external `doris-diagnostics/doris-diagnostics.json` report is schema `1.1` evidence: every
distinct suite SQL has `EXPLAIN` and `EXPLAIN VERBOSE`, and every cold/warm execution has its own
query ID plus raw/full profile paths, hashes, fetch timing, and server summary. CLI failures fall
back to PyMySQL for plans and FE HTTP profile endpoints; attempts and missing/evicted/timeout/
FE-mismatch states remain explicit. The diagnostic scope is limited to the explicit suite;
generate children are not instrumented, and cache/session settings are not changed implicitly.

## Optimization evidence

The Compose baseline deliberately keeps optimization variables visible. Native tables use
`DUPLICATE KEY`, source-first/offset keys and unit bucketing, Bloom filters for source/offset
equality, and inverted indexes for names across the fourteen lossless/derived families. After a
full load, compare `EXPLAIN` and no-cache/warm profiles. The current loader submits `ANALYZE TABLE`
by default; set `DDON_DORIS_ANALYZE_WAIT_SECONDS` when the load evidence must retain terminal
`SHOW ANALYZE` states. Do not infer selectivity from the tiny fixture, where all tablets can be
touched. Materialized views and alternate load methods remain measured variants only.

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
Name-only lookup touches all eight canonical index tablets, so an explicitly provisioned
`full_index_name_candidate` projection was measured and retained as an opt-in path via
`DDON_DORIS_DEFINITION_LOOKUP_TABLE`. It is not automatically created by Compose or the loader:
bind it only after verifying its source identity and ordered result parity. The full application
query suite improved by only about 3.7%, so the canonical `full_index` table remains the default.

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
the durable store identity. Before claiming current serving completeness, repeat native Stream
Load counts, `SHOW TABLE STATS`, `SHOW COLUMN STATS`, `SHOW ANALYZE`, tablet health, and cold/warm
profiles against the promoted manifest. The full season-two symbol run and approved MSVC header
comparison remain separate acceptance gates.

For name-only serving, the opt-in `full_index_name_candidate` projection is source-bound and
ordered-result equivalent to `full_index`. Current CLI evidence is 149 ms p50 for five no-cache
base `rLayout` queries versus 9 ms for the candidate, with `EXPLAIN` pruning the candidate to
1/4 tablets instead of 8/8. Bind `DDON_DORIS_DEFINITION_LOOKUP_TABLE` only after verifying the
source identity and query parity. Native Doris remains the default serving backend.

The approved real-header baseline is currently missing, so this operational result does not yet
authorize byte-stable header parity or the 110%-of-baseline runtime claim. The generic full-store
Parquet query harness timed out and is not a store failure; use the bounded query contract and
the Doris CLI profiles for further serving work. The corrected source-bound rLayout knowledge
export from the historical v27 evaluation is complete with 1,155 nodes, 2,078 relationships,
and no diagnostics. Its classifier-backed closure policy preserves real missing-aggregate
failures while accepting transparent primitive, enum, and declaration-only targets. The historical
v9/v27/v28 paths and database names remain useful evidence references, but must not be used as
current durable-path examples.

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
