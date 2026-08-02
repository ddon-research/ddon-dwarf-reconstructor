# Implementation Plan: Clean Architecture Audit and Modernization

This plan records the delivered refactor and completed Tier 1/2 convergence. It
intentionally describes current contracts, not a request to preserve removed
runtime shapes; Tier 3 real-asset/compiler validation remains deferred.

## Phase 0: Preserve the evidence contract — completed

1. Add regression fixtures for the confirmed source-identity, timeout, CU-header,
   vtable-expression, cache-provenance, and resource-lifetime defects.
2. Define typed result/status models for source identity, search, parse, cache,
   and diagnostic outcomes before changing callers.
3. Record a replacement output/cache contract and an explicit invalid-artifact
   rebuild command in the feature artifacts.

Validation: Tier 1 focused unit tests, `uv run just test-unit`, and
`uv run just check`.

## Phase 1: Unify source identity and artifact lifecycle — completed

- Replace boundary-only authorization in `infrastructure/artifacts.py` and
  `domain/services/lazy_index_source.py` with one source-identity port and one
  implementation. Keep fast metadata as a probe, never as proof of unchanged
  content.
- Remove unbound-cache sampling and load-time shape conversion from
  `cache_schema.py`, `cache_persistence.py`, and `dwarf_config.py`. A cache is
  usable only when current schema, source, producer, and configuration identity
  match.
- Remove the duplicate header cache. `AtomicHeaderPublisher` is the single
  header publication policy and emits a bundle manifest with rollback.
- Make save failures, lock ownership, stale-lock recovery, and atomic replacement
  visible as structured artifact diagnostics.

Validation: Tier 1 cache/artifact tests; Tier 2 fresh-process and corruption
tests; Tier 3 explicit real sidecar reuse and same-path replacement.

## Phase 2: Make evidence status first-class — completed

- Introduce a result type for targeted search and full scan with candidate,
  status, score, CU/DIE provenance, elapsed time, and diagnostics.
- Fix timeout selection so a partial candidate cannot be cached as complete and
  never combine a fallback DIE with another candidate's CU or score.
- Normalize CU headers in the ELF adapter and remove object/mapping dual access
  from lookup and ordering services.
- Replace broad parser fallbacks with specific adapter exceptions and explicit
  unknown/unavailable evidence. Correct expression parsing, `DW_AT_noreturn`,
  enum values, name decoding, and array/type-chain termination.

Validation: Tier 1 parser/search fixtures and Hypothesis invariants; Tier 2
selected real dump lookups; compiler tier for rendered evidence.

## Phase 3: Restore clean application boundaries — completed

- Replace `DwarfGenerator` multiple inheritance and concrete session
  construction with `GeneratorWorkflow` composition and an injected session
  factory supplied by the composition root.
- Apply PS4 ELF normalization once when the adapter is constructed. Failed
  construction must close every opened resource.
- Validate explicit input paths before entering the use case and write bundles
  through one atomic output adapter.
- Delete duplicate utility modules, duplicate exports, and option dictionaries
  after all in-repository callers and tests move to their owning service.

Validation: Tier 1 composition/CLI tests; Tier 2 package smoke and non-performance
suite; architecture and structure gates.

## Phase 4: Make rendering and ordering truthful — focused work completed

- Represent template parameters, arrays, qualifiers, unresolved offsets, and
  diagnostics structurally instead of inferring them from strings.
- Make dependency cycles a blocking diagnostic with deterministic cycle members;
  do not emit an arbitrary order for an unsatisfied by-value cycle.
- Preserve method qualifiers and declaration state during deduplication and
  render optional DIE offsets as explicit unavailable evidence.
- Publish a complete bundle atomically and compare exact output manifests.

Validation: Tier 1 generation tests; Tier 2 MSVC/C++23 probes; Tier 3 fixture and
real PS4 output manifests in fresh and warm processes.

## Phase 5: Converge and document — complete; Tier 3 deferred

- Remove stale settings, retired test names, and documentation that describes
  duplicate indirection or alternate runtime contracts.
- Review the nested specification pipeline for the same typed exception and
  module-size rules without coupling its dependency boundary to the runtime.
- Run all required gates and record any deferred compiler or real-asset work in
  this feature rather than in generated output.

## Dependency order

Phase 1 and Phase 2 enabled deletion of duplicate caches and application
indirection. Phase 3 depended on the typed result and source-identity ports.
Phase 4 depended on truthful completeness and declarator models. Phase 5 is the
completed nested-tool review, documentation sweep, and Tier 1/2 acceptance run;
Tier 3 real-asset/compiler validation is explicitly deferred.

## Validation tiers

- **Tier 1**: focused tests, `uv run just test-unit`, and `uv run just check`.
- **Tier 2**: `uv run just test`, `uv run just coverage-ci`, `uv run just audit`,
  package smoke, and compiler probes where applicable.
- **Tier 3**: explicit PS4 ELF/dump/index runs with cold/warm state, timings,
  source identity, producer/schema/configuration identity, and exact manifests.
