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
- [x] Run focused, repository, real-asset, and environmental validation.
- [x] Run the complete-store canonical/lookup/statistics optimization evaluation and record the
  observed N+1 hydration hotspot, exact `rAIFSM` parity, and rejected source/name candidate.
- [x] Implement bounded source/unit-aware hydration for metadata, attributes, references, and
  child-tag counts, then run exact traced/untraced exhaustive `rAIFSM` confirmation. The serving
  algorithm is retained; remaining physical variants stay `not_observed` until separately measured.
- [x] Recheck the complete store with eager/lazy reference prefetch, decoded-serving attribute
  projection, and targeted child-tag filtering. Record exact output hashes, cold/warm samples,
  trace attribution, rejected candidates, and the additive canonical registry identity refresh.
- [x] Screen the source/unit-bound hydration candidate against the exact canonical ELF path;
  retain exactness and query-fan-out evidence, reject the candidate, and keep global hydration as
  the default.
- [x] Activate the positive standalone candidates together as `combined-positive-below-gate`,
  confirm exact exhaustive `rAIFSM` parity with three cold/five warm repetitions, and record the
  interaction result and auxiliary-statistics promotion boundary.
- [x] Regenerate all 289 Season 2 roots in bounded external batches and audit every published
  header with MSVC as an independent translation unit.
- [x] Correct nested-base closure, nested-base qualification, nested-template forward
  declarations, and namespace-root lookup/rendering defects found by the compiler audit.
- [x] Replace header-generation multiple inheritance with composed `HeaderRenderer` collaborators
  and a typed immutable render context.
- [x] Replace mutable generator setup with the typed `GenerationFacade`/`GenerationRuntime`
  boundary and explicit resource ownership.
- [x] Separate Doris serving from composed JSONL/Parquet validation adapters; centralize definition
  candidate construction and preserve query truncation/diagnostic status.
- [x] Add bounded Doris cache lifecycle, immutable serving-profile validation, explicit registry
  migration, staged publication verification, and typed Stream Load outcomes.
- [x] Add source-bound placeholder rejection after a refactor run exposed silent unavailable-query
  success semantics.
- [x] Re-run complete Season 2, independent MSVC closure, and matched warm performance evidence
  after the boundary refactor. The final run completed 289/289 roots, 2,745/2,745 headers, and
  3,034 published files with exact header and bundle-manifest parity. Independent MSVC passed
  2,745/2,745 units with zero failures/timeouts. The matched warm exhaustive `rAIFSM` benchmark
  recorded p95 `15.796 s` and peak RSS `132.9 MiB`; reports remain outside source control.

## Status notes

Boundary-refactor status (2026-08-11): deterministic repository gates and representative byte
parity are observed, but fresh full-corpus acceptance is not. The pre-fix external run produced
289 directories/manifests but only 1,653 headers versus the immutable 2,745-header baseline because
Doris became unavailable and unresolved roots were incorrectly reported as success. The generator
now propagates non-complete analytical lookup evidence and rejects unresolved source-bound
placeholders. The full rerun is blocked by a Doris BE crash (`online_backend_num=0/1`); `cl.exe`
was not available for the independent compiler gate, and the 110%-of-baseline warm p95/RSS gate is
not observed. Keep these states separate from the historical 2026-08-10 full Season 2/MSVC result.

Boundary-refactor update (2026-08-13): the corrected batch-001 run completed 73/73 roots and
598/598 headers with zero byte-hash mismatches against the immutable baseline for every compared
header. A targeted `rOcdImmuneParamRes` run also published 8/8 headers successfully. Two fresh
full 289-root attempts reached root 190 and the startup/hydration phase respectively, then the
Windows host rebooted without a clean shutdown (Kernel-Power 41 / WER BlueScreen evidence); no
partial output was accepted because publication is atomic. A source-bound single-symbol run was
reproduced successfully after the first reboot. MSVC `14.51.36231` is installed; the independent
11-header probe and the 598-header batch-001 closure passed with zero failures/timeouts (warnings
remain separate); the 2,745-unit full closure remains pending.
The current Doris FE is not observable after the second reboot because its configured 9030 host
port lies in the Windows excluded range; no substitute backend or skipped test is being treated as
full-corpus evidence. Matched post-refactor performance is therefore `not_observed`.

Current boundary (2026-08-10): the promoted durable v1.1 store is
`output/analytical-dwarf/main/store-4236f598acc8f158`; native Doris is the active backend, while
versioned Temp stores, versioned Doris databases, and Iceberg measurements below are historical
evidence only. The promoted generation serving path now uses lazy reference prefetch, the
decoded-serving attribute projection, and the source/name b8 lookup table. The full Season 2
generation suite and per-header MSVC syntax/closure gate described below are historical
2026-08-10 observations; the post-refactor rerun remains blocked as described above. IDA/Sonar
evidence and byte comparison with the unavailable historical approved header remain separate
gates.

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

The 2026-08-09/10 complete-store optimization evaluation is now observed rather than merely planned.
Bounded source/unit-aware hydration, child-frontier/reference prefetching, per-unit line-program
caching, lazy reference prefetch, the decoded-serving attribute projection, and the b8 source/name
lookup are part of the generator serving path. The prior canonical `eager/full/all` run produced an
exact 11-header bundle with `19.121/19.127 s` warm p50/p95; the promoted combined path measured
`16.1152/16.1187 s` with exact output and lower warm p95 RSS. Raw attribute columns remain in the
canonical family. The targeted child-tag filter regressed warm p50 by 10.5% and was rejected; b2
and b4 lookup tables remain comparison-only. The benchmark remains a reusable one-shot
regression/promotion tool, while index, bucket, storage, session, and Stream Load variants remain
`not_observed`.
The fair-path unit-bound hydration screen preserved exact `rAIFSM` output but took `289.048 s` and
expanded the partial trace to `26,463` observations, so the candidate is rejected for query fan-out.
The combined positive-below-gate batch then measured `16.1152/16.1187 s` warm p50/p95 versus
canonical `19.1208/19.1271 s`, with exact output and lower warm p95 RSS. Its active b8 auxiliary
table added `7.23%` storage. A follow-up selective analysis produced two manual terminal-success
jobs with zero failed subjobs. The b8 table is now part of the canonical load plan and is refreshed
from the source-bound index; the canonical physical family model and fourteen-family registry row
contract remain unchanged. The full Season 2 generation suite then completed with 289/289
published roots and exact header manifest integrity; per-header MSVC syntax/closure acceptance also
passes, while IDA/Sonar checks remain separate acceptance gates.

Current acceptance update (2026-08-14): the earlier blocked full-corpus attempts are historical
and are not combined with the accepted run. The final run used healthy remapped Doris FE/BE
endpoints and the validated source/profile-bound selection cache. Request hydration caches still
reset per root. Removing the selection cache changed 15 dependency headers and 21 header payloads,
so it is not an acceptable canonical compatibility switch; an empty transient Doris query cache
only changed bounded query latency by milliseconds in the retained report.
