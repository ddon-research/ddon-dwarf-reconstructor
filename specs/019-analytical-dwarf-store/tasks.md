# Tasks

- [x] Establish goal contracts and authority matrix.
- [x] Add typed analytical records and query/materialization ports.
- [x] Implement one-pass typed Parquet/raw-section publication with opt-in JSONL audit output.
- [x] Add opt-in CU-boundary checkpoint snapshots with explicit incomplete-query semantics.
- [x] Emit typed range, location, line, macro, frame, abbreviation, and name families during the same CU pass.
- [x] Implement manifest validation and source binding.
- [x] Add direct Parquet writers/readers.
- [x] Align JSONL-to-Parquet backfill with the bounded direct writer and manifest layout policy.
- [x] Review the local PyArrow 25 reference and record schema, Dataset, row-group, and memory
  boundaries.
- [x] Add Doris Compose and native loading/evidence plans.
- [x] Add benchmark protocol and report schema.
- [x] Add the optional ADBC Flight SQL client, qmark benchmark matrix, Compose overlay, and
  endpoint/startup-log preflight without changing the default MySQL/Stream Load path.
- [x] Add the typed Doris serving-variant, query-observation, and optimization-report contracts,
  including redacted opt-in tracing through the real generation query executor.
- [x] Add `benchmark-doris-optimization`, isolated source-bound lookup candidates, cold/warm
  repetition controls, selective statistics, and explicit rejected/not-applicable matrix entries.
- [x] Extend the registry/manifest evidence additively with serving-variant identity and preserve
  the canonical fourteen-family row contract.
- [x] Migrate generation and knowledge export to the store.
- [x] Retire normal legacy lookup paths after parity boundary; retain legacy adapters only for explicit validation.
- [ ] Run focused, repository, real-asset, and environmental validation.
- [x] Run the complete-store canonical/lookup/statistics optimization evaluation and record the
  observed N+1 hydration hotspot, exact `rAIFSM` parity, and rejected source/name candidate.
- [x] Implement bounded source/unit-aware hydration for metadata, attributes, references, and
  child-tag counts, then run exact traced/untraced exhaustive `rAIFSM` confirmation. The serving
  algorithm is retained; remaining physical variants stay `not_observed` until separately measured.

## Status notes

Current boundary (2026-08-08): the promoted durable v1.1 store is
`output/analytical-dwarf/main/store-4236f598acc8f158`; native Doris is the active backend, while
versioned Temp stores, versioned Doris databases, and Iceberg measurements below are historical
evidence only. The full season-two run is still in progress, and standalone bundle, approved MSVC,
IDA, and Sonar acceptance remain separate gates.

The implementation and deterministic/direct-storage fixture slice is complete. The v27 real-ELF
run now supplies the complete source-bound Parquet manifest, independent payload validation,
exact native Doris load/count parity, finished statistics, tablet inspection, and ordered native
query parity. The classifier-backed knowledge export is also complete and internally
matches the generated header after the documented include-guard normalization. LLVM UCRT64
verification remains non-clean and is retained as additive diagnostics; it does not authorize
discarding rows. An explicit single-symbol live pyelftools baseline is now observed with a
source-bound 180-second bound; a second fresh store-backed generation also reproduces the exact
current header hash. The remaining acceptance work is recovery of the approved historical real
`rLayout.h` baseline and the complete 110%-of-baseline p95/peak-memory comparison. The generic
full-store file query harness timed out because it rescans fact families per query; this is a
harness limitation, while native Doris is the required serving backend for the measured corpus.
Checkpoints remain diagnostic snapshots only; their real-asset overhead remains unmeasured. These
items are not marked complete from source inspection, a dry-run plan, or partial files.

The Flight SQL evaluation harness is implemented but its full-contract gate remains open. The
stale running containers were recreated with the opt-in overlay, publishing FE `8030`, `8070`,
`9030` and BE `8040`, `8050`; the external preflight observes both Flight listeners, startup
markers, the direct BE route, and a host-side FE socket. Doris 4.1.3 rejects the required qmark
probe with `acceptPutPreparedStatementQuery unimplemented`. The explicit benchmark-only fallback
renders supported values as checked SQL literals and completes the reused-connection matrix, but
the report remains `partial`: strict parity is 54/76 because PyMySQL and Arrow expose Doris
BOOLEAN values as `int` and `bool`, respectively. Doris's current FE producer also returns
FE-local result locations from its process-local address, so endpoint routing is not yet a clean
runtime boundary. The default MySQL/PyMySQL and loader paths are unchanged.

The 2026-08-09 complete-store optimization evaluation is now observed rather than merely planned.
Bounded source/unit-aware hydration is part of the generator serving path. Exhaustive/full-hierarchy
`rAIFSM` produced identical 11-header bundles in 32.123 seconds fresh and 31.683/31.653 seconds
on repeated runs; a paired traced run also produced exact output but exceeded the 5% tracing
overhead limit and retained only partial profile attribution. The canonical Doris physical design
is unchanged. The benchmark remains a reusable one-shot regression/promotion tool, while index,
bucket, storage, session, and Stream Load variants remain `not_observed`.
