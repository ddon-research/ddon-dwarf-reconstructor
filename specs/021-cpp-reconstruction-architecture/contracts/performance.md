# Performance acceptance

For benchmark operators, this reference defines matched source/state/runtime measurements.
Use the existing PerformanceWorkload, PerformanceRunner, and HistoryStore contracts; raw
samples and the history database remain external. Do not write the tracked history by default.

## Matrix

Run MtObject, rLayout, and all 289 roots with headers, assembly/context, canonical sources and
eligible objects, and context-disabled assembly. Retain the established exhaustive rAIFSM
control. Keep knowledge/nested fixture acceptance separately identifiable.

Use three application-cache-cold samples and five fresh-process warm samples per pair. Cold
means an isolated empty derived-artifact cache with a prevalidated source-identity catalog;
source hashing is preflight, not charged repeatedly. Record OS and Doris state as uncontrolled
unless separately controlled. Prime each warm cache before measured samples. Never purge a
durable cache or reload Doris for routine measurements.

## Decision

Candidate p50 and sampled p95 must each be at most 1.10 times baseline for every workload/state.
Use nearest-rank sampled p95 and report sample count; small-sample tails are exploratory.
If a threshold crossing is noisy, retain it and repeat 20 matched samples on each side.
Never combine workloads to hide a regression. Output parity is a prerequisite to comparison.

Record source/store/list/tool hashes, effective options, working-state identity, runtime/GIL,
machine, process boundary, wall/CPU, process-tree RSS/VMS/I/O, sampling, timeout, and cache state.
Use identical sampling and configuration on both sides. Treat traced timings as attribution
unless their overhead is measured and acceptable. More RAM is allowed; paging, instability,
or unbounded growth invalidates acceptance.
