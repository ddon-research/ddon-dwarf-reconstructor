# Implementation handoff

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../docs/reference/project-status.md).

This operational record is for the next implementing agent. The full plan remains incomplete.

- Branch: `codex/021-cpp-reconstruction-architecture`; preserve the existing dirty checkout.
- Original source/configuration snapshot: `1b10b75e751c97b1`. Its recoverable ZIP, index,
  staged/unstaged patches, and baseline artifacts remain under
  `output/refactoring-evidence/021/1b10b75e751c97b1/`.
- Implementation now exists. The user's request to actually implement findings superseded the
  execution pause; final real-asset output/performance acceptance is still required.
- Current production/test/configuration identity is recorded in
  `implemented-findings-working-state.json`: `8271e69eb0576d83dc9632ed3d8ccc3b44ce64c055f011d497e14d47453cd575`.
  It is refreshed after T104 and covers 590 root/nested production and test Python files plus effective project/tooling
  configuration, including the output-equivalence comparator, CU-key policy, and evidence
  helper; the identity algorithm is recorded in that external JSON.
- Implemented F014/F034 temporary-file and failed-rollback ownership, F019 session acquisition
  cleanup, F035 canonical symbol paths, F009 bounded diagnostic reads, and F006 empty coverage
  rejection/high-risk selectors. Focused failure tests and complete local loops passed.
- Addressed existing lint/format findings with precise pyelftools naming exceptions, the existing
  Typer CLI-file policy, literal mnemonic lists, direct canonical imports in tests, and formatting.
- Implemented the F003 domain move: `domain/services/cpp_reconstruction/` owns control flow,
  instruction effects, and operands; `domain/models/cpp_reconstruction/control_flow.py` owns
  published CFG values. CFI acquisition stays in infrastructure. Three old analysis modules were
  removed and all executable callers updated. Five pure tests moved into the domain test tree.
- All 71 moved function ASTs match their pre-move forms in
  `pre-domain-analysis-slice/algorithm-identity.json`. Known F022/F023 status defects are unchanged.
- Architecture now rejects domain-to-application and prohibited external module dependencies,
  with deliberate violation controls. Coverage includes the new reconstruction group.
- Method artifact ownership now fails closed for ambiguous duplicate display names when exact
  `owner_class_key` provenance is absent (T098/F015); the canonical provenance path and stable
  method IDs remain unchanged. Nested source conversion, manifest validation, and semantic report
  publication are staged and rollback-safe (T090-T094). The call-level process dependency check
  is narrow and has a deliberate violating fixture.
- T033 orchestration review is complete. `dwarf_implementation.py` delegates evidence transforms
  to focused siblings, `symbol_output.py` keeps report/manifest publication in one atomic
  transaction, and `composition.py` is already a narrow composition root. Three composition
  characterization tests pass; no arbitrary split or compatibility shim was introduced.
- Current local acceptance logs use `implementation-final-*`, `domain-analysis-*`, and the current
  continuation logs. After T102, `uv run just test-unit` passed 1,156 tests (7 deselected),
  `uv run just check` passed after `docs-api` refreshed six pages for 365 modules, and
  `uv run just test` passed 1,151 tests (12 deselected). `coverage-ci` passed with 80.68% pytest
  line coverage; the repository checker reports 84.2% total line / 68.1% branch coverage and
  all required high-risk groups pass their 80% line / 70% branch thresholds. `audit` passed with
  zero Prospector messages. Full-corpus compiler and performance acceptance remains open.
- T101/F039 is complete. Method-context requests carry aligned implementation/declaration CU
  offsets; analytical queries and batch maps use `(unit_offset, die_offset)` keys, and ambiguous
  unqualified offsets fail closed. The two-CU collision fixture, source-bound lookup fixture, and
  candidate-CU threading test pass in the 34-test focused slice. The completion evidence is in
  `measured-evidence.md`; it is source/configuration-bound to the current receipt above.
- T102/F040 is complete. The architecture quality suite enforces full-SHA external GitHub Action
  references with release comments while accepting repository-local actions; a deliberate
  unpinned fixture fails closed. The 26 architecture tests and all root gates pass. This does not
  establish remote GitHub settings, Dependabot behavior, or branch-protection state.
- T050 is complete for the current documentation slice. Architecture, validation, deployment,
  testing knowledge-base, roadmap, and README pages now describe the implemented C++ boundary,
  CU-qualified context, action provenance check, and blocked external evidence. `docs-api-check`
  and `docs-check` pass (365 modules, 17 Mermaid diagrams, 69 Markdown files), followed by the
  full root `check`, unit, and default test gates. No generated API page changed.
- T103/F041 is complete. `prepare_msvc_analysis.py` reuses the bounded MSVC command runner,
  translates timeout and missing-exit-status results into fail-closed `SonarAnalysisError`, and
  retains the existing `CompletedProcess` caller contract. Fourteen focused tests and the root
  unit/check/default-test/coverage-ci/audit gates pass. At that checkpoint, the receipt was 589 files with identity
  `0db071fa20ea337f4c0dd858d7183f835380558176f8162b722c5018d45ed096`; no MSVC/compiler claim
  is made.
- T104/F042 is complete. The Sonar/MSVC runner drains both child streams concurrently, retains a
  fixed 8 MiB prefix per stream, and marks truncation; preparation and header/compiler validation
  fail closed when required output is incomplete. The 30 focused tests, root unit/check/default
  test gates, coverage-ci, and audit pass; the refreshed receipt covers 590 files. This remains
  deterministic tooling evidence only and does not establish current-candidate compiler,
  full-corpus, or performance acceptance.
- MSVC compiler preflight is now recorded separately from acceptance. `vswhere` and
  `VsDevCmd.bat -arch=x64` locate the installed Visual Studio 18 Community toolchain, and
  `cl.exe /Bv` reports MSVC 19.51.36252. The current candidate `output/` has no generated-header
  bundle, so module validation fails closed for the missing directory. A retained 40-header
  `rLayout` baseline workflow run completed with 39 passes and one `C2040` failure in
  `rAIConditionTree.h`; its aggregate status is failed and evidence is under
  `output/refactoring-evidence/021/1b10b75e751c97b1/compiler-preflight/rlayout-baseline-021/`.
  T022/T060 remain open; this does not establish current-candidate compiler acceptance.
- The Doris BE recovery is successful. The D: FE/BE data paths remain intact and their original
  inspection/log evidence is retained. A hash-verified copy under
  `C:\DorisRecovery\ddon-analytical-dwarf\4.1.3-1b10b75e751c97b1-20260909-2016\` is now used by
  the canonical Compose services through the ignored `ops/analytical-dwarf/.env`. FE HTTP/SQL
  ports are 28030/29030 and BE HTTP is 28040. The initial recovery snapshot reported 251 tablets;
  the canonical service now reports 257 with 69.60% disk use, an empty error field, and a healthy
  heartbeat. FE and BE agree on that current count, the tablet checker reports zero unhealthy
  tablets, and the complete registry plus all fourteen family counts match the source manifest.
  The `MtObject` and `rLayout` header-only controls also succeeded. Do not enable
  `ignore_broken_disk` or delete the D: forensic source. The original Compose IDs were
  recreated during promotion; pre-promotion evidence and never-started forensic definitions
  retain the original D: mount configuration.
- Original baselines: all 32 rLayout samples have applicable byte parity and valid inventories;
  first 289-root all-output run published 254 successful/35 partial roots; first MtObject cold
  attempt failed because BE was unavailable. All failures and partial statuses remain retained.
- Do not resume `run-matrix.py` against this changed checkout: its original-producer hash guard
  correctly rejects it. Finish original-producer samples only from the retained snapshot in an
  isolated checkout after restoring the existing backend; keep candidate samples separate.
- `git diff --check`, the analytical-Doris preflight, and the complete local gates are now current:
  `just test-unit`, `just check`, `just test`, `just coverage-ci`, and `just audit` pass. The
  preflight records both locked image digests, healthy C: storage with 30.4% free space, and
  `ignore_broken_disk=false_or_unset`. Next command: begin the unchanged-code/performance
  continuation from the retained request set. Keep current-candidate controls and any 289-root
  outputs in fresh destinations; do not overwrite retained evidence.
- September 13 acceptance and configuration progress:
  - Centralized path configuration (`ELF_FILE_PATH`, `DWARF_STORE_MANIFEST`, `ORBIS_OBJDUMP_PATH`,
    `ORBIS_AS_PATH`, `LLVM_*`, and Doris endpoints) in `.env` and `Config.from_env()`, eliminating
    command-line path bloat.
  - Canaries (`MtObject` headers/all, `rLayout` all, `rAIFSM` exhaustive) passed with concise CLI.
  - Stage 4 unified 289 Season 2 batch run completed successfully under `output/acceptance-candidate/season2/`
    yielding 254 successful / 35 partial roots, 1,690 classes, 898 headers, 2,564 assembly files,
    5,004 source files, and 29,048 methods, achieving exact parity with the historical baseline
    `021-season2-all-cold-01.json`.
  - T022 MSVC standalone compiler validation completed across all 898 generated headers using MSVC
    19.51.36252: 435 passed, 463 failed, 0 timed out, 0 unobserved; evidence retained at
    `output/acceptance-candidate/season2-msvc/msvc-header-validation.json`.
  - All local gates (`just check`, `just test-unit`, `just test`, `just coverage-ci`, `just audit`)
    pass with 0 Prospector violations, 0 lint/format issues, and coverage thresholds met.
- Remaining: repository review closure (T004-T006), supporting subsystem decisions (T034-T035),
  full baseline/performance matrix (T011, T060), documentation/spec convergence (T070/T071),
  and measured lessons. Doris service recovery is observed; full-corpus parity and standalone MSVC
  compiler evidence are characterized. Do not mark the umbrella goal complete without addressing
  the remaining open tasks.
