# Plan: Evidence-first performance and algorithm audit

## 1. Establish evidence

Run `performance doctor`, the deterministic fixture gate, and process-sampler-only baselines. Use
the existing warm artifacts where their source/configuration identity matches. Run the explicit
`performance-profile-index-traces` recipe against the named external compressed dump, with one
sidecar per profiler. Record tool status, runtime, source identity, cache state, wall/CPU/RSS/VMS,
I/O, sample counts, and profiler-overhead boundaries.

Use cProfile cumulative time for high-level algorithm selection and total time for local hot loops;
use Scalene for Python/native line and memory attribution; use pyinstrument for sampled stacks; and
use tracemalloc only for allocation sites. Use pyperf only for repeated fixture or microbenchmark
comparisons.

## 2. Build the candidate matrix

For every dominant path, record workload, source path, observed evidence, current algorithm,
complexity, memory behavior, correctness risks, candidate change, expected invariant, benchmark
metric, and decision. Maintain separate Python-level and algorithmic/data-structure lanes.

Initial warm candidates are qualified-name/parent-chain reuse, duplicate DWARF initialization, and
only then lower-cost queue/cache operations. Initial cold candidates are batched SQLite writes,
bounded record flushing, parser dispatch, and schema/query-plan changes only when measured.

SCC/Tarjan, type deduplication, topological sorting, dominator trees, graph partitioning, interval
structures, tries, graph mining, vEB storage, and AST parsers are reject/defer candidates unless the
traces prove the required graph, CFG, range, string, or AST workload exists.

## 3. Implement incrementally

Implement one highest-impact candidate per slice. Keep existing CLI semantics and typed source-bound
cache/index contracts. If an on-disk artifact changes, increment its producer/configuration/schema
identity and publish it atomically; never silently reuse an incompatible artifact.

After each slice, run focused tests, `test-unit`, `check`, and `test` before advancing. Keep failed,
neutral, blocked, and inconclusive candidates documented rather than folding them into production.

## 4. Validate and publish evidence

Use at least five alternating warm baseline/candidate runs and two full cold source-bound
confirmation runs after fixture screening. Report medians, dispersion, bootstrap confidence
intervals, peak RSS, CPU, I/O, cache state, source identity, and output-manifest equality. Update
the profiling how-to, performance reference, goal-oriented workflow, benchmark knowledge base,
and this feature's measured evidence.
