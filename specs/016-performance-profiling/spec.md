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

## Non-goals

- Memray on Windows, ETW/PerfView, remote dashboards, Locust load testing, or hosted real-asset CI.
- Always-on parser/generator instrumentation or changes to generated headers.
- Treating a real-asset or profiler skip as a replacement for deterministic evidence.
- Auto-learning performance thresholds from environmental history.
