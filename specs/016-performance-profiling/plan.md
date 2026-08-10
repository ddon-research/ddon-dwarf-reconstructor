# Implementation Plan: Source-bound profiling and benchmark history

## Architecture

The canonical Typer root owns a `performance` command group. CLI handlers build immutable
`PerformanceWorkload` contracts and delegate to infrastructure adapters. The process runner owns
subprocess lifecycle, bounded stdout/stderr capture, psutil process-tree sampling, timeout
termination, source identity lookup, and atomic manifest publication. Profiler adapters wrap the
same workload in separate child invocations and normalize method/line summaries.

The production generation path is not instrumented. Profiling overhead exists only in an explicit
child command. Source identity uses `SourceIdentityCatalog`; raw outputs use the ignored OS-local
performance artifact directory.

## Layered tools

| Question | Primary evidence | Supporting evidence |
| --- | --- | --- |
| Process CPU/RAM/I/O | psutil sampler | Scalene process/line attribution |
| Python allocation | tracemalloc wrapper | Scalene allocation data |
| Deterministic methods/calls | cProfile/pstats | normalized top-N rows |
| Wall-clock call stacks | pyinstrument | py-spy external/native sampling |
| Repeated fixture statistics | pyperf | psutil summary and history ledger |

Scalene is the default deep profiler. py-spy is allowed to remain partial on Windows when process
sampling permissions prevent attachment. pyperformance and Locust are not application harnesses:
the former is a broad Python implementation suite and the latter is for service load testing.

The normal Scalene adapter explicitly enables the experimental memory leak detector. An optional
`scalene-libraries` profiler mode broadens tracing with `--profile-all --profile-system-libraries`
for dependency and standard-library comparison; it is excluded from the `all` selector because
the broad report is diagnostic and can dilute application attribution. cProfile remains an
optional deterministic call-count cross-check because it exposes builtin/native call surfaces
that sampled Scalene output does not reproduce exactly. py-spy `dump` is retained as an operator
snapshot path, separate from the bounded `record` adapter.

The Linux compatibility boundary is a separate pinned Compose image with read-only source/input
mounts and external output, log, cache, profile, and history mounts. Its py-spy adapter uses
nonblocking 5 Hz sampling on CPython 3.14; wrapper-only Scalene output remains non-actionable until
the retained JSON contains reconstructor source-line frames. For module workloads, the Scalene
adapter sets the package-root `--program-path` and excludes `scalene_target.py`; this preserves
Scalene's standard-library exclusion while allowing the complete application tree to be sampled.
`--profile-all` plus a package `--profile-only` filter remains an explicit diagnostic fallback.

## Iteration order

1. Contract and taxonomy tests.
2. Deterministic fixture runner and explicit budget.
3. Warm indexed `rLayout` run using the current CLI.
4. Scalene, cProfile, pyinstrument, py-spy, and tracemalloc cross-checks.
5. Cold compressed-dump index construction in a separate report.
6. SQLite history initialization and static export.
7. Full root and nested validation loops.

## Evidence policy

The tracked ledger stores summaries and checksummed references only. The manifest records raw paths,
sizes, checksums, tool versions, and status. Raw profiles and sample streams are external and may
be removed only through a narrowly targeted operator action; the database remains a historical
record of their availability at collection time.
