# Feature Specification: Source-bound profiling and benchmark history

**Feature branch:** `016-performance-profiling`  
**Status:** Implemented; deterministic fixture and explicit real-asset evidence are recorded  
**Owner:** DDON DWARF Reconstructor maintainers

## Problem

The application has an opt-in real `rLayout` time budget but no reusable resource sampler,
method-level profiler contract, historical ledger, or static report. Existing runtime logging is
not a substitute for process RSS, process I/O, or independent profiler evidence, and raw profiler
formats are not stable enough to place in the repository.

## Outcome

The root project shall provide a typed, source-bound performance workflow that:

1. measures wall time, CPU time, RSS/VMS, process I/O counters, and bounded sampling evidence in
   an isolated child process;
2. runs Scalene first with cProfile, pyinstrument, py-spy, tracemalloc, and pyperf as explicit
   supporting or cross-check tools;
3. records unavailable, partial, blocked, and not-observed evidence without converting it to zero;
4. stores summaries, method aggregates, artifact references, source identity, configuration, and
   machine/interpreter metadata in a versioned SQLite ledger;
5. exports deterministic JSON, CSV, and static Markdown suitable for Zensical;
6. keeps raw profiles, samples, stdout, stderr, and real inputs outside Git; and
7. keeps normal generation free from profiling overhead and preserves deterministic output,
   cache reuse, ordering, offsets, and provenance.

## Acceptance scenarios

### Scenario 1: deterministic fixture

Given a local checkout and the locked uv environment, when `uv run just test-performance-fixtures`
runs, the fixture executes in a child process and reports a bounded wall time, peak RSS, sample
count, and atomic manifest without requiring proprietary inputs.

### Scenario 2: tool discovery

When `uv run ddon-dwarf-reconstructor performance doctor` runs, it reports the Python version,
platform, raw artifact directory, history database, and each supported tool as observed or
unavailable with a bounded diagnostic.

### Scenario 3: warm real asset

Given explicit ELF and source-bound index paths, `performance profile` invokes the current
`export-knowledge` command tree for `rLayout`, records warm state and source identity, and stores
Scalene/cProfile/call-stack results when their tools are available. A tool failure remains a
partial or unavailable row.

### Scenario 4: historical comparison

When two compatible runs are stored, `performance history compare` compares only matching
workload, cold/warm state, source identity, interpreter, platform, machine profile,
configuration fingerprint, and profiler mode. It emits deltas without auto-learning thresholds.

### Scenario 5: static publication

When `performance history export` runs, JSON, CSV, and Markdown outputs are deterministic across
repeated exports and label missing evidence explicitly.

### Scenario 6: Linux container boundary

Given the pinned Compose image and explicit read-only input mounts, when the Linux smoke workflow
runs, it reports CPython 3.14.7 and uv 0.12.3, the locked profiler availability, and durable host-mounted logs,
outputs, raw profiles, caches, and external history. The default service has no profiling
capability; the py-spy profile adds `SYS_PTRACE` only for the requested child-process trace.

Scalene line attribution is accepted as actionable only when retained Linux JSON contains
reconstructor source-line frames. A missing artifact, permission failure, or wrapper-only result is
recorded with its evidence status and does not replace another profiler or the process baseline.
For canonical module workloads, the adapter scopes Scalene to the package root with
`--program-path` and excludes `scalene_target.py`; `--profile-all` is reserved for an explicit
diagnostic matrix run with a package `--profile-only` filter. The CPU-only mode is valid for CPU
line evidence but does not satisfy a memory-attribution requirement.
Every Scalene invocation explicitly passes `--memory-leak-detector`. An optional
`--profiler scalene-libraries` mode uses `--profile-all --profile-system-libraries` with no
package-only filter so dependency and standard-library frames can be compared; it is not included
in `--profiler all`. Empty `leaks` maps are recorded as no likely leak identified for that run,
with `scalene_leak_records=0`, not as proof of leak absence. cProfile remains a deterministic
call-count cross-check, and
`py-spy dump --pid` remains an external point-in-time snapshot path while `py-spy record` supplies
bounded sampled frames.
The py-spy adapter uses bounded nonblocking 5 Hz sampling so external sampling remains usable on
CPython 3.14 under Docker/WSL2; sampling errors, profiler-only timeouts, or a missing speedscope
file remain partial evidence.

## Non-goals

- Memray on Windows, ETW/PerfView, remote dashboards, Locust load testing, or hosted real-asset CI.
- Always-on parser/generator instrumentation or changes to generated headers.
- Treating a real-asset or profiler skip as a replacement for deterministic evidence.
- Auto-learning performance thresholds from environmental history.
- Bundling Doris, proprietary ELF/DWARF inputs, SDKs, credentials, or generated artifacts into the
  profiling image.
