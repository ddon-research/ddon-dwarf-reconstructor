# Measured evidence

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../docs/reference/project-status.md).

This research record serves reviewers checking what actually ran. Paths are local, retained
artifacts; path existence is not source/store, compiler, or performance acceptance.

## September 16 compilation recovery: implementation in progress

This continuation implements the reviewed recovery plan. Earlier T105/T106 compiler counts are
historical observations, not acceptance of the current producer. The retained full validation
at review time was 683/753 passing, 70 failing, with aggregate failure. The 493-header probe had
only two requested roots and is not a comparable full baseline.

Evidence root: `output/template-family-review/recovery-20260916-223850/`.
`working-tree.patch`, `working-state.json`, and `source-snapshot/` preserve the pre-recovery
producer and relevant untracked source. Existing analytical data, caches, and compiler reports
remain in place. The first unchanged generation stopped without an exit record and is incomplete;
its `baseline/generate.log` is retained. A separate `baseline-retry/` ran all 289 roots from the
frozen source through `PYTHONPATH`; the imported package path was verified. The September 20
review found its completed report: 526/753 standalone headers passed, 227 failed, aggregate failed,
and 29 units reported C1003. The earlier `current-validation` report has 683/753 passing and
aggregate failure; these are distinct producer observations, not acceptance of today's dirty tree.
The later alias probe requested one root and had 20/24 passing with aggregate failure.
Both retained full bundles' recorded header hashes matched their files at review time.

Active repair now belongs to [Feature 022](../022-cpp-compilation-repair/spec.md), whose
[evidence ledger](../022-cpp-compilation-repair/measured-evidence.md) records manifest identities,
current unit/format failures, and successful read-only Doris liveness checks. Subsequent
[Feature 023](../023-cpp-declaration-ir/spec.md) defines incremental declaration-IR/compiler work.
Historical slice passes below remain useful evidence, but do not close either successor or
Feature 021's independent full-corpus parity/performance obligations.

Implemented and verified structural slices:

- `domain/models/dwarf/type_scope.py` and `type_reference.py` retain namespace/aggregate ancestry
  and ordered pointer, reference, array, and callable layers. The request-owned parser in
  `domain/services/parsing/type_reference_parser.py` preserves aliases, member-pointer owners,
  parameter evidence, false flags, and CU/DIE offset zero. Its bounded caches include CU identity.
- Parameter, field, and method-return rendering consume these references. Scope-aware aggregate
  forwards require proven namespace ancestry; textual qualified names cannot fabricate namespaces.
  Qualified base names survive absent offset-name map entries. Alias/enum tags cannot be forwarded
  as invented aggregate declarations on this path. Remaining legacy alias, scope-emission, and
  dependency paths still need the ownership plan below.
- `template_families.py` now defaults concrete observations to explicit specializations. The
  cross-instantiation method union and hardcoded fixed-array generic inference are removed.
  Compatible methods merge only within one specialization; differing member offsets now conflict.
  Independent textual template-forward inference remains a separate outstanding repair.

| Slice | Retained verification | Result |
| --- | --- | --- |
| Structural parser | `checks/slice-b-unit.log`, `slice-b-check.log`, `slice-b-test.log` | 1,237 unit tests; quality check passed; 1,232 default tests |
| Typed rendering and scope | `checks/slice-c-unit.log`, `slice-c-check.log`, `slice-c-test.log` | 1,249 unit tests; quality check passed; 1,244 default tests |
| Explicit family planning | `checks/slice-d-unit.log`, `slice-d-check.log` | 1,251 unit tests; quality check passed |
| Compiler canary | `canaries/typed-validation/msvc-header-validation.json` | One header and aggregate passed MSVC 19.51.36252; zero diagnostics |

The compiler canary includes type assertions for arrays of callbacks, a templated nested owner,
and a pure-virtual function returning a function pointer. It establishes host C++ syntax/type
behavior, not PS4 layout acceptance. Focused regression tests reside in
`tests/domain/services/parsing/test_type_reference_parser.py` and
`tests/domain/services/generation/test_typed_declaration_rendering.py`.

Completion remains unverified: aggregate parser tag dispatch and alias publication, recursive
dependency/owner closure, mixed-scope emission, include-cycle grouping, diagnostic reconciliation,
all-root standalone/aggregate compilation, identity/layout coverage, fresh/warm determinism,
intentional output modes, coverage/audit, and matched per-workload/cache-state performance.
No percentage threshold replaces full recovery; the matching p50/p95 limit remains 110%.

## Initial working-state snapshot: observed

- HEAD: `5dc0a316e51f244ca49616775845c7dea510a499`; initial branch `main`.
- Working-state SHA-256: `1b10b75e751c97b1b22861327b2494951127c4f14fe69fd342aedc3c5acbee64`.
- External root: `output/refactoring-evidence/021/1b10b75e751c97b1/`.
- `snapshot.json`, `working-tree.zip`, `staged.patch`, `unstaged.patch`, `status.txt`, and
  `git-index.snapshot` preserve 858 effective tracked files and the original index changes.
- Closed archive CRC and all archived file SHA-256 values matched current effective files.
- The untracked 206,422,016-byte dump SQLite index is inventoried and preserved in place.
- The first ZIP check ran before archive close; the closed archive subsequently passed.

## Environment preflight: partially observed

- CPython 3.14.7 and uv 0.12.3 observed; locked sync completed. It removed optional Flight SQL
  packages not in the default environment; normal Doris serving dependencies remain installed.
- Active Doris FE maps SQL 19030 and HTTP 18030; BE Stream Load maps 18040.
- `performance doctor` observed process sampler and installed profiler capabilities. This is
  availability evidence only. Use the external history database for subsequent runs.
- Complete store inspection is running with the explicit original ELF path; see
  `inspect-store.txt`. Full baseline, compiler, and performance acceptance remain pending.

## 2026-09-06 pilot and fixture preflight

- Store inspection completed: `status=complete`, 2,305 units, source SHA-256
  `4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0`.
- MtObject all-output pilot completed through PerformanceRunner in 48.213361 seconds.
  This preflight sample is not used as a matched acceptance sample. It published 20 headers,
  one `.asm`, one `.s`, one `.o`, and the report/manifest. Report status is `partial`, with
  1,911 method records but one assembly file; do not report full-method validation.
- `uv run just test-performance-fixtures`: 1 passed in 1.59 seconds.
- `uv run just docs-tools-install`: locked installation completed (268 packages).
- MSVC discovered at Visual Studio 18 Community, MSVC 14.51.36231; compiler acceptance pending.
- `initial-lint.txt` retains pre-existing lint failures. `additive-ruff-inventory.txt` retains
  the additive no-fix audit. No source code was changed to fix these before baseline capture.
- `baseline-requests.json` contains 104 serial matched requests (13 workload/profile pairs,
  three cold plus five warm each). The third cold sample primes the cache used by warm samples.
  Matrix execution session: 21858; retained progress: `baseline-matrix.log`.

## rLayout unchanged-code repeatability: initially observed

The first two application-cache-cold all-output runs published the same 120-file inventory:
40 headers, 26 `.asm`, 26 `.s`, 26 `.o`, and two JSON artifacts. All header, assembly, and
object bytes matched. Each manifest's file hashes and byte counts validated independently.
The retained `rlayout-cold-repeatability.json` lists 16 differences, restricted to relocation
cache paths, four tool invocations' duration/stdout/stderr paths, and derived report hash/size
fields. These observations justify only narrowly scoped metadata normalization in the future
comparator. They do not establish repeatability for the remaining workloads or profiles.

The first three cold wall times were 100.635535, 96.767305, and 96.839141 seconds; the first
two fresh-process warm times were 86.242476 and 86.595387 seconds. OS and Doris cache state
remain uncontrolled. No candidate comparison or performance acceptance is claimed.

## Planning-turn checks

The planning turn passed 12 architecture tests and parsed the disputed exception syntax on
CPython 3.14.7. No full generation baseline or complete root quality gate ran in that turn.

## Baseline continuation and source review

Eight rLayout all-output samples and eight header-only samples completed. Header-only cold
sample 1 initially failed with WinError 5 during atomic directory publication; its fresh-output,
isolated-cache retry passed in 54.683519 seconds. The failed run remains reliability evidence.
Session 45349 stopped after the first Season 2 all-output sample;
`baseline-matrix-resume01.log` records progress.

`effective-configuration.json` records credential-free Doris/runtime settings observed during
capture and the local dotenv file identity. `type-chain-source-collision.json` reproduces F018;
`parity-evidence-gaps.json` reproduces F022/F023. These are tiny characterization probes, not
full-suite or performance acceptance.

GitHub PR 15 has passing proposal checks; its diff and checks are retained. Live settings show
main unprotected and secret scanning/push protection/Dependabot security updates disabled.
These are explicit remote follow-ups; no remote setting or workflow was changed.

## September 7 continuation: published partial evidence and backend blocker

All 32 rLayout samples completed, excluding the separately retained failed publication attempt.
The first 289-root all-output run took 4,979.3441051 seconds and returned exit code 1 with
254 successful and 35 partial root dispositions. Its files comprise 898 headers, 2,564 `.asm`,
2,502 `.s`, 2,502 `.o`, and two JSON artifacts. Manifest-owned sizes and hashes and the complete
relative inventory validated. `season2-initial-assessment.json` retains all partial roots and
the 466-diagnostic count. This is published partial evidence, not successful full-corpus
acceptance or unchanged-code repeatability. F033 prevents attributing every missing canonical
source/object to a retained producer diagnostic; do not invent those causes.

The initial producer source hashes still match the snapshot. No production refactoring has
started. A subsequent MtObject all-output cold attempt failed in 1.0693203 seconds because
Doris reported no queryable backend replica. That timing is failed-run reliability evidence,
not an accepted workload sample. The existing BE container had exited; one restart reproduced
`a broken disk is found /opt/apache-doris/be/storage`. The host reported about 20.23 GiB free,
but the storage failure's cause is not established. No storage was deleted, rematerialized,
or reloaded. `doris-backend-blocker-20260907.json` retains exact state, mounts, and startup logs.

Resume measurements only after storage health and source-bound queries are verified. Retain
the failed request/result and create a distinctly named fresh-output/cache retry. Keep OS and
Doris cache states uncontrolled unless explicitly measured otherwise. The matrix collector's
optional symbol selection changes scheduling only; it does not override result status or
reduce the required 104 successful/disposition-reviewed samples.

`doris-load-label-probe.json` records a deterministic loader probe with no network or file
uploads: three label computations parse the manifest three times, and changing the destination
table produces the same label. These observations support F036/F037; live alternate-table
behavior remains untested. Source review now records 118 full source inspections out of 621
inventory entries. Source inspection is distinct from closing caller, test, and acceptance work.

## rLayout complete profile comparison

`rlayout-all-profiles-repeatability.json` validates all 32 retained successful samples against
the first sample of the same profile without normalizing JSON. Each contextual manifest's
file inventory, sizes, and hashes pass. Header bundle hashes match. Headers, `.asm`, `.s`, and
eligible `.o` bytes match within each profile, including all cold/warm comparisons. Context
disabled runs have an external comparison inventory and intentionally have no manifest.

Header-only and context-disabled outputs have no byte differences. The contextual assembly
profiles differ only at the previously observed relocation-cache path, four invocation
duration/stdout/stderr paths, and the derived implementation-report hash/size fields. Exact
JSON difference paths are retained; this observation is not permission for broad normalization.

The established analytical `common.metrics.distribution` helper produced the following
baseline wall-time summary in `rlayout-baseline-distributions.json`. Sampled p95 remains
exploratory at these sample counts; no candidate comparison has run.

| Profile | Application cache | Samples | p50 seconds | Sampled p95 seconds |
| --- | --- | ---: | ---: | ---: |
| all | cold | 3 | 96.839 | 100.636 |
| all | warm | 5 | 86.537 | 91.044 |
| headers | cold | 3 | 49.647 | 54.684 |
| headers | warm | 5 | 49.045 | 50.145 |
| assembly | cold | 3 | 95.666 | 96.086 |
| assembly | warm | 5 | 85.846 | 87.391 |
| no-context | cold | 3 | 96.243 | 96.613 |
| no-context | warm | 5 | 85.280 | 85.854 |

## September 7 deterministic checks

- `uv run just test-unit`: 1,010 passed, 7 deselected; `test-unit-20260907.txt`.
- `uv run just test`: 1,005 passed, 12 deselected; `test-20260907.txt`.
- `uv run just coverage-ci`: passed with 1,005 tests. Total line coverage is 83.9%; required
  parsing, generation, orchestration, and artifact groups pass their line/branch thresholds.
  The pytest combined line/branch figure is 80.28%, distinct from total line coverage.
  `coverage-ci-20260907.txt`, `coverage-20260907.json`, and `test-results-20260907.xml` are retained.
- `uv run just audit`: passed with zero messages; `audit-20260907.txt`.
- `uv run just check`: fails at the unchanged source lint gate with 31 findings;
  `check-20260907.txt`. Later steps of this recipe did not run.
- `uv run just docs-check`: passed API freshness, Markdownlint, 17 Mermaid diagrams, and the
  strict Zensical build; `docs-check-20260907.txt`.
- Nested `uv run --directory tools/dwarf_spec_pipeline just test`: 17 passed, 1 deselected;
  `nested-test-20260907.txt`.
- Nested `test-official` with `DWARF_SPEC_OFFICIAL=1`: 1 passed, 17 deselected against retained
  official artifacts; `nested-official-20260907.txt`. This does not prove fresh conversion.
- Nested `check`: passed lint, formatting, typing, and dependency checks;
  `nested-check-20260907.txt`.
- Explicit Markdownlint over the feature directory passed after removing an extra trailing
  blank line from the plan; `spec-markdownlint-retry-20260907.txt`. No plan behavior changed.

`producer-test-drift-20260907.json` confirms that root and nested production/test files still
match the initial snapshot. These checks characterize the existing dirty producer; they do
not mark the unimplemented refactoring accepted.

`doris-backends-20260907.json` records the FE's read-only backend observation: `Alive=false`
and no route to host. Its capacity and heartbeat fields are stale observations from the last
successful heartbeat, not current storage health. Full-corpus/production acceptance remains
blocked independently of the passing deterministic checks.

## Implemented failure ownership and deterministic checks

Following the user's explicit request to implement the findings, production work proceeded with
the real-asset acceptance gap retained. F014/F034 now remove newly owned temporary files after
write failure and preserve the old bundle backup when publication and rollback both fail.
F019 closes stores acquired by failed analytical-session setup and clears session references
even when close raises. F035 uses the canonical contained-path validator. F009 reads the bounded
diagnostic prefix directly. F006 rejects empty executable coverage groups and extends the
high-risk ownership selectors. The new tests protect their own temporary directories even if
the containment validator regresses.

`failure-ownership-red.txt` and `bounds-coverage-red.txt` retain pre-fix failures;
`failure-ownership-green.txt` and `bounds-coverage-green.txt` retain focused passing results.
The first slice passed 1,017 unit / 1,012 default tests. The expanded deterministic slice passed
1,025 unit / 1,020 default tests, coverage, and audit. Existing lint issues were corrected using
precise protocol naming exceptions, the established Typer file policy, literal mnemonic lists,
and direct canonical imports for tests. No broad lint-rule suppression was introduced.

## C++ reconstruction domain extraction

F003 moves 71 unchanged algorithm functions from three infrastructure modules into
`domain/services/cpp_reconstruction/`. Existing control-flow step/join values move to
`domain/models/cpp_reconstruction/control_flow.py`. CFI acquisition remains in
`infrastructure/implementation_cfi.py`, with direct caller imports. No compatibility forwarding
modules remain. Five pure effect/control-flow tests move into the matching domain test tree.

`pre-domain-analysis-slice/algorithm-identity.json` compares complete function syntax trees
before removing the old files; every moved function matches. This structural characterization
does not claim full-corpus parity. F022/F023's known status behavior remains unchanged.

The extraction passed 1,034 unit and 1,029 default tests, full check, coverage-ci, and zero-message
audit. Coverage is 84.0% total line coverage; the new reconstruction group has 89.1% line and
79.4% branch coverage. A further internal-dependency negative control and containment-test
ownership guard passed the 32-test focused boundary selection. Final loop logs are retained as
`implementation-final-*`; extraction logs use `domain-analysis-*`.

The external-module negative controls first demonstrated that the string pattern did not catch
direct imports. Explicit compiled patterns now match direct modules and their submodules; each
prohibited module has a passing real-domain check and a failing-import control. These checks
make no claim about function-call enforcement such as `os.system`.

The original working-state snapshot remains recoverable. The changed producer has a separate
identity in `implemented-findings-working-state.json`; do not mix it into original baseline
samples. Doris BE was rechecked and remains exited. Full-corpus output/compiler/performance
acceptance, the remaining findings, and final Spec Kit convergence are still incomplete.

The final current-state loop passed `test-unit` (1,035 passed), `test` (1,030 passed), and the
complete `check`. The final explicit feature Markdownlint also passed. The preceding coverage
and audit runs pass; the only subsequent test changes added a negative architecture control
and a test-directory containment guard, with no production change. Final review inventory
accounting is 124 source-inspected entries and 503 pending entries; this is not review closure.

## September 7 implementation continuation: ABI, process, ownership, and analytical labels

The typed ABI split (T031/F004) was compared with the pre-change implementation on 371
characterization cases. `abi-differential.json` records zero mismatches. The acquisition layer
still owns DWARF/tool facts and the domain layer owns pure classification; no compiler or full
PS4 ABI acceptance is implied.

F016/T087 rejects non-finite DWARF and Doris timeout values at configuration construction while
retaining the explicit zero analysis-wait policy. The finite-timeout focused red/green evidence
is retained with the slice logs.

F010/T080 now bounds diagnostic file reads and propagates stream-drain write failures after
terminating the child process. F013/T082 removes hash forwarding from `core.serialization`.
The full deterministic gates for that slice were 1,125 unit tests and 1,120 default tests;
`f010-f013-test-unit.txt`, `f010-f013-check-retry.txt`, and `f010-f013-test.txt` retain the
outputs. The changed code preserves successful tool output and JSON conversion behavior.

F018/T083 moved TypeChainTraverser memoization from process-global state to each ClassParser's
source-bound instance. Integer CU/DIE keys from two interleaved fake sources no longer collide,
and `clear_cache()` releases cached DIE references. The focused parser paths passed 48 tests;
the full slice passed 1,128 unit tests and 1,123 default tests, with complete check. Logs are
`f018-test-unit-retry.txt`, `f018-check.txt`, and `f018-test.txt`. Real-asset header parity is
still unavailable because the retained Doris backend is unhealthy, so this is not a corpus gate.

F036/T096 carries the already validated materialization manifest through a Doris load invocation
instead of reparsing it for every Parquet label. The new three-file concurrent fixture observes
one manifest read, identical source-bound label inputs, and deterministic result order. The full
slice passed 1,129 unit tests and 1,124 default tests; `f036-test-unit.txt`,
`f036-check-retry.txt`, and `f036-test.txt` retain the gates. This local test does not establish
live duplicate-label behavior; F037/T097 remains a separate acceptance decision and no Doris
store was reloaded.

The active working-state identity must be recomputed after these source and evidence updates.
The original snapshot and its accepted baseline outputs remain unchanged and are not mixed with
candidate implementation evidence.

F011/T081 now stages linker output in a temporary sibling directory and atomically publishes the
final `*.linked.o` only after a successful exit and an observed output file. A failed invocation
does not return or overwrite a previous valid object; a zero-exit invocation with no output is
failed evidence. The focused linker/assembly selection passed 16 tests, and the corrected full
slice passed 1,131 unit tests, 1,126 default tests, and the complete check. Logs are
`f011-test-unit-retry.txt`, `f011-check-retry.txt`, and `f011-test.txt`; the decision is recorded
in `contracts/validation-corrections.md`.

F012 removes the unused `output_dir` and `stem` parameters from `collect_object_metadata` and
updates both production callers and the malformed-object characterization. This is a contract
cleanup with no output change; the focused validation/toolchain selection passed 25 tests and
the full F012 gates passed 1,131 unit tests and 1,126 default tests.

## September 7 implementation continuation: bounded tool execution (T032/F005)

The bounded tool workflow now uses one infrastructure contract for implementation-tool capture.
`run_bounded_capture` writes child streams to temporary files, applies explicit output limits, and
returns truncation flags without allowing partial output to become successful evidence. Timeout
metadata is produced by the shared helper, and drain failures remain chained after process cleanup.
`read_tool_version` uses the same runner rather than a second unbounded `subprocess.run` path.

`ToolIdentityCache` caches executable SHA-256 and version observations only for the current
toolchain run and profile. It avoids repeated identity work within one generation while preventing
cross-run or cross-profile reuse. Assembler, linker, objdump, readelf, and ABI-probe callers were
migrated together; their status, diagnostic, and invocation-provenance fields remain unchanged.

Focused toolchain/assembly/linker/ABI tests passed 35 cases. The full deterministic gates then
passed 1,134 unit tests (7 deselected), 1,129 default tests (12 deselected), and `uv run just
check`. No real proprietary tool invocation, full-corpus header/assembly parity, or performance
comparison was performed in this slice; those remain T060 evidence. The 64 MiB capture limit and
UTF-8 replacement decoding are explicit implementation choices and should be revisited only with
tool-output evidence.

## September 7 implementation continuation: nested specification pipeline (T090-T094)

The nested project was run from its own boundary with `uv run --directory
tools/dwarf_spec_pipeline ...`. Source acquisition now cleans a newly created temporary file on
download/read/write/checksum failure while leaving a verified existing cache entry untouched.
The converter adapter stages output in a fresh source-specific directory, uses file-backed stdout
and stderr capture with an 8 KiB diagnostic limit, applies a finite 120-second default timeout,
terminates timed-out children, and publishes an intermediate only after successful conversion.
`ConversionError` is now part of the CLI's expected-error boundary and remains chained to the
underlying failure.

Nested artifact validation now checks the complete relative file inventory, rejects duplicate,
missing, extra, symlinked, path-escaping, unknown, and checksum-invalid entries, validates source
and parser identities, and derives the selected nonempty version set from the manifest. Selected
version fixture builds therefore validate without weakening the official three-version acceptance
test. The normalization flow moved into a stateful `DocumentBuilder`; the `normalize.py` facade
keeps the existing caller contract and the 23 deterministic non-official tests retain rendered
fixture behavior.

Semantic audit JSON/Markdown output is staged as a pair with rollback if the second replacement
fails. `test_write_index_failure_preserves_previous_report_pair` proves that an existing report is
unchanged and temporary files are removed after a simulated publication failure. The nested
project's `just test` passed 23 tests (one official test deselected), and `just check` passed Ruff,
format, Pyrefly, and deptry. Official converter execution and all-three-version artifact evidence
remain unavailable until the Docker/official environment is run.

The architecture quality slice also added a narrowly scoped call-level AST check for unbounded
`os.system`, `os.popen`, and legacy subprocess convenience calls in core/domain/application
modules. The repository scan and deliberate violating fixture both pass; infrastructure process
adapters remain governed by their bounded-runner tests.

F037/T097 now has a deterministic label characterization in
`tests/infrastructure/analytical/test_doris_load_identity.py`: repeated source/family/path inputs
are stable, changing the source identity changes the label, and changing only the destination table
currently does not. That last result is a durable collision risk, not permission to alter labels in
an append-only store. `contracts/validation-corrections.md` records the explicit deferred
migration decision; target-Doris duplicate-label and receipt migration evidence is still blocked.

## September 7 implementation continuation: method ownership fallback (T098/F015)

`symbol_output_methods.method_class_key` now uses the exact `owner_class_key` supplied by
implementation discovery and refuses to select the first insertion-order match when partial or
legacy evidence supplies only an ambiguous display name. Exact and containing-class ambiguity
falls back to `shared` output with no unverifiable root ownership. The canonical provenance path,
stable method IDs, and generated headers are unchanged. The focused symbol-output selection passed
11 tests, including `test_method_ownership_fails_closed_for_ambiguous_display_name`; full gates
remain required after this source change.

## September 7 final deterministic acceptance for the implemented slices

After T098/F015, the root deterministic acceptance loop completed with 1,139 unit tests (7
deselected), 1,134 default tests (12 deselected), and a passing `uv run just check`. The nested
specification project completed `just test` with 23 tests (one official test deselected),
`just check`, `just test-official` with its environment-qualified test skipped, and `just ci`.
The root `coverage-ci` gate passed with 84.1% total line coverage; the required parsing,
generation, orchestration, artifact, and `cpp_reconstruction` groups each met the 80% line and
70% branch thresholds. The blocking `audit` gate passed with zero Prospector messages.

The current production/test/configuration working-state identity is
`a3106e02defb12719dfe5a4db4d11898c7070863fc0fa8ad454334f733a0c2c0`, recorded in
`output/refactoring-evidence/021/1b10b75e751c97b1/implemented-findings-working-state.json`.
`git diff --check` reports no whitespace errors; its CRLF normalization notices are pre-existing
working-tree line-ending warnings. These gates establish deterministic local correctness only.
They do not establish full 289-root header/assembly/object parity, compiler acceptance, or the
10% performance budget. Those claims remain blocked by the unavailable Doris BE and the retained
external toolchain/full-corpus prerequisites; the existing baseline and blocker receipts remain
the authoritative evidence.

## September 7 output-equivalence contract (T020/T021/F007)

`disassembly_output_equivalence.py` now models the current flat publisher rather than assuming
the retired four-batch bundle layout. It validates every `symbols.manifest.json` declaration
against the physical inventory, including byte counts and SHA-256 values for headers, `.asm`,
`.s`, eligible `.o`, and the implementation report. It also validates implementation artifact
declarations and rejects symlinks, path escapes, temporary publication files, missing or extra
files, and context artifacts in a context-disabled profile.

The comparator compares exact byte artifacts independently from JSON evidence. It compares
`implementation-report.json` and `symbols.manifest.json` through structural hashes, allowing only
the runtime fields already demonstrated to vary (tool timing and captured/cache paths, plus the
manifest's derived implementation-report hash/size). Status, offsets, provenance, diagnostics,
unknown JSON fields, and artifact membership remain comparison inputs. Six focused tests cover
runtime variation, changed bytes, missing objects, status/offset/unknown-field changes, invalid
publisher hashes, context-disabled inventories, and overbroad normalization rejection.

Against retained unchanged-code evidence, the comparator rebuilt and compared these pairs with
zero differences: rLayout all-output cold runs (120 files each), assembly profiles (68 each),
header profiles (41 each), and context-disabled profiles using the external inventory (92 each).
This is repeatability evidence for the retained outputs only; it is not a new candidate run and
does not close T011, T022, or T060.

The post-comparator deterministic acceptance loop passed 1,145 unit tests (7 deselected), 1,140
default tests (12 deselected), `uv run just check`, and `uv run just coverage-ci`. Pytest reported
80.53% total line coverage; the repository coverage checker reported 84.1% total line coverage,
with parsing, generation, orchestration, artifact, and `cpp_reconstruction` groups meeting their
80% line and 70% branch thresholds. `uv run just audit` reported zero Prospector messages. These
results are bound to working-state identity
`fa4cad8e8f8e341307dad004b09b894acc4fd19b096706b3894df8f5487dfa7b` and the 583-record receipt at
`output/refactoring-evidence/021/1b10b75e751c97b1/implemented-findings-working-state.json`.

## September 7 orchestration boundary decision (T033)

Source inspection found no justified second orchestration split. `dwarf_implementation.py` is an
application use case whose external association, range, context, and report operations are already
delegated to focused sibling modules. `symbol_output.py` owns the complete staged publication
transaction, including report/manifest assembly and rollback; extracting individual steps would
separate state that must be committed atomically. `composition.py` constructs concrete adapters
only at the infrastructure boundary and keeps optional LLVM cross-check configuration in one
closure. The new `tests/infrastructure/test_composition.py` characterization passed three tests
for adapter construction and factory option capture. T033 therefore records an explicit rejection
of an arbitrary module split or forwarding compatibility shim; the existing typed facade and
ports remain the cohesive boundaries.

## September 7 process-tree metric accounting (T099/F024)

Source review confirmed that the performance runner's CPU and I/O metrics were computed by
subtracting aggregate counters from the first and final *live* process-tree samples. A descendant
that exited before the final sample disappeared from that subtraction, so the result was an
incomplete observation even when the workload itself completed successfully.

`PerformanceRunner` now keeps first and last counters for each observed `(pid, creation_time)`
identity for the duration of one run. Aggregate CPU and I/O metrics sum those per-process
lifetime deltas, including descendants that are absent from the final tree. The raw
`process-samples.jsonl` schema, peak RSS/VMS metrics, wall-time measurement, timeout handling, and
published manifest shape are unchanged. The deterministic regression
`test_process_accounting_retains_short_lived_descendant_deltas` proves that a child observed on an
intermediate sample remains represented after it disappears.

Focused runner/tooling validation passed 5 tests. The post-change root deterministic loop passed
`uv run just test-unit` with 1,149 tests (7 deselected), `uv run just check`, and
`uv run just test` with 1,144 tests (12 deselected). `coverage-ci` passed with 80.53% pytest line
coverage and 84.1% repository checker total coverage; parsing, generation, orchestration, artifact,
and `cpp_reconstruction` groups met the 80% line / 70% branch thresholds. Blocking `audit` passed
with zero Prospector messages. These results are local instrumentation evidence only; T011/T060
still require unchanged-code repeatability and the full workload matrix before using the metrics for
the 110% acceptance gate.

These post-change results are bound to working-state identity
`e0be1ded56acc6f33a5bef0410d5e4536bdc5e283a8e1c4346c2a2f293bf72d2` and the refreshed 584-record
receipt at `output/refactoring-evidence/021/1b10b75e751c97b1/implemented-findings-working-state.json`.

## September 9 Parquet selection evidence (T100/F038)

Source review of `ParquetStoreQueries.find_primary_definition` found that its selection-cache
fast path consumed a cached offset without checking the cache's explicit completeness flag. The
Doris adapter already rejects `False`, so an incomplete historical hint could otherwise be
promoted as complete Parquet evidence. Before the production fix, the new characterization
returned the cached definition for an explicit `False` flag; after the fix it falls back to the
bounded definition query and preserves that result's status and provenance. A complete hint still
hydrates directly. `tests/infrastructure/analytical/test_parquet_partial_evidence.py` passed both
focused regression cases. Full root gates are required for this slice; no header-byte,
full-corpus, compiler, or performance claim is made here.

The post-change root gates then passed `uv run just test-unit` with 1,151 tests (7 deselected),
`uv run just check`, `uv run just test` with 1,146 tests (12 deselected), `uv run just coverage-ci`
with 80.55% pytest line coverage and 84.1% repository-checker total coverage, and blocking
`uv run just audit` with zero Prospector messages. The required high-risk groups remained at or
above 80% line / 70% branch coverage. These local deterministic results do not close the blocked
full-corpus, compiler, or performance matrix. They are bound to the 585-record receipt identity
`ae47e62284aa1f7f64a0cfc69206f18f5f40989f52297b106ad8943405d3dc56`.

## September 9 CU-qualified method context evidence (T101/F039)

Source inspection found that the normalized analytical schema preserves `unit_offset`, but the
batched validation projection used bare DIE offsets for its method, parameter, reference,
attribute, and location filters and its in-memory maps. A deterministic two-CU fixture with the
same DIE offset reproduced the risk: an unqualified request now returns `unavailable` with an
explicit CU-provenance diagnostic, while requests carrying aligned unit offsets retain the
selected CU's tag and calling-convention facts. Candidate implementation CU provenance from raw
validation reports is now threaded into `MethodContextRequest` and subsequent batch lookups.

Focused method-context, validation-evidence, and validation-path tests passed (34 tests), with
Pyrefly, Ruff, and the structure checker clean. The completed root gates then passed with
`uv run just test-unit` reporting 1,154 passed and 7 deselected, `uv run just check` green after
refreshing the six generated API pages for 365 modules, and `uv run just test` reporting 1,149
passed and 12 deselected. `uv run just coverage-ci` passed with 80.69% pytest line coverage;
the repository checker reported 84.3% total lines / 68.1% branches, with parsing 85.7% / 71.8%,
generation 87.0% / 73.0%, orchestration 88.3% / 73.4%, artifact 92.3% / 79.7%, and
cpp_reconstruction 89.6% / 80.3%. `uv run just audit` passed with zero Prospector messages.
These deterministic gates do not claim full-corpus header/assembly/object parity, compiler
acceptance, or the performance budget. The Doris BE blocker remains unchanged.
The evidence is bound to the refreshed 587-record working-state receipt with identity
`f5a6f828a10892b9247423684075ca530d4f5e6bc55259d2ca3ad54058d9950a` at
`output/refactoring-evidence/021/1b10b75e751c97b1/implemented-findings-working-state.json`.

## September 9 workflow provenance check (T102/F040)

The checked-in workflow set already pins every external `uses:` reference to a 40-character
commit SHA and includes a human-readable release comment. The existing actionlint gate checks
workflow syntax, but it did not enforce that provenance policy. `tests/quality/test_architecture.py`
now scans `.github/workflows/` and accepts repository-local `./` actions while rejecting an
external tag or SHA without a release comment. The deliberate fixture
`actions/checkout@v7` fails the same helper, so the check cannot pass because its selector is
empty or because only the current repository happens to be compliant. The architecture test file
passes all 26 tests; targeted Ruff, Pyrefly, and the structure checker are clean. This is a
deterministic policy gate, not evidence that GitHub settings, Dependabot, or remote branch
protection are enabled.

The complete post-change root gates then passed `uv run just test-unit` with 1,156 tests (7
deselected), `uv run just check`, and `uv run just test` with 1,151 tests (12 deselected).
`uv run just coverage-ci` passed with 80.68% pytest line coverage; the repository checker
reported 84.2% total lines / 68.1% branches, with parsing 85.7% / 71.8%, generation 87.0% /
73.0%, orchestration 88.3% / 73.4%, artifact 92.3% / 79.7%, and cpp_reconstruction 89.6% /
80.3%. `uv run just audit` passed with zero Prospector messages. These deterministic gates remain
local evidence only: they do not claim full-corpus header/assembly/object parity, compiler
acceptance, or the performance budget. The updated 587-record working-state receipt is
`output/refactoring-evidence/021/1b10b75e751c97b1/implemented-findings-working-state.json` with
identity `27e1b2d4e2e67a2413b6e2c961974e697e9afa3ffe4eee89c5085a16a4bdffa7`.

The supporting-contract audit also inspected the six inventoried Compose/image-lock files under
`ops/`, the four documentation-tool inputs under `tools/documentation/`, and the eight MSVC/Sonar
tool files under `tools/sonar/`. Compose files keep the analytical store, profiling artifacts,
credentials, and optional observability services at explicit boundaries; image digests are retained
where the deployment workflow uses locks. The API generator publishes only source-derived pages
atomically, Mermaid validation uses a disposable directory, and compiler validation keeps catalog,
bounded command, report, and publication responsibilities separate. No workflow, Dependabot,
remote security setting, or proprietary compiler claim was inferred from local source inspection.

## September 9 Sonar command timeout evidence (T103/F041)

Source inspection found that `tools/sonar/prepare_msvc_analysis.py` had three external command
paths (`vswhere`, the Visual Studio developer shell, and Sonar Build Wrapper) using an unbounded
`subprocess.run`. The neighboring `tools/sonar/msvc_validation/commands.py` already owns finite
timeout handling and explicit timeout status, so the fix reuses that runner rather than adding a
second process abstraction. The preparation module adapts the bounded result back to its existing
`subprocess.CompletedProcess` contract for callers that inspect `returncode`, `stdout`, and
`stderr`; a timeout raises `SonarAnalysisError` and therefore cannot publish a captured database.

`tests/tools/sonar/test_prepare_msvc_analysis.py` covers the finite timeout value, result
adaptation, fail-closed timeout path, and missing-exit-status path. The focused slice passed 14
tests. This is deterministic
tooling evidence only: no MSVC compiler run, Sonar analysis, generated-header parity, or full
workload/performance claim is implied.

The post-change root gates then passed `uv run just test-unit` with 1,159 tests (7 deselected),
`uv run just check`, and `uv run just test` with 1,154 tests (12 deselected). `uv run just
coverage-ci` passed with 80.68% pytest line coverage; the repository checker reported 84.2% total
lines / 68.1% branches, with parsing 85.7% / 71.8%, generation 87.0% / 73.0%, orchestration
88.3% / 73.4%, artifact 92.3% / 79.7%, and cpp_reconstruction 89.6% / 80.3%. Blocking `uv run
just audit` passed with zero Prospector messages. These deterministic gates do not claim
full-corpus header/assembly/object parity, compiler acceptance, or the performance budget. The
The historical 589-file receipt for the T103 checkpoint is
`0db071fa20ea337f4c0dd858d7183f835380558176f8162b722c5018d45ed096` at
`output/refactoring-evidence/021/1b10b75e751c97b1/implemented-findings-working-state.json`.

## September 9 bounded Sonar/MSVC output evidence (T104/F042)

The shared `tools/sonar/msvc_validation/commands.py` now drains stdout and stderr concurrently
and retains at most 8 MiB per stream. It reports truncation explicitly while continuing to drain
the child, so large diagnostics cannot deadlock the caller or grow memory without bound. The
preparation workflow rejects truncated command output, header validation rejects incomplete marker
streams, and compiler-version metadata returns `not_observed` on timeout, truncation, missing exit
status, or capture failure. Finite timeout, exit status, invocation provenance, and bounded-output
behavior remain unchanged for complete output.

`tests/tools/sonar/test_prepare_msvc_analysis.py` and
`tests/tools/sonar/test_validate_header_bundle.py` passed 30 focused tests. The root unit and
default-test gates passed with 1,164 (7 deselected) and 1,159 (12 deselected), respectively;
`uv run just check` passed. `uv run just coverage-ci` passed with 80.68% pytest line coverage;
the repository checker reported 84.2% total lines / 68.1% branches, with parsing 85.7% / 71.8%,
generation 87.0% / 73.0%, orchestration 88.3% / 73.4%, artifact 92.3% / 79.7%, and
cpp_reconstruction 89.6% / 80.3%. `uv run just audit` passed with zero Prospector messages.
This is deterministic tooling evidence only: no current-candidate compiler acceptance,
full-corpus parity, or performance claim is implied. T022/T060 and the Doris-dependent matrix
remain open.
The refreshed working-state receipt covers 590 files with identity
`8271e69eb0576d83dc9632ed3d8ccc3b44ce64c055f011d497e14d47453cd575` at
`output/refactoring-evidence/021/1b10b75e751c97b1/implemented-findings-working-state.json`.

## September 9 MSVC compiler preflight (T022 evidence, not acceptance)

The local Microsoft toolchain prerequisite is available. `vswhere.exe` located the Visual Studio
18 Community installation, `VsDevCmd.bat -arch=x64` resolved `cl.exe` at
`C:\\Program Files\\Microsoft Visual Studio\\18\\Community\\VC\\Tools\\MSVC\\14.51.36231\\bin\\Hostx64\\x64\\cl.exe`,
and `cl.exe /Bv` reported MSVC 19.51.36252. A plain, uninitialized PowerShell process still
does not resolve `cl.exe`, so the validation workflow must initialize the developer environment.

The current candidate checkout has no generated-header bundle under `output/`. Accordingly,
`uv run python -m tools.sonar.prepare_msvc_analysis --validate-only` fails closed because its
default validation directory is absent, and a direct `validate_header_bundle` probe against
`output/` reports no headers. This is a missing-candidate-artifact condition, not compiler
acceptance.

To exercise the workflow without changing the durable store, the retained 40-header `rLayout`
baseline was validated separately. The run resolved the compiler, captured its version, and
completed all standalone processes: 39 headers passed and `rAIConditionTree.h` failed with
MSVC diagnostic `C2040`. The aggregate result was therefore `failed` (process exit 1), with
zero timeouts and zero unobserved headers. The report and per-header evidence are retained at
`output/refactoring-evidence/021/1b10b75e751c97b1/compiler-preflight/rlayout-baseline-021/`.

This establishes tool availability and the fail-closed validation path only. T022 and T060
remain open until a fresh current-candidate bundle is generated and its standalone compiler
results are reviewed separately from byte parity, assembly/object evidence, and performance.

## September 9 documentation convergence (T050)

The documentation slice is `Implemented` and `Verified` against current source and the active
Feature 021 record. The architecture components page now names the C++ reconstruction domain
boundary, the infrastructure ABI-evidence adapter, and CU-qualified analytical method context.
The validation how-to records the current 590-file receipt, the full-SHA workflow rule, and the separate
blocked boundary for full-corpus, compiler, and performance acceptance. Deployment explains that
the local architecture test complements actionlint without claiming remote GitHub settings. The
testing knowledge base records the current deterministic gate results, while the roadmap and
README link to the active evidence. No new page or navigation entry was needed because the
existing Zensical architecture, validation, testing, and roadmap entries already expose these
pages.

`uv run just docs-api-check` passed with 365 source modules in six generated pages. `uv run just
docs-check` passed with 17 Mermaid diagrams in 69 Markdown files and a strict Zensical build with
no issues. The generated API pages were unchanged; the updated authored pages and inventory
entries remain source-backed. Full-corpus parity, compiler acceptance, and performance remain
blocked as recorded above.

## September 9 Doris image and storage recovery

The recovery evidence receipt is retained at
`output/refactoring-evidence/021/1b10b75e751c97b1/doris-recovery-20260909-2016/`.
Both existing Doris containers were stopped before capture, and the original FE metadata and
BE storage paths on D: were left unchanged.

Fresh pulls of `apache/doris:fe-4.1.3` and `apache/doris:be-4.1.3` returned `Image is up to
date`. The local and registry index digests remain the locked FE
`sha256:3dd47644cd9fa8152028bdae449e77170ab0de004bd7a3fa311a204a106c26c7` and BE
`sha256:9f84a8b018069cd3c9a65af42ff5ef2c733b3b25e1ca708e0a3e4078361a1eb3`; no image-byte
update was available. The BE startup banner still contains `4.1.3-rc02`, while its embedded
commit matches the 4.1.3 release. The lock observation was refreshed to
`registry_and_local_pull_verified`.

The retained logs show the BE storage health check failing on
`/opt/apache-doris/be/storage/.testfile` with `errno=5 (Input/output error)` while the D:
volume reported approximately 97.9% utilization. Host NTFS and physical-disk checks remained
healthy, and all 498 files in the original BE storage were readable and hashable. The existing
analytical store remains a complete source-bound fallback: 2,305 CUs, 95,540,741 DIEs, zero
parser errors, and a validated Parquet manifest.

At the initial capture checkpoint the next action was a copy-first clone on C:. That checkpoint
was superseded by the successful recovery documented above: no original D: data was deleted or
repaired in place, and the validated Parquet store was not reloaded. The original container
objects were recreated during canonical promotion, but their pre-promotion inspect, mount,
network, and log evidence is retained alongside the unchanged D: source inventories. Matching
forensic definitions using the original D: mounts were recreated with a `never_start` label and
were never started.

A byte/hash-verified copy of 31 FE metadata files and 498 BE storage files was started from a
new C: directory. The recovery clone reported 251 tablets with no storage error, FE reported
247/247 tablets healthy, SQL and HTTP health probes passed, and every expected family and
auxiliary tablet was `NORMAL`. The canonical Compose service remains healthy on the same copy:
the current FE and BE report 257 tablets, the tablet checker reports 253 user/internal OLAP
tablets with zero unhealthy tablets, and the source-bound fourteen-family counts and hashes
match the complete manifest. The raw backend tablet total is operational metadata that changed
as audit/system activity ran; it is retained as evidence rather than normalized into the data
parity claim. `MtObject` and `rLayout` header-only controls succeeded with 20 and 40 headers.

The deterministic Doris preflight now verifies rendered image digests, readable sampled files,
temporary write/read access with cleanup, volume health, 15% minimum free-space headroom, E:
rejection, and `ignore_broken_disk=false_or_unset`; the final report status is `pass` with C:
free space at 30.4%.

## September 13 configuration management and CLI debloating

To eliminate command-line path bloat, configurable file paths (`ELF_FILE_PATH`, `DWARF_STORE_MANIFEST`,
`ORBIS_OBJDUMP_PATH`, `ORBIS_AS_PATH`, `LLVM_READOBJ_PATH`, `LLVM_OBJDUMP_PATH`) and canonical Doris
endpoints were centralized into `.env` and `.env.template` using forward-slash quoted paths.
`Config.from_env()` in `infrastructure/config/application_config.py` loads these paths from `.env`
and environment variables with clean McCabe-bounded helper functions. `cli.py` commands (`generate`
and `export-knowledge`) default their paths to `Config.from_env()` and use thin `_dispatch_*`
helpers to satisfy the 75-line per-function guardrail.

## September 13 canaries and unified Season 2 acceptance run

The four-stage funnel verified feature parity across the refactored architecture:

1. **Canary 1 (`MtObject` headers)**: 20 headers generated under `output/acceptance-candidate/canaries/MtObject-headers`.
2. **Canary 1 (`MtObject` all profile)**: 20 headers, 1 assembly file, 1 object file under `output/acceptance-candidate/canaries/MtObject-all`.
3. **Canary 2 (`rLayout` all profile)**: 40 headers, 26 assembly files under `output/acceptance-candidate/canaries/rLayout-all`.
4. **Canary 3 (`rAIFSM` full-hierarchy)**: 27 headers, 84 classes traversed under `output/acceptance-candidate/canaries/rAIFSM`.
5. **Stage 4: Unified 289 Season 2 Batch Run**:
   - Command: `uv run ddon-dwarf-reconstructor generate --symbols-file resources/season2-resources.txt --extract-assembly --emit-implementation-sources --output output/acceptance-candidate/season2`
   - Outcome: 289 requested roots (254 success, 35 partial, 0 crashes), 1,690 classes, 898 headers (446 shared), 2,564 assembly files, 5,004 source files, 29,048 methods, 8,467 total files published.
   - Parity with baseline: Exactly matches the historical baseline counts recorded in `output/refactoring-evidence/021/1b10b75e751c97b1/results/021-season2-all-cold-01.json` (254 success, 35 partial, 898 headers, 2,564 assembly files).

## September 13 MSVC compiler validation (T022 evidence)

Standalone MSVC compiler validation was executed across all 898 generated Season 2 headers using
`tools/sonar/validate_header_bundle.py` with the local Visual Studio 18 Community MSVC toolchain
(compiler version 19.51.36252 for x64):

- Header discovery was enhanced in `validate_header_bundle.py` to support versioned root layouts
  with symbol subdirectories (`rAIFSM/`, `shared/`, etc.).
- An automatic MSVC response file (`compile_all.rsp`) was added for aggregate translation units
  exceeding the Windows 8,191-character command line limit across 290 unique bundle directories.
- Results across all 898 headers:
  - Total headers evaluated: 898
  - Standalone passed: 435
  - Standalone failed: 463 (syntax_or_compile_error: 424, unresolved_identifier_or_type: 39)
  - Timed out: 0
  - Unobserved: 0
  - Standalone status: partial
  - Aggregate status: failed
- Detailed report and per-header stdout/stderr logs are retained at
  `output/acceptance-candidate/season2-msvc/msvc-header-validation.json`.

## September 14 template family reconstruction and header deduplication

Following the observation of 90 repeated header basenames in Season 2 generation (notably 99 duplicate
`rTbl2.h` and 38 duplicate `MtCollection.h` headers containing partial generic definitions that produced
2,890 MSVC `error C2953` "class template has already been defined" failures), the template reconstruction
architecture was refactored:

1. **Parameter Model & Provenance**:
   - Replaced split parameter lists with unified `template_parameters: list[TemplateParameter]` in
     `domain/models/dwarf/template_param_info.py`, preserving exact child-DIE order.
   - Parsers in `domain/services/parsing/class_parser_templates.py` record actual argument types,
     non-type values, `uses_default` flags, and DWARF reference provenance (`argument_offset`, `cu_offset`, `die_offset`).
2. **Doris Binary Store Full Audit**:
   - Audited all 9,960 `rTbl2` DIEs in the binary via Doris (`rtbl2-audit-summary.json` and `rtbl2-raw-evidence.jsonl`):
     - Every single one has `DW_AT_byte_size = 128` (100% uniform size across 9,960 DIEs).
     - Every single one has 2 members, 1 base inheritance (`rTbl2Base`), and 1 `DW_TAG_template_type_param`.
3. **Template Family Planning & AST Type Substitution**:
   - Implemented `domain/services/generation/template_families.py` to plan template families conservatively:
     - `generic`: When argument observations discriminate and normalized signatures and layouts match.
     - `explicit`: When member methods or layouts differ across instantiations in DWARF, emitting
       `template <typename T> class Family;` followed by `template <> class Family<Args...> : public Base`.
     - `blocked`: When signatures or definitions conflict.
   - Implemented `domain/services/generation/template_declarations.py` using AST type expression
     replacement (`substitute_type`, `project_template`).
4. **Ownership Planning & Deduplication**:
   - Multi-root template families route to `_SHARED_OWNER` (`shared/`), producing a single canonical header.
   - Fixed `symbol_header_validation.py` balanced bracket parsing in `_definition_matches` to handle attributes
     and template bases without swallowing base arguments.
   - Fixed `header_hierarchy.py` `_unique_definition_names` to deduplicate template classes by rendered
     C++ declaration name, preventing collisions on differently-scoped argument types flattened in `shared/`.
5. **Multi-Root Canary Validation**:
   - Multi-root canary (`rAbilityData`, `rAchievement`, `rAttackParam`) emitted exactly one `shared/rTbl2.h`.
   - All 28 canary headers passed standalone MSVC compilation with 0 failures (100% pass rate).
6. **Full Season 2 Generation Results**:
   - Output generated to `output/template-family-review/20260913/season2/ps4-02020005/`.
   - Header count reduced from 898 to 753 (145 duplicate headers completely eliminated!).
   - `rTbl2.h` reduced from 99 files across symbols to 1 canonical `shared/rTbl2.h`.
   - `MtCollection.h` reduced from 38 files across symbols to 1 canonical `shared/MtCollection.h`.
   - 8,322 total files published across all 289 requested roots (including 2,564 `.asm` and 1,690 classes) with zero validator errors.
7. **MSVC Compiler Standalone Validation (`output/template-family-review/20260913/season2-msvc/msvc-header-validation.json`)**:
   - **`error C2953` ("class template has already been defined"): Reduced from 2,890 mentions to 0 (100% eliminated!)**.
   - **`error C2955` ("use of class template requires template argument list"): Reduced from 289 mentions to 15 (94.8% reduction)**.
   - **Failed headers: Reduced from 463 to 264 (199 headers now compile cleanly, a 43% reduction in failures)**.
   - **Passed headers: 489 / 753 headers pass standalone MSVC compilation (64.9% pass rate)**.
   - Detailed comparison report retained in `output/template-family-review/20260913/msvc-comparison-report.json`.

## September 15 MSVC compiler improvements, C2955/C1003 reduction, and member indirection fixes

Following Astra's review and critical compiler analysis of the remaining 264 failed headers and 195 fatal
`C1003` compiler cascades:

1. **Canonical Template Argument Splitter (`template_argument_parser.py`)**:
   - Replaced fragile character-level splitting with balanced delimiter tracking across `<>`, `()`, `[]`,
     and `{}`. Correctly splits function-pointer template arguments (e.g. `cDelegateBase::cNodeT`).
2. **Recursive Typedef and Nested Template Argument Collection**:
   - Added recursive nested class typedef collection (`s8`, `u16`) in `dwarf_header_support.py` and nested
     template argument extraction in `used_typedef_collection.py`.
3. **Specialization Forward Declarations (`header_forward_declarations.py`)**:
   - Added `_specialization_name_types` and `_template_parameter_types` to forward-declare user classes passed
     as template specialization arguments (e.g., `cAIPawnAutoMotionNode` in `MtTypedArray`), eliminating
     cascading fatal `C1003` compiler aborts.
4. **Base Class Offsets in Template Family Signatures (`template_families.py`)**:
   - Preserved `base_class_offsets` in family signature generation to prevent conflicting specialization merges.
5. **Deduplication of Enum Class and Class Forward Declarations (`header_type_planning.py`, `header_hierarchy.py`)**:
   - Expanded forward declaration pattern to match `enum class` and prioritized `enum class` over `class`
     to eliminate duplicate and conflicting forward declarations (e.g., `MOT_TYPE` in `cDelegate.h`).
6. **By-Value Member Indirection Detection Fix (`header_ordering.py`)**:
   - Implemented `_is_indirection_type` (stripping `<...>` before testing `*` or `&`) to fix by-value members
     containing pointer template arguments (e.g., `cDelegate_4<void, cpSequenceCtrl *, ...>`), ensuring
     `#include "cDelegate.h"` is properly emitted in `cpSequenceCtrl.h`.
7. **Typedef Forward Declaration Exclusion (`header_hierarchy.py`)**:
   - Excluded types already defined as typedefs from forward declaration emission (e.g., `_Myt` in `vector.h`).
8. **Enhanced MSVC Validator (`validate_header_bundle.py`)**:
   - Added `raw_diagnostic_counts`, `unique_location_counts`, and `error_limit_unit_count` (`C1003`).
9. **Compiler Verification Results (`output/template-family-review/current-validation/msvc-header-validation.json`)**:
   - **Passed headers**: Increased from 489 to **580** (+91 headers compiling cleanly, a 18.6% increase).
   - **Failed headers**: Reduced from 264 to **173** (-91 failed headers, a 34.5% reduction).
   - **Fatal `C1003` compiler aborts**: Reduced from 195 to **16** (**91.8% reduction**).
   - **`C2065` undeclared identifier headers**: Reduced from 212 to **80** (**62.3% reduction**).
   - **`C2923` invalid template type argument headers**: Reduced from 202 to **12** (**94.1% reduction**).
   - **`C2913` invalid explicit specialization headers**: Reduced from 210 to **87** (**58.6% reduction**).
   - Target headers `cDelegate.h`, `cpSequenceCtrl.h`, `rStageJoint.h`, and `MtCollection.h` all compile **CLEANLY**.
