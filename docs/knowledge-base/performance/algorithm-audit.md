# Evidence-first performance and algorithm audit

This research note records the Feature 018 audit of the warm indexed `rLayout` knowledge export
and the cold source-bound compressed-DWARF index build. Raw profiles, sidecars, and proprietary
inputs remain in `D:\ddon-perf-artifacts\algorithm-audit-20260804`; the repository stores the
decision record and reproducible commands.

## Result

The retained change removes redundant DWARF materialization from platform classification. The
platform decision uses ELF machine, endianness, and ABI fields; `ElfDwarfSession` still performs
the required DWARF validation and initialization after classification. Five alternating
process-sampler pairs reduced warm median wall time from 1.976 s to 1.766 s (-10.7%), median
user CPU from 1.438 s to 1.344 s, and median peak RSS from 1,485 MiB to 1,295 MiB. All five
baseline/candidate output directories contain the same four files with identical SHA-256
manifests.

The cold implementation remains a one-pass text stream scan with SQLite lookup indexes. The
full-dump traces account for the dominant cost in that scan, but the tested cold changes did not
produce a credible improvement. The sidecar contract, row counts, source identity, and atomic
publication remain unchanged.

## Measured cold evidence

The named dump has source identity
`21def1c1dac96f578826c489c40178865afbfdc5754e534035ef9a1097acd2e8`. The fresh process-sampler
baseline took 268.425 s wall time, 253.953 s user CPU, 806,887,424 B peak RSS, 11,445,429,345 B
read, and 9,578,538,914 B written. A second original-code confirmation took 261.960 s. cProfile
was intentionally interpreted with local `tottime` and algorithm-level `cumtime`: `_scan_dump`
accounted for 667.054 s cumulative and 192.790 s self time in the profiled run; `_scan_line`
accounted for 345.482 s cumulative and 126.610 s self time across 463,660,524 calls.
Scalene attributed 59.891% of sampled CPU to compressed stream iteration and 25.592% to the
call into `_scan_line`; SQLite execute lines were 4.405% and 2.464%. The cold pyinstrument run
was aborted before publishing a trace and is recorded as incomplete evidence, not success.

## Candidate decisions

| Lane | Candidate | Decision | Evidence |
| --- | --- | --- | --- |
| Python/resource lifecycle | Avoid DWARF version lookup during ELF platform classification | Adopt | Focused test proves no `has_dwarf_info()` or `get_dwarf_info()` call; five alternating pairs show the warm improvement above. |
| Python/data access | Memoize parent chains or qualified names | Reject for now | Five-run parent-cache screening moved the median only from 1.982 s to 1.980 s; no credible improvement. |
| Cold data path | Batch method/class SQLite writes | Reject | Two candidate runs had 273.571 s median versus 265.192 s across original confirmations; sidecars were byte-identical. |
| Cold parser | Collapse dispatch and add a literal header-prefix guard | Reject | Single-run improvements were confounded by cache/I/O state; the nearest dispatch comparison differed by about 0.4% and did not establish a repeatable gain. |
| SQLite configuration | Disable journaling for the temporary build | Reject | Two runs were 260.963 s median versus a 261.960 s original confirmation; the sub-second difference did not justify weakening durability assumptions. |
| Cold parser | Switch compressed input and regexes from text to bytes | Reject | Complete source-bound run took 763.659 s, 184.5% slower than the initial baseline, despite identical 1,714,481 class and 386,908 method rows. |
| Algorithmic redesign | Global graph/SCC/Merkle deduplication, CFG algorithms, interval trees, tries, vEB storage, AST/tree-sitter | Defer | The measured workload is a DWARF DIE/text scan and indexed lookup; no corresponding graph, CFG, PC-range, string-prefix, or source-AST query has been established. |

## Source check

The prior analysis is preserved unchanged and is useful as a hypothesis catalogue, especially its
graph-isomorphism proposal at
[the prior analysis](/D:/ddon-dwarf-reconstructor/algorithmandperformanceresearch.md:75).
Its Merkle pseudocode does not define DWARF edge labels, attributes, provenance, incomplete-type
identity, or cyclic hashing, so it is not an implementation specification.

The interpretation follows the [Python profiler documentation](https://docs.python.org/3/library/profile.html):
`tottime` identifies local hot loops and `cumtime` helps assess higher-level algorithm choices.
Repeated fixture measurements use [pyperf](https://pyperf.readthedocs.io/en/stable/index.html);
profiler wall times are attribution evidence, not benchmark baselines. The existing SQLite design
is retained pending query-plan evidence because SQLite documents indexed binary-search lookup,
multi-column indexes, and covering indexes in its
[query-planner guide](https://www.sqlite.org/queryplanner.html).

The supplied Python performance articles remain hypothesis sources; the
[PythonSpeed performance tips](https://wiki.python.org/moin/PythonSpeed/PerformanceTips) likewise
warns that implementation choices should be measured. The graph resources describe real DFS/BFS
and path-expansion workloads, but [deep path traversal guidance](https://memgraph.com/docs/advanced-algorithms/deep-path-traversal)
does not establish that this repository needs an unconstrained global traversal. Finally,
[dwz](https://manpages.ubuntu.com/manpages/jammy/man1/dwz.1.html) is a DWARF-specific
optimization/deduplication tool and [AST references](https://en.wikipedia.org/wiki/Abstract_syntax_tree)
describe source-language trees, not the current dump scanner's input contract.

See the [feature evidence](https://github.com/ddon-research/ddon-dwarf-reconstructor/tree/main/specs/018-performance-algorithm-audit),
[profiling how-to](../../how-to/profile-performance.md), and
[performance reference](../../reference/performance.md) for commands and manifest paths.
