# Measured evidence: performance and algorithm audit

All raw profiles, sidecars, and proprietary inputs are external artifacts. The source identity for
the named compressed dump is recorded in every manifest. Profiler timings are attribution evidence
and are not compared as uninstrumented performance baselines.

## Environment and source identity

| Field | Observation |
| --- | --- |
| Python | CPython 3.14.6 |
| Platform | Windows 11, AMD64, Ryzen 7800X3D workstation |
| Tools | process-sampler, Scalene 2.3.0, cProfile, pyinstrument 5.1.3, py-spy 0.4.2, pyperf 2.10.0, tracemalloc, psutil 7.2.2 |
| Raw artifact root | D:\ddon-perf-artifacts\algorithm-audit-20260804 |
| Compressed dump | D:\research\DDON-binaries\IDA9.3\PS4_DDON_02020005_2016_12_21\DDOORBIS.elf.llvmdwarfdump.zst |
| Dump source identity | 21def1c1dac96f578826c489c40178865afbfdc5754e534035ef9a1097acd2e8 |
| Git revision | 0c55cb644c03ac91991cf769e5e2d6f07a61b92d |
| Real-asset CI | Not required; explicit environmental evidence |

performance doctor observed cProfile, Scalene, pyinstrument, py-spy, pyperf, tracemalloc, and
the built-in process sampler. Memray is not supported on this Windows setup. py-spy remains
optional and did not replace the named function/line evidence. The deterministic fixture gate
passed with uv run just test-performance-fixtures.

## Process-sampler baselines and confirmations

| Run | Workload | Wall (s) | User CPU (s) | System CPU (s) | Peak RSS (B) | Read (B) | Write (B) | Samples |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| cold-dump-index-baseline | cold original | 268.425 | 253.953 | 12.813 | 806,887,424 | 11,445,429,345 | 9,578,538,914 | 267 |
| cold-dump-index-process-sampler-2 | cold original | 274.424 | 259.641 | 12.984 | 808,370,176 | 11,078,142,212 | 9,236,243,605 | 273 |
| cold-dump-index-process-sampler-3 | cold original | 242.076 | 228.844 | 11.891 | 806,965,248 | 11,077,771,645 | 9,235,883,157 | 241 |
| cold-dump-index-original-confirmation | cold original | 261.960 | 249.047 | 11.609 | 807,321,600 | 11,131,155,445 | 9,285,358,748 | 261 |

The four original-code full-source runs have a 265.192 s median, 242.076–274.424 s range, and
14.051 s sample standard deviation. The first and last rows are the two explicit post-screening
source-bound confirmations used for handoff.

## Function and line traces

| Workload | Profiler | Status | Attribution |
| --- | --- | --- | --- |
| cold index | cProfile | observed | 668.380 s profiled wall; _scan_dump 667.054 s cumulative / 192.790 s self; _scan_line 345.482 s cumulative / 126.610 s self over 463,660,524 calls; SQLite Connection.execute 18.741 s over 2,155,503 calls |
| cold index | Scalene | observed | 59.891% of sampled CPU in compressed stream iteration; 25.592% in _scan_line; SQL execute lines 4.405% and 2.464%; peak RSS 1,440,407,552 B |
| cold index | pyinstrument | partial | Attempted complete run was aborted before a profile artifact was published; no timing or adoption claim is based on it |
| warm rLayout | cProfile | observed | Current candidate trace shows _get_qualified_name 32 calls / 2.954 s cumulative, class parsing/hierarchy about 3.136 s cumulative, and no DWARF version scan in platform detection |
| warm rLayout | Scalene | observed | Current candidate manifest published; used as cross-check rather than baseline timing |
| warm rLayout | pyinstrument | observed | Current candidate manifest published; used as sampled-stack cross-check |

cProfile follows the Python profiler contract: tottime is used for local hot loops and cumtime
for higher-level algorithm selection. The cProfile and Scalene runs are slower than the process
sampler by design and are not mixed into the baseline medians. The dominant uninstrumented cold
path is therefore classified as Python line dispatch plus compressed-stream/native I/O, with
SQLite execution measured as a smaller secondary cost.

## Warm alternating benchmark

Five alternating process-sampler pairs used the same warm ELF, indexed DWARF sidecar, CPython
3.14.6, machine, output mode, and source identity. Each baseline output was produced while the
platform detector still materialized DWARF version information; each candidate output used the
retained machine/endianness/ABI-only classification.

| Metric | Baseline median (range) | Candidate median (range) | Median delta | Paired bootstrap 95% interval |
| --- | ---: | ---: | ---: | ---: |
| Wall time | 1.976 s (1.975–1.979) | 1.766 s (1.762–1.770) | -0.210 s (-10.7%) | -0.217 to -0.205 s |
| User CPU | 1.438 s (1.359–1.500) | 1.344 s (1.297–1.344) | -0.094 s (-6.5%) | -0.203 to -0.016 s |
| System CPU | 0.422 s (0.359–0.500) | 0.281 s (0.281–0.313) | -0.141 s (-33.3%) | -0.188 to -0.063 s |
| Peak RSS | 1,485 MiB (1,413–1,674) | 1,295 MiB (1,254–1,329) | -133 MiB (-8.6%) | -393 to -87 MiB |
| Read bytes | 1,505,436,922 | 757,574,701 | -747,862,221 (-49.7%) | same value in all resamples |
| Write bytes | 1,596,719 | 1,598,960 | +2,241 (+0.1%) | +2,235 to +2,244 |

The bootstrap used 20,000 resamples of the five paired differences and a fixed seed. The
performance result is retained because every pair improved wall time and the output contract
was exact. Each of the five baseline/candidate output pairs contains four files with identical
SHA-256 values: manifest.json, nodes.jsonl, reconstructed.hpp, and relationships.jsonl.

## Candidate decision record

| Candidate | Lane | Evidence | Decision |
| --- | --- | --- | --- |
| Avoid redundant DWARF materialization in platform classification | Python/resource lifecycle | Focused no-materialization test; five alternating warm pairs above; exact output equality | Adopt |
| Memoized parent chains / qualified names | Python/data access | Five-run parent-cache screening: 1.982 s baseline median versus 1.980 s candidate median | Reject as neutral |
| Batched SQLite writes / bounded flush | Cold data path | Two candidate runs: 273.571 s median versus 265.192 s original median; sidecars byte-identical | Reject |
| Parser dispatch collapse | Cold parser | 251.149 s and 241.011 s candidate runs; nearest original comparison differed by about 0.4% and cache/I/O state was not controlled | Reject |
| Literal header-prefix guard | Cold parser | 240.031 s single run with lower cache/I/O state; no repeatable paired evidence | Reject |
| Disable journaling for temporary build | SQLite configuration | 260.963 s two-run median versus 261.960 s original confirmation; no meaningful I/O gain | Reject |
| Text-to-bytes compressed parser | Cold parser | 763.659 s full source-bound run, 184.5% slower than initial baseline; sidecar rows and SHA-256 unchanged | Reject |
| min(set) deterministic queues | Python/data structure | No measured high-impact call path in current traces | Defer |
| Global graph/SCC/Merkle deduplication, CFG algorithms, interval trees, tries, vEB storage, AST/tree-sitter | Algorithmic/data structure | Current workloads expose no global graph, CFG, PC-range, prefix-string, or source-AST query | Defer |
| SQLite schema/index redesign | Algorithmic/data structure | Existing equality indexes fit lookup contract; no EXPLAIN QUERY PLAN defect or lookup bottleneck measured | Defer |

All tested cold candidate sidecars are 206,422,016 B with SHA-256
6b6139e8484f6ac8a73b08a29137e3d120c683733987b04663aa5dea9b12eab9, 1,714,481 class rows,
386,908 method rows, and the same metadata/source identity. The cold production parser was
therefore left unchanged.

## Artifact references

The raw process manifests, pstats, Scalene JSON, pyinstrument JSON, samples, and exact output
comparisons are under D:\ddon-perf-artifacts\algorithm-audit-20260804. The explicit cold trace
recipe is performance-profile-index-traces; the profilers have separate sidecars so profiler
overhead and cache state are not conflated. The prior analysis file remains untracked and
unchanged.

## Repository gates

| Gate | Result |
| --- | --- |
| uv run just test-unit | pass |
| uv run just check | pass |
| uv run just test | 463 passed, 5 deselected |
| uv run just coverage-ci | pass; 81.65% total coverage, 85.1% lines / 69.2% branches |
| uv run just audit | pass; zero Prospector messages |
