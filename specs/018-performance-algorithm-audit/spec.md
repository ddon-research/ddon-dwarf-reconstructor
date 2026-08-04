# Feature 018: Evidence-first performance and algorithm audit

**Status:** Complete; implementation, source-bound evidence, regression checks, and repository
quality/correctness gates pass.

## Goal

Determine whether the current algorithms and Python implementations are appropriate for the warm
`rLayout` knowledge-export workload and the cold compressed-DWARF index-build workload. Implement
only evidence-backed improvements, one slice at a time, while preserving deterministic outputs,
source identity, cache/index contracts, and provenance.

## Requirements

- **APA-001:** The audit MUST cover both warm indexed `rLayout` export and cold construction from
  the named PS4 compressed DWARF dump.
- **APA-002:** Each workload MUST have process-sampler evidence and, where available, separate
  cProfile, Scalene, and pyinstrument evidence. Allocation evidence MUST be labeled separately
  from timing evidence.
- **APA-003:** The audit MUST classify Python-level tuning separately from algorithmic/data-
  structure changes and must record adopt, reject, defer, blocked, and inconclusive decisions.
- **APA-004:** An optimization MUST be retained only after deterministic regression checks and
  repeated source-bound benchmark evidence show a statistically credible improvement in its target
  metric.
- **APA-005:** Generated outputs, qualified names, inheritance, field offsets, sizes, source
  locations, DIE/CU provenance, ordering, cache identity, and atomic publication behavior MUST be
  unchanged unless an explicitly versioned contract says otherwise.
- **APA-006:** Generic graph, AST, CFG, and alternative storage algorithms MUST NOT be introduced
  without evidence that the corresponding workload and query semantics exist in this system.

## Boundary

Raw profiles, proprietary inputs, generated headers, indexes, and performance databases remain
outside Git. Real-asset performance is explicit environmental evidence, not a CI requirement.
The audit does not start live graph infrastructure, source-language AST parsing, or runtime/compiler
changes. The untracked `algorithmandperformanceresearch.md` file is reviewed but not modified.

## Acceptance

The feature is complete when the warm and cold dominant cost paths are accounted for or explicitly
classified, the prior algorithm research has an evidence-backed disposition, every retained change
has focused regression tests plus repeated warm/cold measurements, and the required root quality
and correctness gates pass.
