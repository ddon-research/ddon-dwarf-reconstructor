# Research and evidence ledger

## Current documentation boundary (2026-08-08)

The active implementation is the native-Doris path over the promoted v1.1 source-bound store at
`output/analytical-dwarf/main/store-4236f598acc8f158`. Its manifest records 2,305 compilation
units, 597,338,011 rows, 1,452 closed Zstandard Parquet artifacts, and zero parser diagnostics.
The repository-local `output/analytical-dwarf/main/` path is durable local evidence; `%TEMP%\ddon-analytical-dwarf`
is disposable diagnostic storage for checkpoints, bounded probes, profiles, and crash reports.

Iceberg/PyIceberg runtime, catalog, and service decisions in this ledger are historical research
and compatibility measurements retained for provenance. They are not active dependencies, load
targets, or acceptance gates. Current Doris clarification must consult the checked-out
`D:\Apache-Doris-version-4.x-docs` pages as well as the CLI, especially the POC checklist,
Duplicate Key/schema and bucketing guidance, load guidance, and statistics pages. Doris's
`information_schema.statistics` and `information_schema.column_statistics` compatibility views
are not authoritative; use `SHOW TABLE STATS`, `SHOW COLUMN STATS`, `SHOW ANALYZE`, `SHOW AUTO ANALYZE`,
and `__internal_schema.column_statistics`.

The full season-two symbol generation remains in progress. Standalone per-root bundles, status,
provenance, collision-safe publication, and MSVC/IDA/Sonar evidence are separate gates; the
promoted store and historical Doris measurements do not imply complete header acceptance. Versioned
v9/v27/v28 Temp paths and database names below are historical evidence labels, not current path
or service defaults.

## Authority matrix

| Area | Primary evidence | Disposition |
| --- | --- | --- |
| DWARF model | Existing generated DWARF 2/3/4 models, DWARF standards, LLVM `DWARFContext`/`DWARFUnit`/`DWARFDie` sources | Confirmed tree plus cross-reference model; unsupported forms require raw fallback. |
| pyelftools | Version 0.33 `compileunit.py`, `die.py`, and local v0.32-to-v0.33 diff | Confirmed lazy CU/DIE materialization; producer is isolated to infrastructure. |
| LLVM tools | `llvm-dwarfdump --verify`, `--verify-json`, `--statistics`, and `llvm-dwarfutil` behavior | Cross-check and verifier evidence; PS4 semantics remain subject to the repository authority policy. |
| LLVM versus original Sony toolchain | Modern LLVM 22.1.8 from the MSYS2 UCRT64 profile; the local PS4 ELF accepts generic LLVM parsing; no proprietary Sony DWARF extension was established | `supported`, `uncertain`: prefer modern LLVM for generic DWARF parsing and verification, while retaining an explicit unknown-extension escape and keeping Orbis authority only for SCE/ABI semantics. Absence of custom extensions is not proven by one input. |
| JSON converters | `volatilityfoundation/dwarf2json`, `yurydelendik/dwarf-to-json` | Support-only design comparisons; neither is a lossless general DWARF contract. |
| Parquet and Arrow | Parquet row groups/column chunks and Arrow logical/nested types; exact `decimal128(20,0)` for nonnegative DWARF integers | Physical columnar interchange and typed conversion boundary. Do not expose DWARF offsets or unsigned values as Parquet `UINT64` to Doris. |
| Iceberg | Schema, partition, manifest, snapshot, and atomic-commit specification | Table metadata and evolution boundary over Parquet files. |
| Doris | Duplicate-key model, prefix/Bloom/inverted indexes, Parquet and Iceberg lakehouse readers; checked-out `apache/doris-skills`; compiled `doris-cli` | Analytical query/load backends; measured rather than assumed performance. Windows `doris-cli` source build is usable; the npm wrapper is Linux/macOS-only. |

## Current-version and integration review

The current dependency and service review is recorded in the matrix below. `Observed` means the local lock, executable, image, or service was inspected; upstream pages provide release metadata.

### Arrow Flight SQL evaluation boundary

The evaluation is deliberately transport-scoped. `DorisFlightSqlClient` owns the optional ADBC
dependency and opens one reusable DB-API connection with qmark parameters, explicit query/fetch
timeouts, and the configured maximum Flight message size. `fetchall()` is retained as a measured
negative control; `fetch_arrow_table()`, `fetch_record_batch()`, and a bounded batch reducer are
the candidates for Arrow-native use. The benchmark keeps the existing PyMySQL row path as the
baseline and compares the source-bound 36-query contract, single-row/array shapes, and N+1 versus
set-based hydration without changing the domain `DwarfQueryPort`.

The source boundary is the [Doris Flight SQL integration guide](https://doris.apache.org/docs/4.x/connection-integration/arrow-flight-sql/)
and [Doris issue #25514](https://github.com/apache/doris/issues/25514), read with the
[Doris Flight SQL announcement](https://doris.apache.org/blog/arrow-flight-sql-in-apache-doris-for-10x-faster-data-transfer/),
the [Doris Python sample](https://github.com/apache/doris/blob/master/samples/arrow-flight-sql/python/test.py), and the
[Flight SQL specification](https://arrow.apache.org/docs/format/FlightSql.html),
[Flight specification](https://arrow.apache.org/docs/format/Flight.html), and
[Arrow Flight introduction](https://arrow.apache.org/blog/2019/10/13/introducing-arrow-flight/).
Client behavior is based on the [PyArrow Flight cookbook](https://arrow.apache.org/cookbook/py/flight.html),
[PyArrow Flight API](https://arrow.apache.org/docs/python/flight.html),
[ADBC driver manager API](https://arrow.apache.org/adbc/main/python/driver_manager.html),
[ADBC Flight SQL API](https://arrow.apache.org/adbc/main/python/api/adbc_driver_flightsql.html),
[Flight SQL recipe](https://arrow.apache.org/adbc/main/python/recipe/flight_sql.html),
[driver-manager recipe](https://arrow.apache.org/adbc/main/python/recipe/driver_manager.html), and the
[DZone Flight SQL overview](https://dzone.com/articles/arrow-flight-sql-data-transfer). The
[Alex Merced ADBC overview](https://alexmerced.blog/blog/2026-08-06-arrow-flight-adbc-explained.html)
was also requested, but was unavailable to the source fetcher on 2026-08-09 and is not treated as
authority. Together these sources establish the GetFlightInfo/DoGet execution boundary, qmark
parameter contract, Arrow table/RecordBatch readers, and the need to measure row conversion
separately from columnar transfer. The current [DorisFlightSqlProducer.java](https://github.com/apache/doris/blob/master/fe/fe-core/src/main/java/org/apache/doris/service/arrowflight/DorisFlightSqlProducer.java)
source adds the implementation boundary: complete SQL is supported, while
`acceptPutPreparedStatementQuery` throws `UNIMPLEMENTED`; its FE-local schema path returns the
producer's FE `Location`. The companion service constructs that location from
`FrontendOptions.getLocalHostAddress()`, so a host-published FE port does not by itself rewrite a
container-local address returned in `FlightInfo`.

The optional dependency group is installed only for an explicit evaluation environment:

```text
uv sync --group flight-sql --locked
```

The explicit install observed the locked ADBC imports. The first live preflight found that the
running containers had been created from the base Compose file plus a temporary port override with
`!override`, so only FE `8030`/`9030` and BE `8040` were published even though the persisted FE/BE
configs already had Flight listeners. Recreating FE/BE with the Flight overlay published FE
`8030`/`8070`/`9030` and BE `8040`/`8050`; the exact FE/BE startup markers and direct TCP endpoints
were then observed. The latest preflight additionally checks FE public host `192.168.178.81:8070`
and BE public host `127.0.0.1:8050`; its hashes and startup evidence are in
`C:\Users\morph\AppData\Local\Temp\ddon-analytical-dwarf\analytical-flight\doris-flight-preflight-v2.json`.
The required qmark probe returns `NotSupportedError: NOT_IMPLEMENTED:
[FlightSQL] acceptPutPreparedStatementQuery unimplemented (Unimplemented; ExecuteQuery)`. The
explicit benchmark-only fallback renders supported qmark values as checked SQL literals and
completes the reused-connection matrix; it is recorded as `partial`, never enabled by default,
and does not change DDL, Stream Load, or semantic query code. Doris aggregation now uses the
documented per-query `SET_VAR(enable_parallel_result_sink=true)` hint, avoiding a separate
FE-local `SET` result exchange.

| Surface | Status | Evidence | Decision |
| --- | --- | --- | --- |
| Arrow/PyArrow | `confirmed`, `observed` | [Arrow Python docs](https://arrow.apache.org/docs/python/index.html), the local `D:\PyArrow-25.0-python-docs` reference, the installed Python 3.14.6 environment, and the lock resolve `pyarrow==25.0.0`; the runtime reports the `mimalloc` memory-pool backend. | Use explicit per-family schemas, `ParquetWriter` with bounded row groups, capped `Table.from_pylist` inputs, and `pyarrow.dataset` projection/filter/to-batch scans. Treat Arrow memory-pool counters as telemetry rather than whole-process RSS, and consult the local reference before changing these boundaries. |
| Iceberg/PyIceberg | `historical`, retired from active runtime | [PyIceberg reference](https://py.iceberg.apache.org/reference/pyiceberg/) and the historical lock/evidence resolve `pyiceberg==0.11.1` with `pyiceberg-core==0.8.0`. | Retain prior compatibility measurements only; do not use Iceberg format, catalogs, or services in the active runtime. |
| Doris server | `observed` | Pinned 4.1.3 FE/BE images were pulled and the Compose cluster is healthy with immutable digests recorded in `ops/analytical-dwarf/images.lock.json`. | Use native Doris 4.1.3 with the repository-local ignored warehouse and the promoted main store; Temp is diagnostic only. Do not reuse old versioned service state. |
| Doris Docker references | `supported`, `observed` | The [runtime tree](https://github.com/apache/doris/tree/master/docker/runtime), [demo](https://github.com/apache/doris/tree/master/docker/runtime/docker-compose-demo), and [doris-compose](https://github.com/apache/doris/tree/master/docker/runtime/doris-compose) were reviewed. | Keep the small pinned Compose file for reproducible evidence; upstream samples remain operational reference. |
| Doris MySQL client | `confirmed`, `observed` | [Doris MySQL protocol](https://doris.apache.org/docs/4.x/connection-integration/mysql-proto/) and local `D:/doris-cli/target/release/doriscli.exe` connectivity; lock resolves `PyMySQL==1.2.0`. | Use PyMySQL plus HTTP Stream Load for DDL/load and the compiled CLI for SQL, `EXPLAIN`, and profiles. |
| SQLAlchemy | `confirmed`, `observed` | [SQLAlchemy on PyPI](https://pypi.org/project/SQLAlchemy/) resolves stable `2.0.51`; prerelease 2.1 was not selected. | Retain it for PyIceberg's SQL catalog; do not add an application ORM layer. |
| pydoris | `supported`, `uncertain` | [pydoris on PyPI](https://pypi.org/project/pydoris/) resolves `1.2.0`, but no local like-for-like benchmark exists. | Keep as an optional adapter candidate, not a production dependency. |
| Arrow Flight SQL | `partial`: preflight/transport `observed`, explicit fallback `observed`, parameterized contract `blocked`, exact parity/performance `partial` | [Doris Arrow Flight SQL docs](https://doris.apache.org/docs/4.x/connection-integration/arrow-flight-sql/) label it experimental and require separate FE/BE ports. Preflight v2 observed FE `127.0.0.1:8070`, FE public socket `192.168.178.81:8070`, BE `127.0.0.1:8050`, both startup markers, base SHA-256 `ba6a6169e7ad352e635b0fac32fe23e4af8c4073b187a1464a0691681581a127`, current overlay SHA-256 `1b328f3a81a480bc97e6af2ad64bd7874d891bfb1f5cd3d5b2c631156f50c51f`, and rendered-config SHA-256 `4b01984a8d404afa56574f0dd1d3ad9d426c428b2ddf4da119624eab333a5c0a`. The complete reused-only report is `C:\Users\morph\AppData\Local\Temp\ddon-analytical-dwarf\analytical-flight\full-fallback-reused-v3\doris-flight-report.json`; ADBC 1.12.0 with PyArrow 25.0.0 observes both transports, all four Flight consumption modes, and the fallback, but the qmark probe remains blocked. The current matrix compares 76 common row-mode reports: 54 strict digests match and 22 differ only in MySQL `int` versus Flight `bool` representation of Doris `BOOLEAN` columns; row counts, order, schema, nulls, and values match. The current producer's FE-local `Location` remains a routing boundary, while BE DoGet and server logs are clean for the post-hint run. | Keep it out of default Compose, DDL, Stream Load, and semantic query paths. The fallback is diagnostic only and is not a parameterization substitute. Revisit the opt-in read profile only after exact type parity, FE-local endpoint routing, cold/warm point-query gates, and server profile/message-size evidence pass. |
| Doris Iceberg reader | `historical`, retired from active runtime | [Doris Iceberg catalog docs](https://doris.apache.org/docs/4.x/lakehouse/catalogs/iceberg-catalog/) were applied to the historical compatibility bridge and returned two index rows. | Retain as provenance and a possible future experiment only; the active loader and acceptance path are native Doris over direct Parquet. |

## Doris optimization review

The current design uses Doris as an analytical query engine, not as a generic row sink. The
optimization review therefore separates features that are structural requirements from features
that should be enabled only when a measured profile demonstrates a bottleneck.

| Technique | Status | Finding | Decision |
| --- | --- | --- | --- |
| Nereids RBO/CBO, predicate and column pushdown | `confirmed`, `observed` | The current 4.x [query optimizer guide](https://doris.apache.org/docs/4.x/query-acceleration/optimization-technology-principle/query-optimizer) describes RBO rewrites such as column/predicate/partition pruning followed by CBO; the page was updated 2026-05-17. Fixture `EXPLAIN` shows source predicates on both native and Iceberg scans. | Keep SQL source/offset predicates explicit, project only the columns needed by each query, and preserve the optimizer session settings in benchmark evidence. |
| Duplicate-key family tables | `confirmed`, `observed` | Doris recommends Duplicate for append-only detail data; the v9 fixture accepts it for all fourteen lossless/derived families. | Retain Duplicate; Unique/Aggregate would change lossless-record semantics. |
| Prefix/sort keys and bucketing | `supported`, corrected, `observed` on the high-value fixture, full effect `pending` | Doris's [schema guidance](https://doris.apache.org/docs/4.x/query-acceleration/tuning/tuning-plan/optimizing-table-schema/) says key order controls sorting/prefix pruning and bucketing must avoid skew. The already-loaded v9 fixture exposes offset-first keys and `HASH(unit_offset)` distribution; its source/name `EXPLAIN` touches all 16 tablets. A first live load of the revised DDL exposed Doris's key-prefix rule because the generated source-first keys were declared after family columns; the generator now reorders every duplicate-key definition to the physical schema prefix. Fresh database `dwarf_sourcefirst_20260805_b` accepted all fourteen tables, loaded eight high-value Parquet files with zero filtered rows, and `SHOW CREATE TABLE` confirmed source-first keys plus `HASH(source_id, unit_offset)` distributions. | Use source-first/offset keys for new tables because every store query is source-bound and the plan explicitly requires source-aware prefixes. The fresh tiny-fixture profile still touched all eight index tablets and returned one row, so no full-corpus latency improvement is claimed; the old v9 tables are not retroactively updated. |
| Bloom and inverted indexes | `confirmed`, `observed` | Doris's current [index guidance](https://doris.apache.org/docs/4.x/query-acceleration/tuning/tuning-plan/optimizing-table-index/) distinguishes automatic prefix/ZoneMap indexes from secondary Bloom, inverted, N-Gram Bloom, and bitmap indexes. Current DDL applies Bloom filters to source/offset and exact-name fields, plus inverted indexes to index, attribute, and derived-name columns; the native profile observes one returned/scanned row. | Keep Bloom for high-cardinality equality and inverted indexes for name/text lookup. Treat `EXPLAIN`/profile scan counts—not DDL presence—as the acceptance evidence; add N-Gram/bitmap only for a measured query pattern. |
| Statistics and CBO | `confirmed`, `observed` for native fixtures, `pending` for current promoted corpus | Doris records row count, NDV, min/max, null count, and size statistics; its [statistics guide](https://doris.apache.org/docs/4.x/query-acceleration/optimization-technology-principle/statistics) supports manual `ANALYZE` for native tables. The active loader submits native `ANALYZE` by default and can wait for terminal `SHOW ANALYZE` states through `DDON_DORIS_ANALYZE_WAIT_SECONDS`; historical Iceberg statistics measurements are not active evidence. | Keep post-load native `ANALYZE` explicit and record `SHOW TABLE STATS`, `SHOW COLUMN STATS`, `SHOW ANALYZE`, `SHOW AUTO ANALYZE`, and `__internal_schema.column_statistics`. Do not use the empty compatibility statistics views or silently add an unbounded wait. |
| Query profiles and OS telemetry | `confirmed`, `observed` | The current [query profile guide](https://doris.apache.org/docs/4.x/query-acceleration/query-profile) documents `enable_profile`, `profile_level=2` for detailed counters, and FE profile retrieval; the compiled `doris-cli` captured current v9 profiles. Native and Iceberg no-cache name lookups each returned/scanned one row and spilled zero bytes; total times were 13 ms and 105 ms, with Iceberg file-scan partition-pruning timing. | Enable profiles only for benchmark/evidence sessions, use level 2 for comparison, and retain `EXPLAIN`, no-cache cold profile, warm repetitions, scanned rows/bytes, peak memory, and spill status. The tiny fixture's native plan still touches all eight tablets, so selectivity remains a full-corpus question. |
| Apache Doris skills and CLI evidence loop | `observed`, current | Checked out `apache/doris-skills` at commit `aeeb2fe31071918257846b3d58ac09ffa151d4c1` and applied its evidence-first investigation, Duplicate-key, prefix-key, bucket-skew, Bloom/inverted-index, statistics, and profile-reading rules. The local Windows `doriscli 0.1.2` build at `apache/doris-cli` commit `e32ef58b48e0ef88c829177f3944574eadade47a` reports MySQL/HTTP connectivity, one alive BE, and Doris Compose 4.1.3 service health. CLI tablet detail for `dwarf_full_v9_20260806.full_index` reports eight NORMAL tablets, 452.8 MiB, and 1.10 skew; `SHOW CREATE` confirms source-first `DUPLICATE KEY`, `HASH(source_id, unit_offset)` buckets, ZSTD, Bloom filters, and an inverted name index. The no-cache `rLayout` profile is scan-bound at 224 ms with 145 rows scanned/returned, 33,492 bytes peak, and zero spills; the name-candidate comparison is 123 ms, one of four tablets, 145 rows, 29,952 bytes, and zero spills. | Keep the current source-first Duplicate-key families, explicit statistics, Bloom/inverted indexes, and measured optional name-candidate projection. Do not add a materialized view, N-Gram index, bucket rewrite, or session tuning until the complete v27 corpus repeats the profile comparison; the current evidence proves a candidate projection benefit but not a full-corpus acceptance win. |
| Materialized views | `supported`, `deferred` | Doris positions materialized views for query acceleration and lightweight ETL in the [materialized-view overview](https://doris.apache.org/docs/4.x/query-acceleration/materialized-view/intro-link/). The producer already emits source-bound definition and method indexes in the same pass. | Do not add a duplicate MV by default. Evaluate one only if full-export profiles show a repeated join/aggregation hotspot that the derived index cannot cover. |
| Local Parquet loading | `confirmed`, `observed` | Doris's current [load overview](https://doris.apache.org/docs/4.x/data-operate/import/load-manual) recommends Stream Load or Doris Streamloader for local files, Broker Load/`INSERT INTO SELECT` for object-storage or lake files, and Catalog + `INSERT INTO SELECT` for external Iceberg. The v9 native run loaded all eight populated files with zero filtered rows. | Retain HTTP Stream Load for the fixture and small/medium files; benchmark Streamloader, concurrent labeled Stream Loads, and catalog `INSERT INTO SELECT` for the full corpus if file count or transaction overhead dominates. |
| Iceberg layout and pruning | `confirmed`, `observed`, revised | Doris's [Iceberg guidance](https://doris.apache.org/docs/4.x/lakehouse/best-practices/doris-iceberg) demonstrates Parquet, Zstandard, partition pruning, and catalog queries. v9 shows one split, one scan range, 4,036 bytes, and source/name predicate pushdown against the historical bucketed file layout. The new bounded family-layout probe publishes one source-scoped file per family and retains physical `unit_bucket` values for row-group statistics. | Keep Parquet as the physical format and source-scoped family tables. Use `unit_bucket` directory/Iceberg partitioning only when full-corpus profiles demonstrate that its pruning benefit outweighs writer churn and file count. |
| Unsigned Parquet-to-Doris values | `observed`, corrected | The pre-fix full-shape fixture exposed a Doris Iceberg `UINT64` to `BIGINT` cast failure at `11331043433964896261`. The corrected high-value fixture stores `18446744073709551615` as Arrow/Parquet `decimal128(20,0)`; Doris 4.1.3 completed all eight Iceberg `ANALYZE` jobs and a no-cache predicate returned the exact value via `CONCAT`, with one scanned row and no spills. | Keep `DECIMAL(20,0)` as the canonical physical representation for nonnegative DWARF integers and map native Doris columns to `LARGEINT`; add a regression whenever a new analytical reader is introduced. |
| Arrow Hive partition typing | `observed`, corrected | Automatic dataset discovery of the historical bucketed fixture failed because `unit_bucket=...` directory values were inferred as `int32` while physical rows use `int64`. An explicit `source_id: string`/`unit_bucket: int64` Hive partition schema succeeds for bucketed stores, while the canonical family layout uses only a `source_id: string` partition and reads `unit_bucket` from the physical schema. | Keep the lossless `int64` physical field and require the layout-specific typed partition adapter; do not narrow source-offset-derived metadata merely to satisfy directory inference. |
| JSONL-to-Parquet backfill writer lifecycle | `observed`, corrected | Existing complete JSONL stores now backfill through the same bounded `ParquetRecordSink` as direct materialization. The backfill honors manifest `parquet_layout` and `max_open_writers`, records writer metrics, validates closed payloads, and publishes the projection through the existing temporary-directory replacement. Two focused regressions pass for bucketed one-writer rotation and outer-manifest metadata. | Keep JSONL as an audit/interchange projection only; do not reintroduce a second unbounded `ParquetWriter` loop. Measure any alternative Arrow dataset writer separately before changing the canonical sink. |
| Family/source Parquet writer layout | `observed`, bounded, lifecycle insufficient | The real-ELF `bounded-family-v20-64-20260806` probe used the pre-rotation family layout with 64 CUs, direct Zstandard Parquet, no JSONL, and `--max-open-writers 16`. It published 12 closed family/source files, 380 row groups, 148,600,334 Parquet bytes, zero parser errors, `peak_open_writers=12`, and zero rotations. `inspect-dwarf-store --allow-incomplete` validated every declared hash, footer, row group, and compressed payload; independent Arrow reads preserved physical `unit_bucket` values. | Family/source partitioning is useful, but a long-lived writer is not accepted. The next bounded probe must exercise the new CU-boundary rotation before another full traversal. |
| Long-lived family writer — v21 | `rejected`, native crash | The full `full-direct-v21-family-20260806` run used family/source layout and 16 open writers without CU-boundary rotation. After about 112 minutes, Windows Error Reporting recorded the same Python 3.14 / `pyarrow\\lib.cp314-win_amd64.pyd` access violation (`0xc0000005`, offset `0x16a8f0`). The 12 staged Parquet files totalled 2,654,381,412 bytes, including a 1,345,961,777-byte attribute file; every file lacked a readable footer and no manifest was published. | This disproves the assumption that family partitioning alone makes a full run safe. The staged prefix is rejected; rotate and close writers at a bounded CU interval, then revalidate on a real-ELF probe. |
| CU-boundary Parquet rotation | `observed`, bounded | The direct sink closes family writers at a configurable CU interval (default 64), increments `cu_boundary_rotations` separately from checkpoint rotations, and continues with numbered parts. Real-ELF `bounded-family-rotation-v22-64-20260806` completed 64 CUs in 384 seconds with 12 closed files, `cu_boundary_rotations=1`, zero parser errors, and independent footer/payload validation. | This authorizes a full attempt with the rotation enabled. Full-corpus file count, load cost, and query/header parity remain unobserved. |
| Replacement full Parquet traversal — v23 family rotation | `rejected`, Python runtime crash | The fresh `full-direct-v23-family-rotate64-20260806` run started at 19:51:47 CEST with direct typed Zstandard Parquet, no JSONL/checkpoint, family/source layout, 16 open writers, and 64-CU boundary rotation. It terminated at 21:13:55 CEST with Windows Error Reporting reporting `python.exe` access violation `0xc0000005` in `python314.dll` at offset `0x11b5e9` (process 20412). The prefix contains 162 Parquet files: 152 readable footers covering 272,002,245 rows and 4,490 row groups, plus ten truncated `part-00015` files (one per family); no manifest was published. The complete staged directory contained 173 files and 2,701,475,635 bytes. | CU-boundary rotation prevents the earlier long-lived `pyarrow` writer crash through multiple boundaries, but it does not yet make the full producer reliable. The prefix is not a store and cannot be queried, loaded, or used for parity. Do not repeat the full traversal with the same CPython 3.14/native path; first run a bounded crash-isolation/profiling probe and decide whether the runtime or native Arrow boundary must change. |
| Profiler-led materializer crash isolation — v24 | `observed`, bounded with explicit profiler limits | The new `performance profile-materializer` command ran isolated 8-CU direct-Parquet targets. cProfile completed in 135.0 seconds and its self-time leaders were `parquet.py:_flush_buffer`, `parquet_rows.py:_value_columns`, `parquet_rows.py:_attribute_row`, `unit_emitter.py:_write_attributes`, `record_sink.py:write`, and `parquet.py:write`. Scalene 2.3.0 completed the producer but exited 1 during publication; 88.5% of sampled CPU was its eval wrapper, so its line attribution is not actionable. A manual `py-spy 0.4.2` attach to the same bounded producer captured 749 samples with zero sampling errors; exact leaves again concentrated in `_flush_buffer` (203 samples across lines 185/188), `_value_columns` (52), `_scalar_value_columns` (51), `dwarf_recovery.py:read` (27), `pyarrow.parquet.write_table` (17), and `unit_emitter.py:_value` (16). | This is valid producer localization, not a full-run reliability result. cProfile and py-spy support measuring batching/serialization changes; Scalene remains process/memory evidence only on Windows/CPython 3.14. A bounded stress probe must isolate the native/runtime crash before another full traversal. |
| Bounded CU-rotation stress — v25 | `observed`, partial and payload-validated | `bounded-family-rotation-v25-256-r16-20260806` completed normally after 256 CUs with direct typed Zstandard Parquet, no JSONL, family/source layout, `--max-open-writers 16`, and `--rotate-writers-every-cus 16`. Its source-bound manifest records 12,787,238 DIEs, 36,300,455 attributes, 18,914,069 references, 4,752,377 index rows, 4,708,022 names, 256 units, zero parser errors, 16 CU-boundary rotations, `peak_open_writers=12`, 162 Parquet files, 1,399 row groups, and 79,716,446 rows. An independent Arrow batch read of every column completed without errors in 3.436 seconds; all codecs were ZSTD and the files totalled 526,580,562 bytes. | This materially validates repeated writer close/reopen and payload integrity across four times the v22 CU interval, and it did not reproduce the v18/v21/v23 crash path. The manifest is intentionally `partial` because `--max-cus 256` stopped before all 2,305 CUs; the store remains diagnostic-only and cannot serve generation, knowledge export, Doris, Iceberg, or completeness evidence. |
| Bounded v25 query contract | `observed`, partial diagnostic | `performance benchmark-dwarf-store --allow-incomplete` loaded the v25 manifest source-bound and queried the file projection. The `rLayout` prefix returned 17 definitions, while the same run reported `partial` for all analytical query results; the report is `C:\Users\morph\AppData\Local\Temp\ddon-analytical-dwarf\query-bounded-v25-20260806\benchmark-report.json`. File lookup was a 162-file/1,399-row-group scan, with a 0.041-second cold and 0.038-second warm definition query in the diagnostic process. | The 17 matches are only the first 256 CUs and cannot be compared as complete `rLayout` parity. No generated header, knowledge export, Doris load, or backend acceptance may consume this report. |
| Bounded CU-rotation stress — v26 | `observed`, partial and payload-validated | `bounded-family-rotation-v26-1024-r16-20260806` completed normally with `PYTHONFAULTHANDLER=1` after 1,024 CUs using direct typed Zstandard Parquet, no JSONL, family/source layout, `--max-open-writers 16`, and `--rotate-writers-every-cus 16`. The source-bound manifest records 47,292,085 DIEs, 133,994,692 attributes, 69,926,012 references, 17,482,544 index rows, 17,271,294 names, 1,024 units, zero parser errors, 64 CU-boundary rotations, `peak_open_writers=12`, 642 Parquet files, 5,190 row groups, 294,968,826 rows, and 1,960,707,231 Parquet bytes. `inspect-dwarf-store --allow-incomplete` exited 0; an independent Arrow read of every column verified all 642 files in 12.776 seconds with no row mismatch or payload error, and all codecs were ZSTD. No new WER dump was created. | This is the cumulative reliability gate for the 16-CU rotation and direct native path, not a complete store: 1,024 of 2,305 CUs were traversed. It cannot serve generation, knowledge export, Doris, Iceberg, or completeness/header parity evidence. |
| Bounded v26 query contract | `observed`, partial diagnostic | `performance benchmark-dwarf-store --allow-incomplete` loaded the v26 manifest and returned 96 `rLayout` definitions from the 1,024-CU prefix. The report is `C:\Users\morph\AppData\Local\Temp\ddon-analytical-dwarf\query-bounded-v26-20260806\benchmark-report.json`; the file definition query took 2.663 seconds cold and 0.434 seconds warm, scanning the 642-file projection. | The 96 matches demonstrate increased prefix coverage but are not complete `rLayout` parity; the benchmark explicitly reports `partial` and the store remains barred from generation, knowledge export, Doris, Iceberg, and acceptance. |
| Windows dump analysis — v18/v21/v23 | `observed`, diagnostic | Windows Error Reporting retained Python dumps for PIDs 31944, 22356, and 20412 under `C:\Users\morph\AppData\Local\CrashDumps`. CDB 10.0.22621.755 `!analyze -v` found the same invalid-pointer read at `lib.cp314_win_amd64+0x16a8f0` in v18 and v21, with `arrow_python!arrow::py::ConvertPySequence` callers; v23 faulted at `python314!Py_HandlePending+0x11b9` with Arrow/PyArrow modules loaded. | The WER files are mini-dumps and cannot prove the original heap-corrupting write. The effective existing system policy is the `CrashDumps` directory; an HKLM per-app full-dump override requires elevation and the attempted HKCU override is unsupported. Future bounded profiler children set `PYTHONFAULTHANDLER=1`, and CDB/WinDbg remains the crash evidence path. |
| Live partial-file querying | `rejected` for normal runtime; checkpoint path `observed` on deterministic interruption | The active v6 producer had 202 open files and 1.38 GB of visible bytes at one probe, but all Parquet footer reads failed because the writers had not closed. The new opt-in checkpoint path closes and rotates writers, records an immutable Parquet file list, preserves `checkpoint.json` after interruption, and returns `partial` query status when explicitly loaded. | Keep atomic publication and fail-closed runtime semantics. Use `--checkpoint-every-cus N` only for diagnostic snapshots; measure its rotation overhead before any production benchmark. |
| DIE-offset lookup shape | `supported`, optimization `pending` | The source-bound query contract accepts a DIE offset without a CU offset. On the tiny existing native fixture, a no-cache profiled `source_id + die_offset` lookup returned one row with a 66 ms scan operator and 535 ms total time, while adding `unit_offset` returned one row with a 31.6 ms scan operator and 72 ms total time. The fixture is too small for a latency claim, but the access-path difference is real evidence that a wide DIE fact table alone may not be the best global-offset lookup structure. | Keep the canonical DIE fact table lossless. Measure a narrow `die_locator(source_id, die_offset, unit_offset, ordinal, is_null)` projection—distributed and keyed by source/DIE offset—only if representative profiles show global DIE lookups dominate; do not duplicate it speculatively before the full query suite is available. |

| Store line-program facade | `observed`, corrected | The typed `line` family already contained source-file and state rows, but the first runtime adapter returned an empty line program. The corrected JSONL/Parquet facades reconstruct file indexes, directories, line entries, and extended-command state from those rows without a live ELF session. | Full real-asset declaration-file and header parity is still required before the file runtime can pass the acceptance gate. |

The main challenge to the current setup is therefore not another generic index. It is statistics,
file sizing, and load-method selection at full-corpus scale. Native Doris can be optimized further,
but the acceptance gate must compare those variants using profiles rather than assuming that a
secondary index helps a tiny fixture.

## Research conclusions

1. `[confirmed, observed]` A CU is the indivisible correctness boundary. The canonical producer performs one explicit CU traversal and derives every index from that pass.
2. `[supported, observed]` A typed flat logical record stream is a better interchange contract than a nested object dump. Parquet/Iceberg receive those rows directly; JSONL remains an opt-in audit and fixture contract rather than a mandatory production intermediary. Parent/child and reference edges make the graph explicit while preserving original offsets.
3. `[confirmed, observed]` Raw bytes are chunked and checksummed outside individual JSON records. This preserves unsupported data without requiring a 30 GB in-memory representation.
4. `[confirmed]` Names are query attributes, not identities. Source identity, section, CU offset, DIE offset, and traversal ordinal are the stable keys.
5. `[supported]` The existing compressed LLVM text index is useful cross-check evidence but cannot be the authoritative replacement because it is a presentation format and does not preserve all attributes and sections.
6. `[deferred]` Graph algorithms remain deferred until the analytical query workload demonstrates a need; the materialization contract does not depend on them.
7. `[supported, observed]` Doris table design is family-specific: immutable rows use `DUPLICATE KEY`; source-first keys then bounded numeric offsets preserve source pruning and offset locality; high-cardinality equality columns use Bloom filters and name searches use inverted indexes. Parquet stores nonnegative DWARF integers as exact `DECIMAL(20,0)` and native Doris exposes them as `LARGEINT`; heterogeneous values remain value columns and never become keys or distribution columns.
8. `[observed]` The compiled `D:\doris-cli\target\release\doriscli.exe` is the preferred local evidence client for SQL, profiles, and tablet inspection. The installed npm wrapper reports unsupported `win32-x64`, so it is not treated as an available Windows executable.
9. `[observed]` The current producer emits typed range, location, line, macro, frame, abbreviation, and name families in the same traversal. Macro sections are represented as checksummed `raw_only` rows when pyelftools 0.33 does not expose a public decoder; raw bytes remain authoritative for that family until a decoder is selected.

## Compatibility gates

- `[confirmed]` pyelftools 0.33 imports under CPython 3.14.6 and retains the required CU/DIE API behavior.
- `[observed]` JSONL records round-trip without lossy stringification on fixtures.
- `[observed]` Parquet and Iceberg outputs preserve fixture counts, offsets, forms, and ordering.
- `[observed]` Doris native and Iceberg current v9 fixture query suites execute; full real-corpus query parity is still pending.
- `[observed]` A `2^64-1` attribute value round-trips through direct Parquet, Doris native schema generation, Doris-over-Iceberg filtering, and Iceberg `ANALYZE`; the earlier unsigned-to-`BIGINT` failure is retained as pre-fix evidence rather than hidden.
- `[pending]` The generated `rLayout.h` still needs comparison with the approved real-asset baseline, which is currently unavailable.
- `[observed]` The complete v27 knowledge export is source-bound, deterministic, internally byte-stable with the generated header after the documented include-guard normalization, and has no unresolved closure diagnostics.
- `[confirmed]` Every external tool or service reports `observed`, `partial`, `blocked`, or `unavailable` status in evidence.
- `[observed]` Full-corpus materialization does not require a JSONL staging pass; the same typed sink feeds Parquet/Iceberg directly and Doris loads that output without reparsing the ELF.

## Doris skill and CLI operating loop

The [Apache Doris skills repository](https://github.com/apache/doris-skills) was used as the
optimization checklist, and the compiled [Apache Doris CLI](https://github.com/apache/doris-cli)
at `D:\doris-cli\target\release\doriscli.exe` was used for live evidence. The repeatable loop is:

1. Inspect the generated DDL and key order with `SHOW CREATE TABLE`.
2. Run `EXPLAIN` for each access shape, including source/CU/DIE lookup and name-only lookup.
3. Run a no-cache query with profiling enabled and capture query ID, scanned rows/bytes, operator
   time, memory, spills, and tablet count.
4. Inspect tablet distribution and statistics before proposing a key, bucket, Bloom, inverted
   index, or materialized-view change.
5. Compare the same query contract against direct Parquet and Doris only after the store is
   complete and source-bound.

The live source-first fixture follows this loop. It uses `DUPLICATE KEY` to preserve lossless
records, puts `source_id` and `unit_offset` first in the physical key, distributes by those same
columns, and uses secondary indexes only for measured equality/name access. Exact CU-scoped DIE
lookup pruned to 1/16 tablets, while source/name lookup touched 8/8 tiny index tablets because the
CU predicate is unavailable. The latter is a reason to measure a derived serving path or MV on the
full corpus, not a reason to add one speculatively to a two-row fixture.

The CPU loop is similarly evidence-gated. The repository `performance` runner invoked the same
benchmark workload under cProfile and Scalene. cProfile supplied method/line attribution and
identified repeated Parquet row scans; the resulting CU-aware hydration, child memoization, and
tag-only projection reduced the profiled CPU from about 9.73 s to 3.49 s (3.71 s process wall).
Scalene retained process
and memory evidence, but its Windows/CPython run has not produced an actionable application-line
hotspot; the normalizer excludes the launcher wrapper and the fresh run's only ranked source line
was import-time class setup. No
Doris schema change is accepted from the current fixture-scale evidence alone.

The live `py-spy` stack of the long-running pre-refactor header worker then confirmed the repeated
`find_definitions` → `_candidate` → `child_tag_counts` → Parquet `_rows` path. The current adapter
primes missing definition-parent tag counts in one projected scan. On the complete store this
reduced the store-port cold `rLayout` lookup from 349.532 s / 21.327 GB read to 42.985 s / 2.812 GB
read while retaining 145 ordered matches. A fresh C:-temp Doris profile still showed MySQL response
reads dominating wall time; Scalene's only ranked source line was an import-time native attribution
at `infrastructure/elf_session.py:20`, so it is not used as a Doris or Python hotspot.

The fresh header trace also showed CU-unscoped reference and child scans during array/type parsing.
The adapter now carries the known DIE CU into those filters, activating the existing
`unit_bucket` partition pruning. The process that produced the trace predates this edit, so the
effect remains pending a fresh header-parity run.

The first fresh current-code full-store definition query exposed a second Arrow scan-shape issue:
one 145-value cross-partition attribute `IN` expression repeatedly raised a Zstandard decompression
error, while the same files and values succeeded when read one `unit_bucket` at a time. Index
hydration now uses one DIE query plus bucket-scoped attribute batches, retries without Arrow
threads, and recursively splits a CU batch when the predicate remains too wide. The current query
returned all 145 ordered matches in 16.819 seconds; cProfile reports 17.856 seconds, 178 `_rows`
calls, 13.489 seconds in indexed hydration, and 2.531 seconds in child-count priming, compared with
45.973 seconds, 577 scans, 27.255 seconds, and 15.493 seconds before the change. The result is a
query-adapter improvement, not yet header-parity evidence.

A subsequent full-payload audit changed the evidence boundary. PyArrow 25.0.0 can read the v9
attribute file footer and most row groups, but `unit_bucket=7/part-00000.parquet` row group 10
fails even when read directly, specifically in the `decoded_value_kind` column. The manifest hash
is stable, so footer/hash validation alone did not prove readable compressed pages. Complete
publication now reads every closed row group before it can be accepted; the v9 store is rejected
for header, Iceberg, and full-benchmark acceptance until a replacement traversal passes this gate.

The current-code bounded real-ELF probe closes the schema boundary without weakening the
completeness boundary: one CU produced 392 DIEs, 1,276 attributes, 206 index rows, and valid
Zstandard Parquet footers under a source-bound `partial` manifest. The matching benchmark refused
Doris, Iceberg, and knowledge export as designed. A C:-temporary Scalene 2.3.0 run over the same
store retained 147 samples and ranked only import-time class setup at `zstd_dump_parser.py:36`, so
no new CPU optimization is inferred from it.

## Full-corpus Doris decision (2026-08-07)

The v27 replacement changes the canonical-store conclusion. One source-bound traversal now
publishes a complete direct Parquet store: 2,305 CUs, 596,944,504 rows, 1,451 closed Zstandard
files, 10,611 row groups, and zero parser errors. Strict store inspection and an independent
Arrow payload read both pass. The source-bound recovery profile is retained in the manifest as an
explicitly authorized six-substitution overlay supported by the preserved LLVM textual dump; it
does not change raw-section bytes or provenance.

The full native Doris load into `dwarf_full_v27_20260807` also passes row-count parity: 1,451
successful Stream Loads, zero filtered rows, and exact counts for all fourteen families. The
compiled `doriscli 0.1.2` reports finished statistics for every canonical table and the separately
provisioned name candidate, all tablets `NORMAL`, with skew no worse than 3.0. The measured
serving decision is now evidence-based at corpus scale:

- The canonical source-first `DUPLICATE KEY` families remain lossless and support source/CU/DIE
  point access. The exact `full_die` lookup prunes to 1/16 tablets and returns one row.
- The global name path is a distinct access shape. Base `full_index` touches 8/8 tablets and the
  profiled `rLayout` lookup scans 153.72 MB; the opt-in `(source_id, name)` candidate touches 1/4
  tablets and scans 30.38 MB. Five no-cache CLI runs are 149 ms p50 versus 9 ms p50, with 145
  ordered rows on both paths. The candidate is therefore useful for rLayout-style serving, but
  it remains an explicit projection rather than a canonical lossless family.
- Native and Doris-over-Iceberg have ordered parity across the 36-query `rLayout`/`MtObject`
  contract. Iceberg references all 1,451 Parquet files without copying them and preserves the
  exact 596,944,504 snapshot row count, but its 291.340-second query wall is far above native's
  3.664 seconds. Iceberg is the interchange/reference surface; native Doris is the serving
  backend.

The current generic Parquet query harness timed out after 15 minutes because it rescans full fact
datasets for each query/iteration. That is a benchmark-shape problem, not evidence against the
complete store. An explicit live pyelftools baseline is now observed for the same source: with a
180-second search bound, `rLayout` reached a complete candidate after 1,534 CUs at 151.102 seconds
cold and 167.795 seconds warm, with 18.16 GB peak RSS. This is a single-symbol legacy lookup
baseline, not a full header/query-contract baseline. The first store-backed header run completed
in 922.901 seconds and a second fresh run completed in 932.357 seconds with the same 63,167-byte
SHA-256, proving current internal determinism. The approved historical `rLayout.h` baseline is
still not present, so historical byte parity remains blocked and the complete 110%-of-baseline
acceptance comparison is not closed. The corrected knowledge export completed in 935.1 seconds
and published a source-bound
`complete` manifest with 1,155 nodes, 2,078 relationships, and reconstructed C++; the six earlier
diagnostics disappeared after the exporter began classifying present target DIEs and failing closed
when a target is absent. This closes the knowledge-export completeness gate without weakening raw
DWARF evidence.

The profiling order remains important: cProfile and py-spy supplied the actionable method/line
localization for Parquet flush and row projection; Scalene supplied process/memory evidence but
no trustworthy application-line hotspot on Windows/CPython 3.14. Doris schema changes were
accepted only after `EXPLAIN`, no-cache profiles, statistics, tablet inspection, and ordered query
parity. No MV, N-Gram index, bucket rewrite, or session tuning is justified.

## Historical full-corpus Doris decision (2026-08-06)

The complete v9 store removes the fixture-scale uncertainty from the serving decision. The
source-bound manifest contains 2,305 CUs and 596,944,504 typed rows in 413 closed Zstandard
Parquet files. Native Doris loaded the same files into 14 `DUPLICATE KEY` family tables with zero
filtered rows; all family counts, table statistics, and tablet states match the manifest.

The measured access paths are deliberately split:

- Source/CU/DIE lookup is a native-table point path: `EXPLAIN` prunes `full_die` to 1/16 tablets.
- Name-only definition lookup cannot use the CU prefix. Base `full_index` touches 8/8 tablets,
  while the separately provisioned four-tablet `full_index_name_candidate` projection routes by
  `(source_id, name)` and cuts the no-cache profiled scan from about 155 MB to 34 MB. Results for
  `rLayout` and `MtObject` are ordered-identical. The full 36-query application suite improves
  only about 3.7%, so this projection remains opt-in rather than a new canonical family.
- Doris-over-Iceberg preserves the same data without copying the Parquet files, but its complete
  name lookup opens 382 file splits and is seconds slower. It is therefore the lakehouse/reference
  interface; native Doris is the required serving backend for low-latency lookups.

This applies the Doris skills workflow: inspect DDL and prefix order, explain each access shape,
capture no-cache and warm profiles, inspect tablet skew/statistics, and accept a schema/index
variant only when the paired profile and ordered query results support it. The current evidence
does not support a generic materialized view, bucket-count rewrite, or extra index. The one
measured serving projection is supported by a source-bound environment override, but its creation
and refresh must remain explicit until a repeatable lifecycle is implemented.

The Python performance loop is separate from Doris diagnosis. cProfile identifies method/line
cost in the repository benchmark runner; Scalene is retained for process/memory evidence but
produces no application-file line attribution under Windows/CPython 3.14. Doris CLI BE profiles
remain authoritative for scan bytes, tablet/file fanout, operator time, memory, and spill claims.

The subsequent Parquet query refactor was verified against the complete store rather than inferred
from a timing sample: batched definition hydration returned all 145 `rLayout` matches in 0.692 s
cold and 0.804 s warm through the direct typed Parquet path, and the duplicate-index-row test
preserves multiplicity. This improves the correctness backend's per-query scan pattern; it does
not change the decision that native Doris is the serving backend, and it does not satisfy the
unobserved 110%-of-baseline gate.
