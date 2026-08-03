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
