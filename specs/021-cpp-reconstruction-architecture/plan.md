# Repository-wide architecture review and refactoring plan — v6

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../docs/reference/project-status.md).

## Summary and corrections to v5

Review the entire repository and implement justified refactorings, including analytical storage and nested tooling. Preserve current header output exactly and allow at most **10% regression in measured median and tail runtime**, assessed separately for each workload and cache state.

This replaces [implementation_plan.md](C:/Users/morph/Downloads/implementation_plan.md). The review established several necessary corrections:

| Gap in v5 | Required correction |
|---|---|
| Narrow file list presented as a comprehensive review | Inventory every subsystem and track review coverage before choosing refactoring slices. |
| Spec Kit introduced after implementation | Establish specifications, contracts, tasks, and analysis before production changes. |
| Invalid exception-syntax claim | Remove it. The syntax parses on the pinned CPython 3.14.7; no custom syntax guard is warranted. |
| Assumed `.context.json` outputs | Baseline actual publisher behavior: `implementation-report.json`, manifests, and eligible assembly/object files. |
| Whole-manifest hash equality | Separate artifact integrity from equivalence; reports can contain invocation-specific metadata. |
| Automatic replacement with `TypeChainTraverser` | Characterize behavior first: its stopping rules, depth limits, diagnostics, and caches differ from ABI fact extraction. |
| New generic toolchain helper/service | Reuse the existing bounded process runner and introduce narrow capabilities where callers need them. |
| Compatibility shims and arbitrary line-count targets | Update internal callers atomically; split responsibilities rather than aiming for approximately 380 lines. |
| Blanket frozen/slotted models and broad lint expansion | Preserve purposeful mutability and introduce individually justified checks. |
| “19 existing Ruff findings” | The exploratory proposed-rule selection reports 329 findings at current settings, including 239 argument-count findings. Inventory before enforcement. |
| Missing coverage migration | Update path-based coverage groups when modules move; reject empty groups. |

Review evidence is limited to targeted source/configuration inspection, local syntax verification, and **12 passing architecture tests**. Full-corpus generation, compiler acceptance, and performance baselines remain unperformed. The accidental Ruff fixes made during inspection were reversed; the attachment remains unchanged.

## Phase 0 — Preserve the working state and establish governance

1. Record HEAD, branch, staged and unstaged patches, relevant untracked files, and hashes of effective source/configuration inputs. Preserve a recoverable external snapshot of the working tree. The baseline identity must include existing uncommitted work.
2. Create the umbrella feature at `D:\ddon-dwarf-reconstructor\specs\021-cpp-reconstruction-architecture\`. Follow the checked-in Spec Kit sequence: specify → clarify → plan → tasks → analyze → implementation → converge. Do not run setup scripts that overwrite existing feature artifacts.
3. Link existing features 001, 006, 010, 016, 018, 019, and 020. Keep their authoritative contracts in place; use the new feature to coordinate changes and evidence.
4. Resolve the documented governance inconsistency: the constitution calls Prospector non-blocking, while current `AGENTS.md` makes it blocking. Retain the stricter operational gate and synchronize the constitution through its amendment procedure.

Required feature artifacts:

- `spec.md`, `plan.md`, `research.md`, `tasks.md`, `quickstart.md`.
- `contracts/architecture.md`, `contracts/output-parity.md`, `contracts/performance.md`.
- `review-inventory.md`, `measured-evidence.md`, `handoff.md`, `lessons-learned.md`.

Every implementation task must contain an ID, requirement/finding link, dependencies, exact source/test paths, intended behavior, validation tier, evidence destination, and completion condition. `handoff.md` records the last completed task, current working-state identity, failed checks, blockers, and exact next command.

## Phase 1 — Complete the repository-wide review and tooling analysis

Use a file inventory plus dependency and caller searches. The inspected checkout currently contains 356 production Python modules and 175 test modules; regenerate counts when implementation starts.

Review these surfaces explicitly:

- CLI and composition roots; generation orchestration and publication.
- DWARF protocols, parsing, type/declarator resolution, definition selection, hierarchy planning, and rendering.
- Source identity, durable caches, locking, atomic publication, and resource ownership.
- Analytical materialization, Parquet schemas/manifests, Doris loading, query batching, hydration, and session caches.
- Assembly discovery, instruction parsing, ABI facts, SDK profiles, object/linker evidence, and optional validation.
- Knowledge export, observability, profiling, history, packaging, containers, documentation tooling, CI, and the nested specification pipeline.

For each module, record its responsibility, dependencies, callers, state/lifetime ownership, relevant tests, review status, and findings. “Reviewed” requires source inspection; a search hit or passing lint is insufficient.

Classify findings as correctness, evidence fidelity, architecture, duplication, performance, or maintainability. Implement substantiated refactorings throughout the repository. Record unsupported proposals as rejected with reasons; record external blockers with an unblock action.

Before selecting new checks:

- Inspect existing architecture, structure, coverage, taxonomy, Ruff, Pyrefly, deptry, Prospector, and workflow enforcement.
- Run exploratory lint with **`--no-fix`** and preserve the normal rule selection when assessing additional rules.
- Separate real design problems from intentional CLI signatures, protocol compatibility, legitimate stdout output, and mutable builders.
- Verify effective Pylint similarity settings before changing thresholds.
- Establish remote evidence before proposing workflow or Dependabot changes, as required by `AGENTS.md`.

**Exit condition:** every inventoried subsystem has an explicit review disposition, and each accepted finding has an executable task and acceptance test.

## Phase 2 — Capture fresh output and performance baselines

Complete this phase before production refactoring.

### Environment and retention

Verify the supplied ELF, promoted store manifest, Doris publication, SDK executables, runtime, and compiler availability. The ELF, manifest, Orbis assembler, and objdump paths from v5 exist; their operational readiness remains to be established.

Do not hard-code Doris container names or ports without inspecting active configuration. Do not reload or rematerialize the complete store merely to establish a baseline.

Retain accepted baselines under:

`D:\ddon-dwarf-reconstructor\output\refactoring-evidence\021\<working-state-id>\`

Keep disposable profiler output in the established OS-local performance location. Use an external history database instead of modifying the already-dirty tracked benchmark ledger.

“Clean output” means a new destination. It does not mean deleting retained caches, resetting Doris, or purging the main analytical store.

### Workload matrix

| Workload | Required output profiles |
|---|---|
| `MtObject` | Headers; assembly/context; assembly/context plus canonical sources and eligible objects; context disabled |
| `rLayout` | Same profiles, with complete dependency closure |
| All 289 Season 2 roots | Same profiles, globally deduplicated |
| Established exhaustive `rAIFSM` control | Existing benchmark configuration, unchanged |
| Knowledge export and nested pipeline | Deterministic fixtures; named real inputs where affected by accepted changes |

Use the canonical `generate` entry point. Record all effective options, including exhaustive search and parameter-name resolution. `--full-hierarchy` currently serves as a compatibility flag; complete dependency closure is already resolved.

“All outputs” means every output supported and eligible under the selected profile. Missing instructions, rejected assembly, unavailable tools, and unsupported methods require explicit status accounting. Generation does not itself establish strict ABI or semantic validation.

### Measurement

Use the existing performance runner, workload contracts, process sampler, and history comparison/export facilities. The current profiling CLI lacks some full-output options; use the existing typed workload/runner interface for those arguments rather than introducing another benchmark framework.

For each baseline/candidate workload:

- Measure three isolated application-cache-cold runs and five fresh-process warm runs, following established benchmarking conventions.
- Record OS and Doris cache state separately; do not describe them as cold unless actually controlled.
- Keep source, toolchain, runtime, sampler, database configuration, workload arguments, and cache preparation comparable.
- Record wall time, CPU, process-tree RSS/VMS, I/O, sample count, timeouts, and output identity.
- Retain raw samples. Label small-sample p95 as exploratory.

First prove repeatability with unchanged code. A baseline that cannot reproduce itself is not ready to judge a refactor.

## Phase 3 — Implement the output-equivalence contract

Extend the existing regression support and publisher tests; keep comparison logic independently testable.

1. Compare the complete relative file inventory, detecting missing, extra, renamed, duplicated, and empty artifacts.
2. Require byte-identical headers and identical header bundle hashes. Preserve qualified names, layouts, inheritance, source locations, CU/DIE provenance, root ownership, ordering, and unresolved/conflict diagnostics.
3. Require identical `.asm` and `.s` bytes for equivalent runs. Verify `.o` reproducibility with the same toolchain before adopting byte equality as its gate.
4. Validate every manifest against its own files before comparing runs. Do not substitute semantic comparison for broken integrity.
5. Compare report and manifest evidence structurally. Allowlist only explicitly identified run metadata demonstrated to vary in unchanged-code repetitions. Never normalize away source identity, candidate selection, evidence status, diagnostics, tool identity, or artifact membership.
6. Verify context-disabled output separately; use the external comparison inventory when the application intentionally omits its manifest.
7. Retain compiler acceptance separately from byte parity. Use established standalone MSVC validation; preserve optional aggregate and Orbis results as distinct evidence.

Comparator tests must detect changed bytes, omitted roots, altered offsets, status downgrades, missing objects, invalid hashes, unexpected JSON fields, and overbroad normalization.

**Gate:** no header difference may be silently accepted or “fixed” by regenerating expectations. An existing output defect requires a separate behavioral-change specification and an explicit acceptance decision.

## Phase 4 — Refactor through independently validated slices

### C++ reconstruction domain

Use one concrete namespace consistently:

- `D:\ddon-dwarf-reconstructor\src\ddon_dwarf_reconstructor\domain\models\cpp_reconstruction\`
- `D:\ddon-dwarf-reconstructor\src\ddon_dwarf_reconstructor\domain\services\cpp_reconstruction\`

Group existing behavior into control-flow, instruction-effects, and ABI responsibilities. Move existing models and algorithms before introducing additional representations. Do not invent a pseudocode generator, recompilation engine, or unused CFG/liveness abstraction.

Move pure analysis from `implementation_parity.py` and `implementation_effects*.py`; retain tool-output parsing and tool-specific syntax handling in infrastructure. Preserve uncertainty, path bounds, unsupported instructions, and evidence dispositions.

Separate `implementation_abi_facts.py` into typed evidence acquisition and pure ABI classification. Keep source/form/CU reference resolution behind existing lookup contracts. Preserve pointer/aggregate distinctions and current failure behavior before considering shared traversal changes.

### Toolchain adapters and application orchestration

Consolidate process execution around [toolchain_process.py](D:/ddon-dwarf-reconstructor/src/ddon_dwarf_reconstructor/infrastructure/toolchain_process.py). Preserve bounded output, finite timeout policy, process cleanup, exit status, chained errors, and invocation provenance.

Use narrow assembler, linker, metadata-reader, and disassembly capabilities where application callers require them. Reuse existing ports first. Avoid a universal compiler service combining unrelated responsibilities.

Introduce typed requests/results for cohesive operations that currently pass loosely related arguments. Construct concrete adapters only in composition roots. Preserve optional strict validation as an independent workflow.

Cache tool identity/version observations within an appropriate run lifetime and key reuse by executable/profile identity. Do not cache failures indefinitely.

### Shared header, analytical, and supporting subsystems

Implement findings from Phase 1 in dependency order, with characterization tests preceding each change. Preserve:

- One source-bound session and canonical definition/type policies.
- Global dependency planning and batched hydration.
- Source/CU/DIE cache identity and bounded query intermediates.
- Producer/serving separation and fail-closed store validation.
- Atomic publication, retained artifacts, and diagnostic fidelity.
- Knowledge-export behavior and nested project boundaries.

Higher RAM usage is acceptable when measured runtime benefits justify it. Avoid repeated hashing, full scans, unnecessary subprocesses, and unbounded caches.

Update internal callers, tests, package exports, documentation discovery, and configuration together. Remove compatibility-only forwarding modules. Preserve intentional public CLI and artifact contracts.

## Phase 5 — Enforce demonstrated architectural rules

Implement enforcement alongside the relevant refactoring slice, not only at the end.

- Extend architecture tests for domain-to-application dependencies, prohibited external execution dependencies, and the actual reconstruction boundaries.
- Preserve empty-selector rejection and deliberate violation controls.
- Use module dependency checks for modules. Use supported banned-API rules or narrowly tested call analysis for functions such as `os.system`; import matching alone cannot establish call-level enforcement.
- Verify adapter contracts through typing and behavioral tests, rather than class-name reflection.
- Require immutability for published value objects where appropriate; permit mutable accumulators, builders, and session caches.
- Update [coverage groups](D:/ddon-dwarf-reconstructor/tests/support/quality/check_coverage.py) for moved and newly covered high-risk modules. Add rejection of accidentally empty groups.
- Introduce additional lint rules in small, reviewed groups. Do not duplicate an argument-count rule in a custom AST checker. Do not interpret comprehension/style rules as measured performance improvements.
- Keep the established structural limits; add no arbitrary lower module target.

Each new check needs a real motivating finding, a passing example, a failing example, a documented exception policy, and integration into the existing local/CI contract.

## Phase 6 — Documentation and Spec Kit convergence

Update documentation throughout implementation, followed by a dedicated consistency pass using the repository’s documentation-writer workflow.

Cover the relevant arc42 building blocks, runtime, crosscutting concepts, decisions, quality, and risks. Use Mermaid/C4 only where the diagram answers a useful architectural question.

Keep Diátaxis purposes separate:

- Explanations describe ownership, dependencies, and design tradeoffs.
- How-to guides describe baseline capture, validation, and benchmarking.
- References describe verified commands, options, artifacts, and statuses.
- Knowledge-base pages preserve measured evidence and uncertainty.

Refresh generated API pages through `docs-api`; do not hand-edit them. Synchronize navigation, roadmap, affected existing specs, README, contributor guidance, and instruction adapters. Run Spec Kit analysis before implementation expansion and convergence before closure.

## Phase 7 — Final regression and performance acceptance

After every coherent slice, run focused tests followed by:

```text
uv run just test-unit
uv run just check
uv run just test
```

Before handoff, also run `coverage-ci` and blocking `audit`; run package/package-smoke for distribution changes. Execute nested `test`, `test-official`, and `check` from their own project boundary when affected.

Coverage acceptance remains **80% total line coverage**, plus **80% line / 70% branch coverage** for required high-risk groups.

Repeat the complete baseline workload matrix. Require:

- Exact header and applicable assembly/object parity.
- Equivalent evidence status, candidate provenance, ownership, and diagnostics.
- Successful integrity checks and retained compiler results.
- No previously available output becoming unavailable or partial.

For each workload/cache-state pair, candidate p50 and sampled p95 must each be **≤110% of baseline**. Do not average improvements across workloads to hide a regression. Treat a noisy threshold crossing as inconclusive; repeat matched measurements with 20 samples per side and retain both rounds.

Report RAM separately. Increased memory alone does not reject a refactor, but paging, instability, or unbounded growth invalidates a claim of acceptable performance.

Unavailable prerequisites remain blocked evidence. Passing fixtures cannot substitute for the requested full-corpus baseline.

## Phase 8 — Lessons learned and agent guidance

Write lessons after acceptance results exist. For every proposed guideline, record the motivating finding, actual change, measured outcome, tradeoff, and deterministic enforcement where available.

Update `AGENTS.md` and applicable adapters with demonstrated guidance on:

- Domain/adaptor ownership and appropriate abstraction boundaries.
- Source-bound cache lifetime and preservation.
- Output-equivalence testing and benchmark interpretation.
- Safe read-only tooling invocation.
- Resumable task/evidence records.

Do not codify speculative rules or findings rejected during the review.

Completion requires accounted-for repository review coverage, completed accepted tasks or explicit external blockers, synchronized documentation/specifications, retained regression/performance evidence, and a handoff that accurately distinguishes verified results from remaining uncertainty.
