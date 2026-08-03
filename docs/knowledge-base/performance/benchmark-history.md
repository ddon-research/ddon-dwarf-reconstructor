# Benchmark history

This page is generated from `resources/performance/benchmarks.sqlite3`. Raw profiler outputs remain in the OS-local performance artifact directory.

Evidence statuses are `observed`, `partial`, `unavailable`, `blocked`, or `not_observed`. Real-asset rows are report-only; deterministic fixture budgets are gated by their explicit performance command.

## Latest like-for-like baselines

| Workload | State | Profiler | Status | Wall time (s) | Peak RSS (MiB) | Read (MiB) | Write (MiB) | Started |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| cold-dump-index | cold | process-sampler | not_observed | 2.012 | 809.070 | 1434.723 | 0.019 | 2026-08-03T21:37:08.244556+00:00 |
| cold-dump-index-rebuild | cold | process-sampler | observed | 275.139 | 770.086 | 10907.381 | 9125.749 | 2026-08-03T21:41:37.689664+00:00 |
| fixture | warm | pyperf | observed | 13.544 | 137.488 | 5.752 | 0.001 | 2026-08-03T21:52:05.762718+00:00 |
| warm-rlayout | warm | cprofile | observed | 4.554 | 1276.117 | 1435.581 | 2.052 | 2026-08-03T21:32:36.962886+00:00 |
| warm-rlayout | warm | pyinstrument | observed | 4.346 | 1408.703 | 1435.952 | 1.590 | 2026-08-03T21:32:41.608485+00:00 |
| warm-rlayout | warm | scalene | observed | 4.746 | 1640.344 | 1446.867 | 2.726 | 2026-08-03T21:32:32.099300+00:00 |
| warm-rlayout | warm | tracemalloc | observed | 44.480 | 1540.742 | 1435.623 | 1.558 | 2026-08-03T21:32:46.027046+00:00 |
| warm-rlayout-py-spy | warm | py-spy | partial | 0.621 | 50.160 | 5.350 | 0.000 | 2026-08-03T21:49:23.600696+00:00 |

## Latest like-for-like deltas

| Workload | State | Profiler | Status | Wall delta (s) | RSS delta (MiB) | Read delta (MiB) | Write delta (MiB) |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| fixture | warm | pyperf | observed | -0.162 | -0.047 | 0.000 | 0.000 |

## Tool availability

| Tool | Status | Version | Detail |
| --- | --- | --- | --- |
| cprofile | observed | 3.14.6 | — |
| process-sampler | observed | built-in | — |
| psutil | not_observed | — | no artifact recorded |
| py-spy | partial | py-spy 0.4.2 | profiler did not publish the expected output |
| pyinstrument | observed | pyinstrument 5.1.3, on Python 3.14.6 | — |
| pyperf | observed | 2.10.0 | — |
| scalene | observed | Scalene version 2.3.0 (2026.05.08) | — |
| tracemalloc | observed | 3.14.6 | — |

## Method-level evidence

The database retains normalized top-N method or line summaries. Follow each run's manifest path for the checksummed raw profile when it is available.
