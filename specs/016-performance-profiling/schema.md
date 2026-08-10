# Performance history schema contract v1

The SQLite database is `resources/performance/benchmarks.sqlite3`. `schema_meta.schema_version`
and SQLite `user_version` are both `1`. Existing unsupported versions are rejected rather than
silently migrated.

## Tables

| Table | Contract |
| --- | --- |
| `schema_meta` | `key`/`value` migration metadata and schema version |
| `runs` | workload, cold/warm state, status, timestamp, return code, Git, Python/platform/machine, runtime implementation/name/GIL state, source identity, configuration fingerprint, profiler mode, manifest path |
| `metrics` | typed integer/real/text/null value, unit, evidence status, bounded detail |
| `method_metrics` | profiler, rank, method/line identity, file/line, timing, call count, memory, Scalene CPU percentage |
| `artifacts` | profiler, format, external path, size, SHA-256, tool version, status, detail |

Foreign keys from all evidence tables to `runs` use `ON DELETE CASCADE`. The application replaces a
run's child rows transactionally when a manifest is enriched with normalized method summaries.

## Status and comparison

`observed`, `partial`, `unavailable`, `blocked`, and `not_observed` are distinct values. A
comparison key is workload, cold/warm state, source identity, Python version, runtime name/
implementation/GIL state, platform, machine profile, configuration fingerprint, and profiler mode.
Real-asset rows are report-only; fixture budgets are explicit code/test thresholds. Runtime columns
were added additively within schema v1 so existing ledgers remain readable.
