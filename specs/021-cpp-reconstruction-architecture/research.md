# Architecture review decisions

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../docs/reference/project-status.md).

This research record serves maintainers evaluating the implementation choices. Source inspection
is distinct from fixture, real-asset, compiler, and performance acceptance.

## Accepted decisions

| ID | Finding and evidence | Decision | Task |
| --- | --- | --- | --- |
| F001 | The initial worktree has staged and unstaged changes. | Snapshot effective files, index, and patches before mutation. | T001 |
| F002 | Constitution calls Prospector non-blocking; AGENTS and just audit require it. | Amend constitution to the stricter operational rule. | T003 |
| F003 | implementation_effects/parity contain pure policy alongside external evidence types. | Move characterized pure behavior to cpp_reconstruction. | T030 |
| F004 | implementation_abi_facts mixes DIE acquisition with return classification. | Split typed facts and pure classification; preserve traversal semantics. | T031 |
| F005 | toolchain_process already owns bounded streaming; version helpers repeat subprocess.run. | Implemented in T032: shared bounded capture/version probing, finite timeout metadata, and a per-run/profile identity cache now serve assembler, linker, objdump, readelf, and ABI-probe paths. | T032 |
| F006 | Coverage groups select literal old paths and count an empty group as 100%. | Test empty-group rejection and migrate high-risk selectors with moves. | T040 |
| F007 | Regression helper recognizes legacy bundle paths and broadly normalizes field names. | Implemented in T020/T021: the current flat publisher inventory (`implementation-report.json`, `symbols.manifest.json`, headers, assembly, and eligible objects) is validated against physical files; byte artifacts compare exactly and only demonstrated report/runtime-derived fields are normalized. | T020/T021 |
| F038 | Parquet primary-definition fast path consumed a selection-cache offset without checking explicit completeness; Doris rejected `False`, so incomplete historical evidence could be promoted. Two focused tests reproduced the adapter mismatch. | Check `get_symbol_completeness` before using the fast path; complete hints remain fast, while explicit incomplete hints fall back to the bounded query without changing its status or provenance. | T100 |
| F039 | `DorisBatchContextQuery` keyed DIEs, attributes, references, and locations only by `die_offset`, even though analytical rows are keyed by `(unit_offset, die_offset)`. A same-offset fixture from two CUs could therefore mix or select the wrong evidence. | Carry aligned CU offsets in `MethodContextRequest`, scope batch family filters and in-memory joins by source/CU/DIE, and fail closed when an unqualified offset is ambiguous. Thread selected candidate provenance from raw validation reports into follow-up lookups. | T101 |
| F040 | The repository policy requires external GitHub Actions to be pinned to full commit SHAs with readable release comments, but no deterministic test checked that policy; actionlint validates workflow syntax rather than provenance pinning. | Add a narrow architecture-quality check over workflow YAML, allow repository-local actions, and include a deliberate unpinned fixture. Keep remote settings and action updates outside the checkout-only gate. | T102 |
| F041 | `tools/sonar/prepare_msvc_analysis.py` invoked `vswhere`, the developer command shell, and Sonar Build Wrapper through `subprocess.run` without a timeout, while the adjacent MSVC validation adapter already provided finite timeout status. | Reuse the bounded MSVC command runner, adapt its typed result back to the existing `CompletedProcess` contract used by the preparation workflow, and convert timeout status into `SonarAnalysisError` so incomplete compiler evidence cannot be treated as a captured database. | T103 |
| F042 | The reused Sonar/MSVC command runner applies a finite timeout but `subprocess.run(capture_output=True)` retains unbounded child stdout and stderr; compiler/build-wrapper diagnostics can therefore consume unbounded memory before the timeout gate runs. | Drain stdout and stderr concurrently with a fixed retained-byte budget, preserve whether either stream was truncated, and fail the preparation/validation workflow closed when required output is incomplete. Keep timeout, exit status, and invocation behavior unchanged for bounded output. | T104 |

## Rejected proposals

- Invalid-exception guard: CPython 3.14.7 parses unparenthesized exception lists.
- Blanket frozen/slotted dataclasses: mutable builders and session caches are intentional.
- Arbitrary module shrink targets and compatibility forwarding packages: responsibility and
  complexity determine extraction; internal callers move together.
- Blind replacement by TypeChainTraverser: stopping rules, bounds, and source/cache identity
  require characterization before sharing behavior.
- Blanket proposed Ruff families: 329 exploratory findings were observed with replacement
  selection; count is not an estimate of necessary fixes under an additive policy.
- T033 orchestration split: `dwarf_implementation.py` already delegates association, range,
  context, and reporting responsibilities to focused sibling services; `symbol_output.py` owns
  one staged publication transaction; and `composition.py` is a small composition-root factory.
  Further splitting would introduce forwarding seams or scatter transaction state without a
  measured correctness or performance benefit. Composition wiring is characterized by
  `tests/infrastructure/test_composition.py`; no compatibility shim was added.

## Open evidence

Full module review, Doris readiness, unchanged-code output repeatability, compiler readiness,
baseline matrix, and final measurements remain open. Do not promote these from path existence.

## First inspection slice

| ID | Observation | Disposition and next evidence |
| --- | --- | --- |
| F008 | Initial lint reports DWARF protocol naming errors after pre-existing suppression removal. | T042: restore scoped policy without renaming adapter methods. |
| F009 | toolchain_process.read_text_prefix uses read_bytes before slicing. | Implemented in T080: the diagnostic prefix is read with a bounded file handle/read and its decoding/missing-file behavior is preserved. |
| F010 | Process drain threads do not propagate write failures to the calling operation. | Implemented in T080: drain failures are retained, promoted after process cleanup, and chained to the bounded tool error; timeout and no-pipe cleanup remain covered. |
| F011 | Linker exit zero can be observed without output; stale output may survive failure. | T081: characterize output freshness; separate any evidence-status correction from byte refactoring. |
| F012 | collect_object_metadata immediately discards output_dir and stem. | Implemented in T032 as a narrow contract cleanup: the metadata capability now accepts only the object, readelf tool, and timeout; callers were updated atomically. |
| F013 | core.serialization forwards hash functions already owned by core.content_hash. | Implemented in T082: callers import the canonical content-hash module and serialization owns JSON conversion only; no forwarding seam remains. |
| F014 | temporary_text can fail before returning its temporary path to cleanup caller. | Investigate with write/fsync failure test before accepting a repair task. |
| F015 | Method fallback ownership takes first matching duplicate name. | Implemented in T098: provenance-backed `owner_class_key` remains authoritative; ambiguous display-name and containing-class fallbacks now fail closed to shared output instead of silently attributing an artifact to the first match. |
| F016 | Positive-float configuration accepts non-finite floats through <= comparison. | Implemented in T087: DWARF and Doris timeout fields reject NaN/infinity while the existing zero-allowed analysis wait policy remains valid. |
| F017 | Domain-to-application and prohibited process dependencies lack explicit rules. | Implemented in T041: import-direction rules remain explicit and a narrow AST call check rejects unbounded `os.system`/`os.popen` and legacy subprocess convenience calls in inner layers, with passing and deliberate-failure controls. |

Installed Pylint defaults: `min-similarity-lines=4`, with comments, docstrings, imports, and
signatures ignored. The profile has no explicit similarity override. Increasing to eight lines
would weaken this default; no such change is selected. Additive Ruff probing reports 354
findings across src/tests/tools/sonar, including 239 argument-count findings at default max 5.
These are audit findings, not an automatic cleanup mandate.

## Source ownership and repeatability follow-up

| ID | Observation | Disposition and next evidence |
| --- | --- | --- |
| F018 | TypeChainTraverser caches process-global DIE results by CU/offset, and repository callers never clear them. A retained two-source fixture returned source A's offset 100 for source B, whose target is 200. | Implemented in T083: caches are owned by each ClassParser traverser, integer-key collisions are isolated, and clear_cache releases retained DIE references. Traversal stopping rules and within-source behavior are unchanged; real-asset parity remains blocked. |
| F019 | AnalyticalDwarfSession.__enter__ can raise after store acquisition without closing it, unlike ElfDwarfSession. | Characterize source mismatch and as_dwarf_info failure with a fake store before accepting cleanup repair. |
| F020 | The first header-only rLayout baseline failed os.replace with WinError 5; stage rollback left no output. Eight full-output runs completed. | Retain failure, retry in a fresh destination/cache, investigate if repeated. No production workaround or cause attribution yet. |

F018 reproduction is retained as `type-chain-source-collision.json` under the initial evidence
root. Existing traversal tests use Mock compilation-unit offsets, which bypass the integer-keyed
cache; new characterization must exercise actual integer CU/DIE keys and interleaved sessions.

## Validation and workflow follow-up

| ID | Observation | Disposition and next evidence |
| --- | --- | --- |
| F021 | Live GitHub settings report main unprotected, Dependabot security updates disabled, and secret scanning/push protection disabled. | Explicit remote follow-up; checkout edits cannot enable these settings. No settings changed. |
| F022 | A conditional CFG fixture with a saved/written rbx and no restore returns observed/preserved. The set subtraction accepts either a save or a restore. | Behavioral defect reproduced in parity-evidence-gaps.json. Characterize separately before migration; no silent status change inside evidence parity refactoring. |
| F023 | Identical unresolved direct-call references return observed external-edge parity despite the function's fail-closed documentation. | Behavioral defect reproduced in parity-evidence-gaps.json. Preserve the defect record and prepare a separate acceptance proposal. |
| F024 | PerformanceRunner computed CPU/I/O deltas from currently live process-tree samples; exited descendants could disappear from later totals. | Implemented in T099: retain first/last counters per PID and creation time for the lifetime of the run, include observed descendants in CPU/I/O totals, and keep the raw sample schema unchanged. |
| F025 | The architecture test fixes HeaderRenderingComponents field count at ten and checks concrete class bases. | T041: replace implementation-shape assertions with meaningful dependency and collaborator behavior checks where the contract permits composition changes. |

The complete checked-in workflow set and composite action were read alongside the local just
contract. PR 15's diff and checks are retained; all required proposal checks succeeded, so no
failed log applies to that proposal. These are remote proposal observations, not evidence that
the current dirty checkout passed correctness. No workflow or action-version change is selected.

The full-output rLayout profile completed eight samples. The header-only retry in a new
destination/cache succeeded; the original WinError 5 sample remains retained and excluded from
successful-run timing summaries, with the failure still part of reliability evidence.

## Nested pipeline and publication review

| ID | Observation | Disposition and next evidence |
| --- | --- | --- |
| F026 | Nested source acquisition cleans temporary files after checksum failure, but the earlier download exception path can leave them behind. | Implemented in T090: download/read failures now clean only the new temporary path; verified existing cache entries are never removed. |
| F027 | Nested converters use unbounded capture without timeout and unlink existing intermediates before conversion succeeds. ConversionError also escapes the CLI's expected-error boundary. | Implemented in T091: the independent runner uses finite waits, file-backed bounded diagnostics, process cleanup, staged output, and a CLI error boundary for chained `ConversionError`; real converter execution remains explicitly blocked. |
| F028 | Nested output validation ignores undeclared/duplicate manifest entries and can accept absent semantic files even when the manifest declares them. | Implemented in T092: complete relative inventories, duplicate/missing/extra checks, safe paths, hashes, and required semantic pairs are validated before document consumption. |
| F029 | Nested build supports selected versions, but directory validation always requires versions 2, 3, and 4. | Implemented in T092: validation derives a nonempty selected version set from the manifest and retains all-three-version enforcement only in official acceptance. |
| F030 | The audit command rewrites semantic JSON/Markdown beside the publication without refreshing manifest hashes; write_index can leave one file updated if the second write fails. | Implemented in T094: semantic report files are staged and rollback-safe; canonical document manifests remain unchanged because audit outputs are a separate derived publication. |
| F031 | build_document combines omission classification, heading transitions, table normalization, and mutable section accumulation in one long function. | Implemented in T093: `DocumentBuilder` owns explicit state in a cohesive sibling while `normalize.py` remains the public facade; intermediate provenance and deterministic fixture output remain covered. |
| F032 | Converter identity is not recorded in the nested artifact manifest, and Docker's converter packages are resolved from apt at build time. | Record runtime/tool identities in external baseline evidence; a new published provenance schema is a separate behavioral proposal. |
| F033 | SymbolPublisher discards canonical-source/assembler rejection diagnostics when no file is emitted. | Baseline missing output remains explicitly unexplained where the producer retains no cause; propose a separate evidence-contract change rather than inventing a status. |
| F034 | If stage publication and rollback rename both fail, SymbolPublisher's finally block attempts to delete the backup containing the previous valid bundle. | T085: reproduced with deletion intercepted in publication-rollback-failure.json; preserve recoverable backup and chained failures. |
| F035 | SymbolPublisher duplicates a weaker relative-path validator than artifact_io.safe_relative_path, omitting drive-relative path checks. | T088: use the canonical validator and characterize Windows drive-relative, root-relative, and traversal paths. |

`resource-ownership-failures.json` additionally reproduces F014 (temporary text survives fsync
failure) and F019 (failed analytical session entry leaves its acquired store open). These
failure-path repairs preserve successful output bytes and are accepted refactoring work.

## Analytical loader continuation

| ID | Observation | Disposition and next evidence |
| --- | --- | --- |
| F036 | Every `_load_label` call reparses the complete materialization manifest. Three file labels caused three manifest reads in an isolated probe. | Implemented in T096: execute validates and passes one manifest through the load, native labels reuse its source SHA, and a three-file concurrent fixture observes one manifest read with unchanged deterministic results. |
| F037 | `_load_label` binds source prefix, family, and relative path but omits destination table and producer/configuration identity. Two different table plans produce the same label. | T097: characterize cross-table/rebuilt-manifest identity and prepare a separate durable-label acceptance proposal; do not silently invalidate existing load receipts. |

## Method ownership continuation

F015 is resolved without changing the normal implementation-discovery path. Methods produced by
`dwarf_implementation.py` already carry an exact `owner_class_key`; `symbol_output_methods.py`
now refuses to select among duplicate display names when that provenance is absent. The artifact
is retained under `shared` and root ownership is omitted, which is safer than publishing a
plausible but unverifiable class assignment. `test_method_ownership_fails_closed_for_ambiguous_display_name`
covers the duplicate-name case. No header bytes or method identifiers change when the canonical
provenance field is present.

`doris-load-label-probe.json` establishes the local call count and collision, not live server
acceptance. The checked-out Doris Stream Load reference describes duplicate labels and
`ExistingJobStatus`; the current client classifies duplicate-label responses as failed. Do not
reinterpret them as successful without verifying destination and publication identity.

The September 7 backend startup error is an environmental blocker, not a selected application
refactoring. Restore the existing storage mount and queryable backend before continuing T011.
The retained store and projection have not been purged or rebuilt.
