# Research: Python profiling tool selection

## Decision sources

The Python standard library documents deterministic `cProfile`/`pstats` output and warns that raw
profile files are not a portable interchange format. `tracemalloc` supplies Python allocation
tracebacks and current/peak snapshots but does not represent all native process memory.

The official pyinstrument documentation describes statistical wall-clock profiling with full call
stacks and JSON/Speedscope output. py-spy provides low-overhead external sampling and native-frame
options. Scalene adds CPU, system time, allocation, line/function, and memory attribution and is
the primary deep profiler for this Windows/CPython 3.14 checkout. The checked 2.3.0 `run` command
writes JSON without opening the browser; its optional `view --html` step is a separate offline
rendering action. The adapter does not enable web output or any network/AI suggestion feature.

pyperf supplies calibrated repeated command runs, metadata, JSON output, and statistical checks;
the application uses psutil for resource counters because pyperf's Windows RSS tracker is not a
required source of evidence. pyperformance is a broad benchmark suite for Python implementations,
not a workload harness. Locust targets service load and is outside this CLI batch application's
boundary. Memray is not selected because the supported project environment is Windows.

## Revalidation record

The current environment reports CPython 3.14.6 on Windows and these installed tools:

| Tool | Observed version |
| --- | --- |
| Scalene | 2.3.0 |
| pyinstrument | 5.1.3 |
| py-spy | 0.4.2 |
| pyperf | 2.10.0 |
| psutil | 7.2.2 |

The external educational references supplied for this feature remain useful orientation but are
not acceptance evidence. Runtime compatibility is checked by `performance doctor` and the locked
uv environment.

## References

- [Python profiling](https://docs.python.org/3/library/profile.html)
- [Python tracemalloc](https://docs.python.org/3/library/tracemalloc.html)
- [Scalene](https://github.com/plasma-umass/scalene)
- [pyinstrument](https://pyinstrument.readthedocs.io/en/latest/guide.html)
- [py-spy](https://github.com/benfred/py-spy)
- [pyperf](https://pyperf.readthedocs.io/en/stable/index.html)
- [pyperformance](https://github.com/python/pyperformance)
- [Locust](https://locust.io/)
