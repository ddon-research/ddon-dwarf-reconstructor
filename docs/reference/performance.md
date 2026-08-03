# Performance command reference

The `performance` group is the canonical opt-in resource and profiler interface:

| Command | Purpose |
| --- | --- |
| `performance doctor` | Probe tools and report evidence paths |
| `performance profile <elf>` | Run a named profiler around the canonical reconstruction CLI |
| `performance profile-index <dump>` | Profile a complete compressed-dump index rebuild |
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

## Metric contract

The process runner samples the complete child process tree with psutil. It records wall time, CPU
user/system seconds, peak RSS/VMS, read/write bytes and operation counts, sample count, and bounded
capture indicators. `tracemalloc` current/peak values are separate `traced_*` metrics and must not
be interpreted as total process RSS.

## Artifact contract

Raw profiles (`.json`, `.prof`, Speedscope), sample streams, and bounded child output live under
`DDON_PERFORMANCE_ARTIFACT_DIR` or the OS-local default. Each run manifest records the external
path, size, SHA-256, tool version, format, and evidence status. The tracked database stores only
summaries, method aggregates, and checksummed references.

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
