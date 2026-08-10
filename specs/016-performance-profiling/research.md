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
The Linux container probe retained valid Scalene JSON but only launcher/import attribution for the
real analytical-store workload. The same probe retained reconstructor frames from py-spy when its
rate was bounded to 5 Hz; the canonical adapter therefore uses nonblocking 5 Hz sampling on
CPython 3.14 and records sampling errors as evidence.

## Scalene scope revalidation

The upstream [Scalene argument defaults](https://github.com/plasma-umass/scalene/blob/master/scalene/scalene_arguments.py)
set `profile_all` to `false`, leave `profile_only`, `profile_exclude`, and `program_path` empty,
sample CPU at `0.01` seconds, and enable memory profiling. The upstream
[tracing implementation](https://github.com/plasma-umass/scalene/blob/master/scalene/scalene_tracing.py)
applies explicit exclusions and `profile-only` filename filters before choosing either the
`profile_all` location rule or the `program_path` tree. With `profile_all` disabled, it also
excludes the standard library and installed packages.

The repository's `scalene_target.py` wrapper is required to preserve a canonical `python -m`
workload. The prior default command made the wrapper directory the implicit program scope, so a
Linux real-asset run recorded the wrapper's `runpy.run_module` line and only four non-wrapper import
lines. A bounded source-bound matrix on the same complete Doris query produced the following:

| Configuration | Result | Artifact observation |
| --- | --- | --- |
| default wrapper command | partial attribution | five non-zero rows; wrapper present as the dominant row |
| `--profile-all --profile-only /workspace/src/ddon_dwarf_reconstructor --profile-exclude scalene_target.py` | observed | 70 package rows, no wrapper rows, `manifest.py` validation lines present |
| the same flags plus `--cpu-only` | observed | 38 package rows, no wrapper rows, same leading `manifest.py` lines, 10.9 MB JSON |
| `--program-path /workspace/src/ddon_dwarf_reconstructor --profile-exclude scalene_target.py` | observed | 73 package rows, no wrapper rows, default library exclusion retained |

The normal adapter now uses the final configuration. `--profile-all` remains an explicit diagnostic
fallback, not the default, because the package-root scope recovered the missing application lines
without broadening tracing to system libraries. `--cpu-only` is recommended only when memory
evidence is not required. These runs establish Linux line attribution; they do not prove that a
Windows CPython runtime has the same behavior, so the Windows comparison remains a follow-up.

## Library scope and leak-detector revalidation

The optional library view is deliberately separate from the normal package-scoped run. In the
current upstream tracing order, `--profile-system-libraries` alone does not bypass the earlier
system-path exclusion; the effective broad configuration is `--profile-all
--profile-system-libraries` with the wrapper excluded and no `--profile-only` filter. The
repository exposes this as `--profiler scalene-libraries`; it is not included in the `all` selector.

Every repository Scalene command now passes `--memory-leak-detector` explicitly. The current
Scalene source defaults the experimental detector to enabled, so this makes the intended mode
stable across the recorded command even though it is not a new behavior for the pinned Linux image.
The runner now publishes the detector's count as `scalene_leak_records` when the JSON contains a
valid `files` payload.

The same source-bound Doris query was run with the following additional configurations:

| Configuration | Result | Artifact observation |
| --- | --- | --- |
| scoped package profile plus explicit leak detector | observed | 73 non-zero rows, 18,513,844 B JSON, `scalene_leak_records=0`, empty `leaks` maps in every file, maximum footprint 62.48 MB at `benchmark.py:440` |
| `--program-path` plus `--profile-system-libraries` | observed but ineffective for library scope | 70 non-zero rows and no external library files; this confirms that the flag alone does not overcome the upstream exclusion order |
| `--profile-all --profile-system-libraries --profile-exclude scalene_target.py` | observed | 78 non-zero rows across 11 files and 30,794,564 B JSON; `scalene_leak_records=0`; `threading.py:1024` was the largest external CPU row at 6.06%, `pathlib` reached 1.10%, and `pyarrow/dataset.py` was present but small; all `leaks` maps were empty |
| canonical `profile-dwarf-store --profiler scalene-libraries` | observed | 134.331 s wall, 0.56 s process CPU, 462,946,304 B peak RSS, 1,336 samples, 20 normalized summaries, and `scalene_leak_records=0`; the broad alias completed with no diagnostics |

The broad profile is useful for library-alternative research but does not currently displace the
application profile: the leading application rows remained `manifest.py` validation lines, while
the external Python rows were mostly standard-library synchronization/path machinery. The leak
detector reported no likely leak records for this one-iteration workload. Its observed growth-rate
and maximum-footprint fields are allocation-growth signals, not proof of a leak; a repeated
long-lived workload is required before promoting a leak action item.

## cProfile and py-spy roles after Scalene recovery

Scalene now supplies actionable application line, native-time, and memory attribution on Linux,
but cProfile remains useful as a deterministic call-count cross-check. On the same bounded query,
cProfile recorded 104,672 `posix.lstat` calls with 71.099 seconds self time, reached through
repeated `Path.resolve()` calls. Scalene located the surrounding manifest-validation lines and
native time but did not expose the same exact builtin call-count surface. Keep cProfile optional
and in the explicit `--profiler all` cross-check set; do not treat it as the primary profiler or
run it for every resource baseline.

py-spy remains complementary: `record` supplies low-overhead external sampled frames, while
`py-spy dump --pid` can capture a point-in-time stack from a running process without restarting or
modifying it. The repository keeps the bounded nonblocking 5 Hz `record` adapter and documents
`dump` as an operator snapshot. Sampling errors and ptrace limitations remain explicit evidence.

pyperf supplies calibrated repeated command runs, metadata, JSON output, and statistical checks;
the application uses psutil for resource counters because pyperf's Windows RSS tracker is not a
required source of evidence. pyperformance is a broad benchmark suite for Python implementations,
not a workload harness. Locust targets service load and is outside this CLI batch application's
boundary. Memray is not selected because the supported project environment is Windows.

## Revalidation record

The prior Windows revalidation record captured CPython 3.14.6 and these installed tools:

| Tool | Observed version |
| --- | --- |
| Scalene | 2.3.0 |
| pyinstrument | 5.1.3 |
| py-spy | 0.4.2 |
| pyperf | 2.10.0 |
| psutil | 7.2.2 |

The external educational references supplied for this feature remain useful orientation but are
not acceptance evidence. Runtime compatibility is checked by `performance doctor` and the locked
uv environment. The later Nuitka/free-threaded runtime evaluation is recorded separately in
[feature 017](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/017-nuitka-runtime-comparison).

## References

- [Python profiling](https://docs.python.org/3/library/profile.html)
- [Python tracemalloc](https://docs.python.org/3/library/tracemalloc.html)
- [Scalene](https://github.com/plasma-umass/scalene)
- [pyinstrument](https://pyinstrument.readthedocs.io/en/latest/guide.html)
- [py-spy](https://github.com/benfred/py-spy)
- [pyperf](https://pyperf.readthedocs.io/en/stable/index.html)
- [pyperformance](https://github.com/python/pyperformance)
- [Locust](https://locust.io/)
