# Benchmark history

This page is generated from `resources/performance/benchmarks.sqlite3`. Raw profiler outputs remain in the OS-local performance artifact directory.

Evidence statuses are `observed`, `partial`, `unavailable`, `blocked`, or `not_observed`. Real-asset rows are report-only; deterministic fixture budgets are gated by their explicit performance command.

## Latest like-for-like baselines

| Workload | State | Runtime | Profiler | Status | Wall time (s) | Peak RSS (MiB) | Read (MiB) | Write (MiB) | Started |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| cold-dump-index | cold | cpython-3.14.6 | process-sampler | not_observed | 2.012 | 809.070 | 1434.723 | 0.019 | 2026-08-03T21:37:08.244556+00:00 |
| cold-dump-index-rebuild | cold | cpython-3.14.6 | process-sampler | observed | 275.139 | 770.086 | 10907.381 | 9125.749 | 2026-08-03T21:41:37.689664+00:00 |
| fixture | warm | cpython-3.14.6 | pyperf | observed | 13.544 | 137.488 | 5.752 | 0.001 | 2026-08-03T21:52:05.762718+00:00 |
| runtime-compare-cpython | warm | cpython-3.14.6 | process-sampler | observed | 2.270 | 1626.246 | 1435.611 | 1.578 | 2026-08-03T22:34:23.428821+00:00 |
| runtime-compare-cpython | warm | cpython-3.14.6 | process-sampler | observed | 2.275 | 1404.879 | 1435.611 | 1.578 | 2026-08-03T22:34:25.810695+00:00 |
| runtime-compare-cpython | warm | cpython-3.14.6 | process-sampler | observed | 2.272 | 1405.012 | 1434.798 | 0.893 | 2026-08-03T22:34:28.154871+00:00 |
| runtime-compare-cpython | warm | cpython-3.14.6 | process-sampler | observed | 2.066 | 1644.762 | 1435.611 | 1.589 | 2026-08-03T22:37:06.434524+00:00 |
| runtime-compare-cpython | warm | cpython-3.14.6 | process-sampler | observed | 2.060 | 1601.949 | 1434.798 | 1.311 | 2026-08-03T22:37:08.610892+00:00 |
| runtime-compare-cpython | warm | cpython-3.14.6 | process-sampler | observed | 2.068 | 1705.656 | 1435.611 | 1.589 | 2026-08-03T22:37:10.737747+00:00 |
| runtime-compare-cpython | warm | cpython-3.14.6 | process-sampler | observed | 2.059 | 1481.871 | 1435.323 | 1.304 | 2026-08-03T22:41:17.053857+00:00 |
| runtime-compare-free-threaded | warm | cpython-3.14.6-free-threaded | process-sampler | partial | 0.211 | 8.242 | 0.000 | 0.000 | 2026-08-03T22:34:39.372060+00:00 |
| runtime-compare-free-threaded | warm | cpython-3.14.6-free-threaded | process-sampler | partial | 0.211 | 7.723 | 0.000 | 0.000 | 2026-08-03T22:34:39.655867+00:00 |
| runtime-compare-free-threaded | warm | cpython-3.14.6-free-threaded | process-sampler | partial | 0.211 | 7.914 | 0.000 | 0.000 | 2026-08-03T22:34:39.942170+00:00 |
| runtime-compare-free-threaded | warm | cpython-3.14.6-free-threaded | process-sampler | observed | 2.268 | 1626.641 | 1435.613 | 1.602 | 2026-08-03T22:37:20.286009+00:00 |
| runtime-compare-free-threaded | warm | cpython-3.14.6-free-threaded | process-sampler | observed | 2.268 | 2003.883 | 1435.359 | 1.505 | 2026-08-03T22:37:22.623924+00:00 |
| runtime-compare-free-threaded | warm | cpython-3.14.6-free-threaded | process-sampler | observed | 2.268 | 2016.426 | 1435.359 | 1.342 | 2026-08-03T22:37:24.959216+00:00 |
| runtime-compare-free-threaded | warm | cpython-3.14.6-free-threaded | process-sampler | observed | 2.270 | 2034.434 | 1435.616 | 1.593 | 2026-08-03T22:41:31.271189+00:00 |
| runtime-compare-nuitka | warm | nuitka-cpython-3.14.6 | process-sampler | observed | 3.090 | 1512.406 | 1427.982 | 69.742 | 2026-08-03T22:34:30.499604+00:00 |
| runtime-compare-nuitka | warm | nuitka-cpython-3.14.6 | process-sampler | observed | 3.090 | 1496.203 | 1427.982 | 69.742 | 2026-08-03T22:34:33.657887+00:00 |
| runtime-compare-nuitka | warm | nuitka-cpython-3.14.6 | process-sampler | observed | 2.472 | 1532.777 | 1427.982 | 69.742 | 2026-08-03T22:34:36.818925+00:00 |
| runtime-compare-nuitka | warm | nuitka-cpython-3.14.6 | process-sampler | observed | 2.265 | 1533.258 | 1427.982 | 69.753 | 2026-08-03T22:37:12.873613+00:00 |
| runtime-compare-nuitka | warm | nuitka-cpython-3.14.6 | process-sampler | observed | 2.466 | 1532.445 | 0.001 | 68.166 | 2026-08-03T22:37:15.207148+00:00 |
| runtime-compare-nuitka | warm | nuitka-cpython-3.14.6 | process-sampler | observed | 2.474 | 1517.066 | 0.003 | 68.166 | 2026-08-03T22:37:17.740173+00:00 |
| runtime-compare-nuitka | warm | nuitka-cpython-3.14.6 | process-sampler | observed | 2.470 | 1554.688 | 0.003 | 68.166 | 2026-08-03T22:41:24.258127+00:00 |
| warm-rlayout | warm | cpython-3.14.6 | cprofile | observed | 4.554 | 1276.117 | 1435.581 | 2.052 | 2026-08-03T21:32:36.962886+00:00 |
| warm-rlayout | warm | cpython-3.14.6 | pyinstrument | observed | 4.346 | 1408.703 | 1435.952 | 1.590 | 2026-08-03T21:32:41.608485+00:00 |
| warm-rlayout | warm | cpython-3.14.6 | scalene | observed | 4.746 | 1640.344 | 1446.867 | 2.726 | 2026-08-03T21:32:32.099300+00:00 |
| warm-rlayout | warm | cpython-3.14.6 | tracemalloc | observed | 44.480 | 1540.742 | 1435.623 | 1.558 | 2026-08-03T21:32:46.027046+00:00 |
| warm-rlayout-py-spy | warm | cpython-3.14.6 | py-spy | partial | 0.621 | 50.160 | 5.350 | 0.000 | 2026-08-03T21:49:23.600696+00:00 |

## Latest like-for-like deltas

| Workload | State | Runtime | Profiler | Status | Wall delta (s) | RSS delta (MiB) | Read delta (MiB) | Write delta (MiB) |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| fixture | warm | cpython-3.14.6 | pyperf | observed | -0.162 | -0.047 | 0.000 | 0.000 |
| runtime-compare-cpython | warm | cpython-3.14.6 | process-sampler | observed | 0.000 | -155.133 | -0.289 | -0.277 |
| runtime-compare-free-threaded | warm | cpython-3.14.6-free-threaded | process-sampler | observed | 0.206 | 115.168 | 0.000 | -0.000 |
| runtime-compare-nuitka | warm | nuitka-cpython-3.14.6 | process-sampler | observed | 0.000 | 22.383 | 0.002 | 0.000 |

## Tool availability

| Tool | Status | Version | Detail |
| --- | --- | --- | --- |
| cprofile | observed | 3.14.6 | — |
| nuitka | not_observed | — | no artifact recorded |
| process-sampler | observed | built-in | — |
| psutil | not_observed | — | no artifact recorded |
| py-spy | partial | py-spy 0.4.2 | profiler did not publish the expected output |
| pyinstrument | observed | pyinstrument 5.1.3, on Python 3.14.6 | — |
| pyperf | observed | 2.10.0 | — |
| scalene | observed | Scalene version 2.3.0 (2026.05.08) | — |
| tracemalloc | observed | 3.14.6 | — |

## Method-level evidence

The database retains normalized top-N method or line summaries. Follow each run's manifest path for the checksummed raw profile when it is available.
