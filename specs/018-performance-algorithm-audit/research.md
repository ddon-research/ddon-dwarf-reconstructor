# Research and initial algorithm dispositions

## Repository evidence

The current warm path performs targeted class discovery and class parsing over pyelftools DIEs;
qualified names walk DIE parents. The cold path performs one streaming compressed-text scan and
writes a source-bound SQLite sidecar. The current workload does not construct a global graph, CFG,
source AST, or graph database.

The cold source-bound process runs observed 242.076–274.424 seconds, with a four-run original-code
median of 265.192 seconds. cProfile found 463,660,524 calls through the line scanner and
Scalene attributed 85.483% of sampled CPU to stream iteration and scanner dispatch. SQLite
execution was a smaller secondary cost. The source produces 1,714,481 class rows and 386,908
method rows. This accounts for the measured target path without inventing a graph workload.

The warm path was measured in five alternating process-sampler pairs. Removing platform-time
DWARF materialization reduced median wall time from 1.976 to 1.766 seconds and preserved all
four output file hashes. Parent-chain memoization was screened separately and was neutral.
All raw artifacts remain external.

## Review of `algorithmandperformanceresearch.md`

The prior document is retained as a hypothesis catalogue. SCC/Tarjan, type deduplication, and
topological ordering are conditional candidates only if a measured global reference graph becomes
necessary. Its Merkle-style pseudocode is not directly adoptable because DWARF edge labels,
attributes, provenance, and cyclic hashing semantics are not defined by that sketch.

Dominator trees, Kernighan–Lin partitioning, interval trees, burst tries, graph mining, and
cache-oblivious/vEB storage are deferred because the current measured paths do not expose their
required query or execution model. The SQLite sidecar already uses indexed equality lookup and
deterministic ordering; query-plan evidence must precede a storage replacement. AST/tree-sitter
resources are out of scope because the input is DWARF rather than a source-language AST.

Format-specific DWARF deduplication work such as `dwz` is useful comparative evidence, not proof
that a generic graph-isomorphism pass fits this producer. Generic Python tips are hypotheses only;
measurements on CPython 3.14.6 and this workload are authoritative.

## Citations

The Python profiler documentation at https://docs.python.org/3/library/profile.html defines
tottime as local time and cumtime as time including callees; it also says profilers are for
execution profiles rather than benchmark timing. pyperf at
https://pyperf.readthedocs.io/en/stable/index.html is reserved for repeated fixture and
microbenchmark comparisons. The SQLite query-planner guide at
https://www.sqlite.org/queryplanner.html supports retaining indexed equality lookup until an
EXPLAIN QUERY PLAN defect is measured.

The archived PythonSpeed performance tips at
https://wiki.python.org/moin/PythonSpeed/PerformanceTips supports measuring before choosing a
micro-optimization. The graph reference describes DFS/BFS and bounded expansion in Memgraph's
deep traversal guidance at https://memgraph.com/docs/advanced-algorithms/deep-path-traversal;
that is not evidence for a global traversal here. dwz at
https://manpages.ubuntu.com/manpages/jammy/man1/dwz.1.html is a format-specific DWARF optimizer.
AST resources, including the AST overview at
https://en.wikipedia.org/wiki/Abstract_syntax_tree, concern source-language trees rather than
the compressed DWARF dump.
