# Research: Clean Architecture Audit

## Scope and method

This audit covers the maintained root runtime under `src/`, its tests, the
standalone `tools/dwarf_spec_pipeline/` project, active documentation, Spec Kit
artifacts, and repository Python instructions. The implementation kept
proprietary inputs, generated DWARF reference documents, runtime caches, and
generated headers outside the repository.

The review used four passes:

1. inventory tracked source, tests, documentation, specifications, and launch
   surfaces;
2. run the existing fast test and quality gates before changing guidance;
3. inspect cache, lookup, parser, renderer, adapter, and composition boundaries;
4. reproduce high-risk claims with small in-memory or temporary-file probes.

The repository contained 145 tracked production Python files and 95 root test
files. The nested specification tool was reviewed separately because it has its
own package, lockfile, and quality loop.

## Baseline evidence

- `uv run just test-unit`: 406 passed, 21 deselected.
- `uv run just check`: passed Ruff, formatting, structure, ArchUnitPython,
  Pyrefly, and deptry checks.
- The worktree was clean before the audit on `main`, nine commits ahead of
  `origin/main`.
- The passing suite logs errors from malformed test doubles, including a CU
  header attribute error and mocked indexed-DIE failures. Those paths are
  currently converted into fallback behavior, so a green test result does not
  prove that the fast lookup path is healthy.

## Confirmed findings

| ID | Priority | Finding and evidence | Planned direction |
| --- | --- | --- | --- |
| CA-001 | P0 | `src/ddon_dwarf_reconstructor/infrastructure/artifacts.py:49-115` identified a warm source using only size and first/last 64 KiB. A temporary-file probe changed 100,000 middle bytes without changing those regions and showed `boundary_collision=True`; both returned identities differed from the actual SHA-256. | Make source identity one explicit contract. Reuse a full SHA-256 only when complete metadata matches; otherwise re-establish it before authorizing derived offsets after a same-path replacement. |
| CA-002 | P0 | `src/ddon_dwarf_reconstructor/domain/services/parsing/class_parser_scan.py:198-230` and `src/ddon_dwarf_reconstructor/domain/services/lazy_index_search.py:123-161` selected and cached a positive candidate as complete even when `state.timed_out` was true. A direct state probe recorded `complete=True` after timeout in both services. | `SearchResult` now carries status, provenance, elapsed time, and diagnostics. A timeout may be cached only as `complete=False`; callers reject it when complete evidence is required. |
| CA-003 | P1 | `src/ddon_dwarf_reconstructor/core/dwarf.py:36-45` declared `DwarfCompilationUnit.header` as a mapping, while `src/ddon_dwarf_reconstructor/domain/services/lazy_index_search.py:94-99` read `cu.header.unit_length`. Existing test doubles used a mapping and the baseline logged `dict` attribute failures. | `core.dwarf.compilation_unit_length()` now owns the mapping/object normalization used by domain search and lookup. |
| CA-004 | P1 | `src/ddon_dwarf_reconstructor/domain/services/parsing/class_parser_methods.py:98-105` accepts decimal text only. The checked-in `resources/rGUI.dwarfdump` contains at least six `DW_OP_constu 0x...` expressions; the parser probe returned `0` for `0x5`, `0x7`, and `0x11`. The same parser sets `is_noexcept` from `DW_AT_noreturn` at line 56, conflating `[[noreturn]]` with C++ `noexcept`. | Parse expression operands with the DWARF numeric grammar and map only evidence that actually represents exception specifications. Add real-text and synthetic attribute tests. |
| CA-005 | P1 | `src/ddon_dwarf_reconstructor/domain/services/lazy_index_search.py:145-159` returns `fallback.die_offset` but, when the best score is non-positive, caches that DIE with `best.cu_offset` and `best.score`. A direct probe returned DIE `0x400` while recording CU `0x100`. | Keep candidate identity, score, completion, and CU/DIE provenance together; never synthesize a new record by mixing state fields from different candidates. |
| CA-006 | P1 | `src/ddon_dwarf_reconstructor/domain/repositories/cache/cache_schema.py:162-177` migrated an old record with `"complete": True` while the score was explicitly unknown. `cache_persistence.py:177-201` also defaulted missing completeness to true during merges and best-definition selection. | Runtime loading now requires schema 5.0 and the complete current shape; it does not promote historical records. Explicit maintenance commands remain responsible for rebuilds, and unknown completeness is never promoted. |
| CA-007 | P1 | `src/ddon_dwarf_reconstructor/infrastructure/elf_session.py` owns the resource graph. The invalid-ELF probe previously raised during `__enter__` and left `file_handle.closed=False`; repeated PS4 patch calls also produced distinct wrapper layers. | `ElfDwarfSession` closes partial construction, is injected through `DwarfSessionFactory`, and applies `patch_pyelftools_for_ps4()` once per session entry. |
| CA-008 | P1 | The former `domain/repositories/cache/header_cache.py` keyed files by stem only and wrote directly. Two different `one/build.elf` and `two/build.elf` paths reused the same cache file and the second instance accepted the first header. | The duplicate header cache was deleted. `AtomicHeaderPublisher` is the sole header writer and publishes a manifest with rollback and stale-file removal. |
| CA-009 | P2 | `src/ddon_dwarf_reconstructor/infrastructure/config/dwarf_config.py:24-55` silently ignored invalid integer/float environment values. A configured `DWARF_MAX_SEARCH_TIME_MS=invalid` therefore became the default without a diagnostic, and the setting was not consumed by targeted search. | `DwarfRuntimeConfig` now validates positive values at startup and connects the millisecond setting to the targeted search timeout. Full hierarchy scans retain their separate bounded scan policy. |
| CA-010 | P2 | `src/ddon_dwarf_reconstructor/domain/services/parsing/type_resolution.py:34-75,214-238`, `class_parser_aggregate_types.py:155-175`, `class_parser_class_info.py:166-184`, `file_registry.py:147-168`, and `infrastructure/elf_platform.py:36-105` catch broad failures or return guessed/empty values. These are not all defects in isolation, but they make unavailable evidence indistinguishable from successful resolution. | Introduce structured diagnostics at each boundary, catch only adapter-specific expected failures, and make the application decide whether partial evidence is publishable. |

## Brittle assumptions requiring focused regression tests

- `src/ddon_dwarf_reconstructor/domain/services/generation/header_ordering.py:100-123`
  removes the lexicographically smallest remaining node when no topological node
  is ready. This makes cycles deterministic but silently emits an order for a
  by-value cycle that should be a blocking diagnostic.
- `src/ddon_dwarf_reconstructor/domain/services/generation/header_type_planning.py:34-58`
  emits `template <typename T>` for every specialization. Multi-parameter and
  non-type template arities need structured template evidence before rendering.
- `src/ddon_dwarf_reconstructor/domain/services/generation/header_member_rendering.py:141-154`
  formats `class_info.die_offset` as an integer even though the model permits
  `None`. The optional evidence contract needs an explicit unresolved rendering.
- `src/ddon_dwarf_reconstructor/domain/services/parsing/class_parser_scan.py:102-160`
  treats `has_children` as proof of members and uses the first fallback candidate
  after timeout while assigning it the best score. This is a provenance and
  completeness mismatch even when no exception is raised.
- `src/ddon_dwarf_reconstructor/domain/services/parsing/class_parser_aggregate_types.py:51-70`
  maps malformed enumerator values to zero. Invalid input must not invent a
  numeric enumerator value.
- `src/ddon_dwarf_reconstructor/main.py:179-195` writes each generated header
  directly. A failure after the first file leaves a partial bundle despite the
  artifact policy requiring atomic publication.
- `tools/dwarf_spec_pipeline/src/dwarf_spec_pipeline/readers.py` is 309 lines
  and `source_manifest.py:86-91` uses a broad cleanup catch. The nested tool is
  independently healthy, but it should receive the same decomposition and
  exception-specific review when its next feature changes behavior.

## Test and documentation gaps

The implementation added same-size middle replacement, malformed-root,
timeout-candidate, mixed-provenance, invalid-configuration, partial-cache, and
failed-publication regressions. Search fixtures still intentionally cover both
mapping-style and object-style CU headers at the adapter boundary. The explicit
real-asset and compiler tiers remain separate because they require local tools
and immutable inputs.

The active instructions and architecture documents previously described
duplicate indirection and alternate entry points as contracts. This audit updates
those documents to describe one canonical application path and intentional
breaking refactors. Terminology from external DWARF standards or ABI layout
remains because it describes the input format or binary target, not a software
API promise.

## Scope boundary

The focused implementation is recorded in the same feature so the findings and
contracts remain traceable. Nested-tool review and full Tier 1/2 quality gates
are complete. Explicit real-asset/compiler evidence is deferred; the real PS4
acceptance artifact remains outside the repository.

## Implementation evidence

| Contract | Implementation evidence |
| --- | --- |
| Source identity | `infrastructure/artifacts.py`, `domain/ports/source_identity.py`, and `tests/infrastructure/test_artifacts.py` use metadata for warm reuse and a full SHA-256 identity when metadata changes or verification is requested. |
| Search status | `domain/services/search_result.py`, `lazy_index_search.py`, `class_parser_scan.py`, and `tests/domain/services/test_lazy_index_paths.py` preserve status, score, CU/DIE identity, and timeout diagnostics. |
| Cache integrity | `domain/repositories/cache/cache_schema.py`, `cache_persistence.py`, and cache tests require schema 5.0/current shape and never promote incomplete evidence to complete. |
| Composition and publication | `infrastructure/elf_session.py`, `application/generators/generator_workflow.py`, `infrastructure/header_output.py`, and generator setup/main-path tests cover partial construction, one-time patching, atomic replacement, rollback, and stale-file removal. |
| Nested specification pipeline | `tools/dwarf_spec_pipeline/src/dwarf_spec_pipeline/readers.py` and `source_manifest.py` were reviewed; source cleanup catches only download/checksum/filesystem failures, and nested checks/tests pass. |
| Documentation contract | `AGENTS.md`, Python instructions, README, architecture/testing/flow docs, and this feature describe the packaged CLI, typed configuration, session ownership, search results, and atomic publication. |

## CI follow-up: cross-platform source identity

The 2026-08-03 goal run inspected all seven open Dependabot PRs with the GitHub CLI. PRs 1-7
propose isolated GitHub Action or nested-pipeline dependency updates; their lint, quality, and
nested-tool checks pass, while each required correctness job fails at the same test:
`tests/infrastructure/test_artifacts.py::test_catalog_reuses_identity_after_source_relocation`.
The referenced [PR #7 job](https://github.com/ddon-research/ddon-dwarf-reconstructor/actions/runs/30774416064/job/91567057120)
reports `AssertionError: relocation rehashed the complete source`.

The failure is platform-specific. Linux changes `st_ctime_ns` when a file is renamed, but the
existing lookup key included ctime. Windows therefore passed the test locally while Ubuntu
rehashes the unchanged moved file. The test-result publisher's separate 403 check-run write is
secondary and does not explain the correctness failure.

The follow-up implementation centralizes the relocation-stable key in the source-identity port
using size, mtime, device, and inode. The infrastructure catalog retains ctime and path history
as a mutation guard, accepts ctime-only drift only when the recorded path disappeared, reuses the
recorded strong identity, and keeps `verify=True` as the complete-hash boundary. A ctime-only
existing-path regression prevents the portability fix from accepting same-path mutation.

Focused validation after the change: the artifact unit module passed 12 tests, source-bound lazy
index/cache tests passed 27 tests, and Pyrefly reported zero diagnostics. The root loop then
passed `just check`, `just test-unit` (445 passed, 6 deselected), `just test` (447 passed, 4
deselected), `just coverage-ci` (84.87% total coverage), and `just audit` (zero diagnostics).
The nested project passed `just test` (17 passed, 1 deselected) and `just check`; its official
test selection skipped one test because the external official artifact is unavailable. A
post-fix remote PR rerun remains T025 because the repair has not been published.
