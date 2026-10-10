# Measured evidence: Compilation repair

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../docs/reference/project-status.md).

## Retirement snapshot: October 10, 2026

Commit `f0cb1af34f729ba7abfb7019bf7a4303c8a20bec` preserves the unfinished implementation
as-is. Feature 022 is retired with incomplete acceptance. The v15 compiler observations below
precede the final method-template changes; no new 289-root compiler, semantic, ABI, or performance
acceptance was attempted for retirement. The [final status record](../../docs/reference/project-status.md)
records fresh recipe failures and passing documentation/audit checks without changing task checks.

## T011 source-bound primary-template feasibility: September 26

An explicit, bounded Doris query found 28,837 `cArray<...>` name-index rows and 252
distinct spellings for source SHA-256 `4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0`.
The external research script and report are under `output/compilation-repair-022/t011-20260926/`.
`carray-family-complete-evidence.json` (SHA-256
`eb78713315b7e44b6bc23f71b310d77d14bf2cf0d3d93f4195e2bfba1e6ba33c`) contains one
complete CU/DIE-bound representative for **all 252** spellings. Each reports
`nDDOUtility.h:493`, two parameters (`typename T`, `unsigned int N`), one `elems` member at
offset zero, no bases or nested classes, and a member-array extent equal to `N`. For 193
representatives the member's terminal type DIE directly matches the recorded type-argument DIE;
59 pointer/alias cases need structured-chain comparison before claiming equivalent element types.
Observed method counts vary from zero to four; a primary containing only `elems` cannot silently
replace every explicit specialization. This is a complete name-level sample, not a check of every
one of the 28,837 CU observations.

`ctree-family-evidence.json` (SHA-256
`05a184a72167666fad8117bcf10cb7c2138015846b8e898af909130cd344aa44`) retains four
CU/DIE-bound observations across the three indexed `cTree` spellings. All four outer classes are
56 bytes, have the same four member offsets, and cite `cBVHGrass.h:168`. Two other instantiations
have a complete 32-byte nested `cNode`; both `rGrass::cCluster` observations expose only an
incomplete nested `cNode` in that CU. The two `searchT` DIEs in the exact `rGrass` specialization
each have a `DW_TAG_template_type_param` whose argument DIE equals the referent DIE of the explicit
parameter. That supports a *member-function template* declaration that need not name
`uGrass::cRenderOperatorCDRAW` in an early primary, but it does not prove an original generic
`cTree` body or reconcile all specialized methods.

The new `nested-generic-layout-valid.cpp` canary models an early primary with the observed host
sizes and a source-supported member-function template. The optional canary report at
`generic-schedule-canaries/declaration-canaries.json` matched all 36 MSVC/Clang C++17 and
latest/C++23 outcomes, including the prior negative ordering cases. A separate copy of the v15
bundle changed only `nDDOUtility.h` to a candidate `T elems[N]` primary; both `nDDOUtility.h` and
`cPawnActInterface.h` compiled standalone with MSVC and Clang. The copy has **no valid publication
manifest** and is diagnostic only. Its exact modified header hash, compiler hashes, commands, raw
logs, and four pass statuses are in `carray-generic-diagnostic-only/carray-diagnostic-probe.json`
(SHA-256 `f43b07ac60a004e73363fe46e09cc0165ce9cf5ba76c2c904aa585626b1ecf7b`). The
producer still emits the explicit specialization and the manifest-bound result remains 60/65.

The next production step is a small source/producer-bound **declaration certificate**, generated
off the hot path, that validates every required type-argument chain and method obligation before
allowing a generic primary. The declaration scheduler must publish that primary once, before the
owner, and retain explicit specializations for observed distinct methods only where their order
is legal. If any certificate check is incomplete or conflicting, keep the explicit/blocking result.
This can make the `cArray` cycle repair reproducible without a 28,837-row family scan in normal
generation; `cTree` still needs member-template modeling and nested-node reconciliation.

## T011 member-template declaration probe: September 26

Producer `ddon-dwarf-reconstructor.symbols.compilation-repair-v15` publishes a member-template
primary declaration inside its proven owner when the DWARF scope and parameter signature agree,
while retaining the blocked specialization and its unresolved-definition diagnostics. This is a
declaration-visibility repair, not a generic template body. The local `n4950` draft conversion at
commit `1ef40e3d656c6e77e07ead58308e76b7b55ebf4a` supports member-template declarations in
`temp.md` `[temp.mem]`; the tracked `nested-member-primary-valid.cpp` canary passed MSVC 19.51.36260
and Clang 22.1.8 in C++17 and latest/C++23 modes. The complete canary report, with 32 matched
outcomes, is `output/compilation-repair-022/t011-20260926/v15-canaries/declaration-canaries.json`
(SHA-256 `03ee50a6616648885fd3279a92cfc165b1e5f4f7d09871344638ca3f1912f6df`).

The fresh source-bound `rGrass` output is
`output/compilation-repair-022/t011-20260926/real-rGrass-nested-primary-v15/ps4-02020005/`
(manifest SHA-256 `b4d2ff4d0c18f90425cdbf1dfc916790a4879f642b511ccece9c9d3454263340`).
Its `uGrass.h` adds exactly `template <typename _NODE_> class cRenderOperatorCDRAW;` within
`uGrass`; the other 64 header bytes match v14. The root remains `partial` because the concrete
specialization cannot yet be emitted and the two nested by-value cycles remain. The manifest-bound
MSVC report at `real-rGrass-nested-primary-v15-validation/msvc-header-validation.json` (SHA-256
`c9ccf4ae48d5427a706b8c082baf4fe6c798e6c57ac1a3c6f999946dd41f1adf`) attempted all
65 headers: 60 passed, five failed, none timed out, and aggregate compilation failed. The first
compiler errors remain at `cBVHGrass.h:34`, `nDDOUtility.h:29`, and `uGrass.h:144`. This probe
does not close T011, T013, or the 289-root acceptance gate.

A separate warm-process context run took 191.19 seconds and produced a byte-identical manifest and
all 65 byte-identical headers. A fresh-process `--no-generate-context` run took 183.47 seconds and
produced the same 65 header bytes with no context manifest, as intended. All three runs returned
exit code 1 because the `rGrass` status remains `partial`. The repeated "different source" cache
message refers to a retained symbol-cache file last written on August 2; it does not justify
deleting that file or treating this pair of wall times as a performance win.

After the final guard against unqualified member-template primaries, `just test-unit` passed 1,464
tests, `just check` and `just test` passed, `coverage-ci` passed with 81.99% total coverage and all
scoped gates, and `just audit` reported zero messages. The 35 focused template-family tests passed.
The next falsifiable compiler experiment is a bounded, source-bound structural comparison of the
three observed `cTree` instantiations and a representative cross-section of `nDDOUtility::cArray`:
parameter-referenced member types, base and member offsets, alignment, nested declarations, and
method sets must normalize consistently before a candidate primary body is even considered. A
matching sample is a hypothesis, not permission to replace explicit specializations. If that
comparison cannot support a lawful primary, retain blocker `022-NESTED-BY-VALUE-001` and use
Feature 023's C++ to DWARF differential fixture to identify the missing source fact.

## Optional compiler feedback: September 26

The readable C++ reference is cloned outside the project at `D:/research/cppstdmd`, detached at
`1ef40e3d656c6e77e07ead58308e76b7b55ebf4a`. Its `n4950/` Markdown is the primary local
lookup for current declaration clauses; the versioned `n4140/` and `n4659/` chapters remain
available for historical language-mode comparisons. The clause routes, limits, and invocation
contract are in [compiler-feedback.md](compiler-feedback.md). The clone is a draft conversion,
not ISO authority or an inferred historical producer profile.

MSVC changed in place during this investigation from 19.51.36252 to 19.51.36260 (binary SHA-256
`b0a1818ebae6da7f18230a84e76ce839212584ac4c2ab55b97a0d5268085da57`). The optional
probe correctly classified a selected recompile against the older report as `partial` because
compiler hashes differed. A fresh unchanged-bundle validation was then retained under
`output/compilation-repair-022/compiler-feedback-20260926/current-msvc-validation/`: 60 of 65
standalone headers passed, five failed, none timed out, and aggregate failed. Its manifest binding
matched all 65 published headers; this still is not full-corpus acceptance.

The current report-bound probes are under `output/compilation-repair-022/compiler-feedback-20260926/`:
`verified-u00037/selected-failure.json` first reports `C2065` at `nDDOUtility.h:29` for
`cPawnActInterDisableMgr`; `verified-u00002/selected-failure.json` first reports `C2065` at
`cBVHGrass.h:34` for `rGrass`. Both report the unchanged publication manifest SHA-256
`66db3ea52112a5282509fbaa373d13d1d4e2f8a4ba03e657785805190f55c040`, the pinned
reference commit, compiler identity, observed include trace, and a source-matched CU/DIE witness
verified against the retained `owner-evidence.json` hash. The witnesses establish the real nested
owners; a first compiler error is not automatically a complete causal analysis or a legal repair.

`verified-canaries/declaration-canaries.json` records 28 matched expectations across MSVC
19.51.36260 and Clang 22.1.8, C++17 and latest/C++23 modes, seven tracked minimal sources,
and an observed `clang-query`/host record-layout probe. Both owner-first and
specialization-first nested by-value header include orders fail in each profile. The ordered
allocator explicit specialization passes, and its reversed order fails. An initial reversed **generic** allocator
example passed because instantiation was delayed; it was replaced by explicit specialization
fixtures before retaining this result. These canaries distinguish language scheduling from the
source-evidence question; they do not prove a generic DDON primary, PS4 ABI, or Feature 022
acceptance. The original v14 report remains five failures among 65 standalone headers and an
aggregate failure. T009-T014 and the 289-root gates remain open.

The four current report SHA-256 values, in order of fresh MSVC bundle, canaries, pawn selected
probe and grass selected probe, are:

```text
7aa5ae4642c08342645f6226ac6fb08f89bba1d109ed6130a4206068faa70977
c839004e7d9a542b32bf154dce0e318dd9b67e1385a0402ecb23093b759a9bfe
124db69856250b4a29ed46705269b68200de872944b7bafb34153c6d26278485
9595df6e9ec97e6bf882cfb2187768cdfdcad93999cb233f70206bd8a82bbb63
```

The verified focused validator/probe suite passed 24 tests. Final `just test-unit` passed 1,462
tests; `just check` passed; `just test` passed 1,457 tests; `just coverage-ci` passed with 81.96%
combined coverage and all scoped coverage gates; `just audit` reported zero messages. Explicit
Markdownlint for the new spec page and updated Feature 022/023 research pages passed. These gates
cover this tooling slice, not the final Feature 022 producer or semantic closure.

## Implementation continuation: September 20-22

Evidence root: `output/compilation-repair-022/20260920-235036/`. The verified `producer.zip`
captures 934 effective tracked and relevant untracked files before these repairs. `snapshot.json`
records their hashes, the closed archive hash, HEAD, and the 289-root request hash. Producer
fingerprint: `9bd3e5b1e1f55de567ed195684a0e8b787833480b13d926b6498ccd945840445`.
Four large non-producer text/dump artifacts are inventoried in place rather than copied.
Existing sources, caches, analytical stores and retained outputs were preserved.

`retained-report-inventory.json` binds the three historical full/probe reports to report/manifest
hashes, compiler identities, flags, code counts, failure classifications and unit records.
It confirms 683/753, 526/753 and 20/24 passing respectively; all three aggregate attempts failed.
These remain historical producer observations, not current candidate acceptance.

`doris-preflight.json` records a validated complete runtime manifest, source binding and serving
registry, followed by `DorisDwarfIndex.targeted_symbol_search` results with explicit `complete`
status for `cArcLoader01`, `rCharacterEditCameraParam`, and `rGrassWind`. The source identity
matches the retained PS4 store. This proves those bounded searches, not full-corpus closure.
No storage repair, service restart or runtime fallback was performed.

T003 stabilized the existing alias self-cycle repair and formatted the two remaining files.
Retained gates: `t003-alias.log` (7 passed), `t003-unit.log` (1,278 passed, seven deselected),
`t003-check.log` (complete root check passed), and `t003-test.log` (1,273 passed, 12 deselected).
These supersede the earlier formatting-blocked package-delivery observations below.

The current T004 slice preserves every nested anonymous-type typedef, names the anonymous
definition through its first source typedef, and emits a real `typedef struct/union/class/enum`
definition rather than inventing an aggregate tag. Subsequent aliases retain access and target
provenance and follow the definition. The reverse alias index is bounded and resolver-owned;
it never scans an entire CU or namespace to guess an unavailable alias. Those unavailable
reverse-reference cases remain explicit diagnostics for dependency closure, not fabricated names.

`t004-focused.log` records 71 focused tests. Four emitted canaries passed Clang C++17, and
`t004-msvc/msvc-header-validation.json` records four standalone headers plus aggregate success,
zero diagnostics, and MSVC 19.51.36252. These small canaries do not establish the 289-root result
or PS4 ABI compatibility. Final T004 gates passed: `t004-unit.log` (1,293 passed, seven
deselected), `t004-check.log` (complete root check), and `t004-test.log` (1,288 passed,
12 deselected). The MSVC canaries also verify public named declarations following private
anonymous typedefs. Publication uses producer identity `compilation-repair-v1` so changed
anonymous declaration semantics cannot reuse the earlier producer stamp. General nested
declaration scheduling remains T010/T011 work.

T005 retains qualified generic-primary identity during definition deduplication and adds
regressions for distinct qualified arguments, conflicting same-specialization observations
across CUs (including offset zero), and both publication members. `t005-focused.log` records
35 passed; `t005-unit.log` records 1,298 passed; `t005-check.log` passed; `t005-test.log` records
1,293 passed. `t005-msvc/msvc-header-validation.json` records standalone and aggregate success
for the emitted two-specialization canary, with both namespace-owned argument definitions.
Primary-template declaration placement was still open at the T005 boundary; T006 below repairs it.

T007 follows T005 before T006; both depend on T005 and are implemented sequentially because
they share family policy. The compiler-guided overload check uses the C++17 target contract in
[over.load](https://timsong-cpp.github.io/cppwp/n4659/over.load), rather than assuming the newest
working draft has identical correspondence rules. The first MSVC canary caught mixed
ref-qualified/unqualified members with different cv qualifiers (`C2559`); retained failure:
`t007-msvc/msvc-header-validation.json`. That feedback tightened the checker. An old unit test
that expected a conflicting return type to disappear was corrected to require a diagnostic.
Final T007 gates passed: `t007-focused.log` (82 passed), `t007-unit.log` (1,328 passed,
seven deselected), `t007-check.log` (complete root check), and `t007-test.log` (1,323 passed,
12 deselected). `t007-msvc-final/msvc-header-validation.json` records standalone and aggregate
success for legal cv/ref overloads. `t007-negative-canaries/compiler-oracle.json` retains six
Clang rejection cases for illegal duplicate declarations. The checker preserves declaration
attributes separately from overload keys; family planning blocks conflicts, and rendering
raises `MethodDeclarationError` rather than dropping a conflicting return type. Type aliases,
parameter adjustment and structured/string normalization remain T009 work.

The continuation quality loop also passed `coverage-ci` (1,323 tests; combined coverage 81.42%,
total line coverage 84.8%; all scoped line/branch gates passed) and `audit` (zero Prospector
messages). Logs: `continuation-coverage.log` and `continuation-audit.log`. These gates validate
the current repair slices, not T018 final-producer acceptance after all remaining tasks.

T006 now derives primary declarations from the family signature and proven lexical scope.
Literal-based parameter guesses and maximum-arity selection were removed. Namespace headers
use the same primary policy, including parameters on a primary without specialization spelling;
incomplete reads fail rather than publishing a partial namespace. Declaration-only parsing
examines direct parameter DIEs without hydrating members/methods and never caches that projection
as a complete class. Namespace scanning remains proportional to the requested namespace's direct
types and their direct children; no full-CU traversal or runtime fallback was introduced.

The negative-argument canaries exposed filesystem sanitization in macro guards (`Box<-1>`).
`header_guards.py` now supplies valid, bounded guards with qualified-name fingerprints; regression
cases cover namespace, case, punctuation and truncation collisions. This intentionally changes
header bytes. The first report (`t006-msvc/msvc-header-validation.json`) retains three guard
failures; corresponding headers are copied in `t006-canaries-before-guard-repair/`. The repaired
report (`t006-msvc-final/msvc-header-validation.json`) records all 11 standalone headers and the
aggregate passing with zero diagnostics. The cases cover signed/boolean/short parameters in
three rendering modes, namespace declarations and different signatures on same-spelled primaries.

T006 focused generation/application checks currently record 320 passed and two explicitly skipped
real-asset tests. Settled-slice gates passed: `t006-unit.log` (1,357 passed, seven deselected),
`t006-check.log` (complete root check), `t006-test.log` (1,352 passed, 12 deselected),
`t006-coverage.log` (81.49% combined coverage, 84.9% total lines; all scoped gates passed),
and `t006-audit.log` (zero Prospector messages). Complex
non-type declarators and parameter alias normalization remain T009; required alias/owner ordering
and missing-dependency diagnostics remain T010/T011. These canaries do not close corpus acceptance.

## T008 enum and bitfield evidence: September 24

Evidence root: `output/compilation-repair-022/t008-20260924/`. Enum parsing now keeps
scopedness (`true`, `false`, or unknown), the observed flag state, representation type and DIE,
fixed-base uncertainty, byte-size status, CU/DIE identity, and lexical scope separately. An
absent `DW_AT_enum_class` is unknown for a named C++ enum; rendering raises an explicit
`EnumDeclarationError` instead of inventing `enum class` or unscoped semantics. A known scoped
enum uses its integral representation for a compatible declaration and definition. An explicitly
unscoped enum has no opaque forward declaration or inferred fixed-base syntax. The model does
not treat `DW_AT_type` as proof that the source spelled a fixed enum base. This follows the
[DWARF 5 enumeration description](https://dwarfstd.org/doc/DWARF5.pdf), which says the flag
*may* be present for type-safe semantics.

Member parsing retains zero bit sizes, distinct `DW_AT_data_bit_offset` and
`DW_AT_bit_offset`, source CU/DIE and terminal integral/enum type width. Alias and cv wrappers
are followed without erasing pointer indirection. Rendering preserves unnamed zero-width
alignment barriers, rejects named zero-width, static, nonintegral, and over-wide field
declarations, and keeps a 128-bit member-pointer storage observation as a member pointer.
Nested struct rendering no longer drops an unnamed zero-width barrier lacking a byte offset.

Focused parser/rendering tests passed (52 tests across four modules). Final slice gates:
`test-unit.log` records 1,392 passed and seven deselected; `test.log` records 1,387 passed and
12 deselected; the complete `just check` gate passed, including structure, typing, architecture,
API freshness and documentation. `coverage-ci.log` records 1,387 tests, 85.0% total line and
69.9% total branch coverage, with all scoped gates passing. `audit.log` has zero Prospector
messages. The exact-renderer `EnumBitfieldCanary.h` was regenerated after the settled code;
`validation/msvc-header-validation.json` records one standalone header and aggregate MSVC
19.51.36252 success with zero errors, error-limit units, or timeouts. This is C++ syntax
evidence, not layout, PS4 ABI, or 289-root acceptance.

The read-only `doris-enum-evidence.log` binds the query to promoted source SHA-256
`4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0`.
It counted 233,785 enum DIEs and 1,013 `DW_AT_enum_class` attribute rows; every present flag
row had decoded value `true`. A bounded first-30 enum sample had no scopedness or underlying
type attribute, while all 30 had byte sizes. These counts show a large evidence gap, not that
every absent flag denotes an unscoped enum. T013 should identify which requested root closures
need such enums and retain their source DIEs; if contextual compilation cannot disambiguate a
specific case, T019 must record the minimal blocker and link the 023 declaration-IR experiment.
No full corpus generation or compiler acceptance is claimed here.

### T008 source-producer correction and bounded real-root probe

The first `rGrass` generation probe stopped at `MtAllocator::TYPE` (CU 613377789,
DIE 613403976). Read-only adapter evidence identifies the CU producer as
`clang version 3.5.0 (PS4 clang version 2.50.0.2333)`, DWARF version 4, C++ language 4.
This enum has neither `DW_AT_type` nor `DW_AT_enum_class`. The historical
[Clang 3.5 frontend](https://raw.githubusercontent.com/llvm-mirror/clang/release_35/lib/CodeGen/CGDebugInfo.cpp)
supplied an underlying type when `EnumDecl::isFixed()`; the historical
[LLVM 3.5 emitter](https://raw.githubusercontent.com/llvm-mirror/llvm/release_35/lib/CodeGen/AsmPrinter/DwarfUnit.cpp)
then emitted `DW_AT_type` and `DW_AT_enum_class` together whenever that type was
present. It did not test source-level `isScoped()`. In the promoted source, all
1,013 enum flag rows pair with `DW_AT_type`; there are no type-only rows among
the 2,026 matching attribute rows. A full read-only inventory of those 1,013
flagged DIEs found exactly one per CU and one name, `io_errc`, in all 1,013;
the first 25 owners were the `std` namespace. The C++
[working draft](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/n4950.pdf)
specifies `std::io_errc` as a scoped enum. The parser does not generalize that
standard-library identity into a rule for arbitrary fixed enums.
This producer-conditioned evidence supports
non-fixed unscoped syntax for `MtAllocator::TYPE`. A flagged fixed enum could
be either `enum class` or an unscoped enum with an explicit base, so it remains
unknown. The parser applies the profile only to the exact producer string,
DWARF4, and C++ CU language; it retains the raw flag and fixed-base evidence.

The next probe passed that enum but stopped on `MtOscillator::mpUpdateFunc`.
Its source DIE 613430240 reports `DW_AT_bit_size=128`, a wrapped
`DW_AT_bit_offset`, `DW_AT_byte_size=0`, and byte location 48. The type chain
is typedef `UpdateFunc` (DIE 613430263) to `DW_TAG_ptr_to_member_type`
(DIE 613430910) to a subroutine type. The renderer now treats that bit size as
member-pointer storage evidence, not legal C++ bitfield width. Focused tests
retain the exact chain and offset, while a separate regression keeps invalid
nonintegral bitfields rejected.

The third isolated `rGrass` run reached publication, with 60 emitted headers,
142 selected classes, 29 diagnostics and root status `partial`. The source-bound
manifest is at `t008-20260924/real-rGrass-legacy-profile-2/ps4-02020005/`.
MSVC 19.51 compiled both `MtAllocator.h` and `MtOscillator.h` standalone;
the entire partial bundle had 40 passing and 20 failing standalone headers,
and the aggregate failed. The dominant remaining diagnostics involve owner,
template, alias, and ordering closure; they belong to T010-T015. A partial
bundle and these two passing headers do not establish full Feature 022 acceptance.

Current settled-tree gates after the producer and member-pointer correction:
`current-test-unit.log` records 1,403 passed and seven deselected;
`current-check.log` passed all quality and documentation checks;
`current-test.log` records 1,398 passed and 12 deselected;
`current-coverage-ci.log` records 85.0% total lines, 69.9% total branches,
and all scoped thresholds passed; `current-audit.log` has zero Prospector
messages. The first `current-check.log` attempt failed only the two newly
introduced complexity limits; the enum policy was decomposed and the final
log passed. These are slice gates, not T018 final-producer acceptance.

T009 has started but remains open. `array_parser.py` now carries a structured
`TypeReference`, rejects inexact dimensions and preserves ordered nested
array/callable layers; `header_hierarchy.py` no longer caches qualified names
by Python object identity, and `type_reference_parser.py` caches only complete
CU/DIE keys. A subsequent method-signature slice makes source and rendered
method deduplication use one structural parameter key; template-family
signatures ignore stale raw parameter/member/return spelling when a structured
reference exists. The former text-only alias table conflated `u8` with `s8`
and `uint8_t` with `int8_t`; it was removed rather than repaired by another
unproved global alias map. Focused regressions cover opposite signedness,
callable layer order, and typed-versus-raw divergence. The settled-tree gates
above precede this latest method-signature edit; fresh gates are recorded
separately below. C++ parameter adjustment, alias-target equivalence and a
real-source compiler comparison remain T009 work before US2.

### T009 incremental verification and namespace enum diagnosis

The completed method-signature increment follows complete typedef targets instead of a global
spelling map, and applies C++ array/function parameter adjustment only to structured declarator
layers. It leaves qualified or incomplete aliases distinct rather than erasing possible element
qualification. Focused tests cover alias-target identity, missing targets, array/function decay,
and inner array extents. This is an incremental improvement; return-type alias equivalence and
the full source-to-rendered declarator contract still need T009 review.

Final tree gates after this increment are retained under `t008-20260924/t009-final-*`:
`unit` has 1,412 passing tests and seven deselected; `check` passed, including strict Zensical;
`test` has 1,407 passing tests and 12 deselected; `coverage` reports 85.0% total line and
70.0% total branch coverage with all scoped gates passing; `audit` found zero Prospector
messages. `t009-adjusted-focused-final.log` retains the focused signature tests.

A source-bound `rGrass` run from the final tree published 60 headers and 142 classes with
29 diagnostics; its sole requested root remained `partial`. Its manifest and MSVC report are
under `t008-20260924/real-rGrass-t009-adjusted/ps4-02020005/` and
`t008-20260924/real-rGrass-t009-adjusted-validation/`. MSVC 19.51 attempted every emitted
header: 40 standalone passes, 20 failures, no standalone timeout, and aggregate failure with
one error-limit unit. `MtAllocator.h` and `MtOscillator.h` still pass standalone. The 60 emitted
header hashes and standalone statuses match the immediately preceding T009 probe exactly;
this proves no compiler regression in that bounded closure, not full-corpus improvement.

The 29 generation diagnostics include 25 missing method parameter/return dependencies on
`nDraw` names. Read-only source-bound queries found `nDraw::PASS_TYPE` at CU 613377789,
DIE 613447899, and `nDraw::COMPARISON_FUNC` at DIE 613448065. Both are complete namespace-child
`DW_TAG_enumeration_type` DIEs without fixed-base/scopedness attributes in the exact profiled CU;
they contain 26 and eight enumerators respectively. `FORMAT_TYPE` (DIE 613446507) and
`DRAW_MODE` (DIE 613450884) are likewise complete namespace enums with 55 and 13 enumerators.
The current `nDraw.h` publishes selected class definitions but none of these namespace enum
declarations. `DIETypeClassifier.requires_resolution` explicitly excludes enum DIEs, while the
namespace renderer visits only class/struct children. The class-only canonical graph therefore
has no enum publication node to connect to the method edges. The remaining `C2039` and
signature failures are a concrete typed-publication and dependency-closure problem for T010-T013,
not evidence that the T008 enum syntax policy should invent a forward declaration. A safe repair
needs the enum DIE identity and complete definition in a lawful namespace-owned header, then an
include edge to consumers. No hardcoded `nDraw` include was added.

### Namespace enum publication increment: September 24

Evidence root: `output/compilation-repair-022/t009-20260924/`. The renderer now emits complete
namespace-child enum definitions from parsed DIEs. The symbol publisher resolves referenced
namespace enum CU/DIE identities, rejects conflicting same-qualified definitions, groups them
in guarded `shared/*-enums-*.h` headers, and includes those headers from each class consumer.
Enum-only headers retain qualified identities and root origins in `symbol-artifacts/2`; root
header counts include them. A namespace-root header includes the shared enum header and omits
its matching local definition. A different same-named definition is an error, not silently
deduplicated. An absent or unknown scopedness still fails closed.

The real `nDraw` namespace canary (`namespace-enum-canary/` and its MSVC report) contains
`PASS_TYPE`, `COMPARISON_FUNC`, `FORMAT_TYPE`, and `DRAW_MODE`; standalone and aggregate MSVC
compilation passed. The structured parameter-adjustment canary likewise passed standalone
and aggregate compilation. Both are bounded canaries.

The fresh source-bound `rGrass` candidate in `real-rGrass-enum-publication-2/ps4-02020005/`
published 62 headers and 142 classes, including 14 `nDraw` enum identities. The generated
`cDraw.h` includes the shared enum header. Its 25 former unresolved method-enum diagnostics
disappeared after preserving the qualified type spelling in diagnostic reconciliation;
four diagnostics remain, and the root status is `partial`. The two `rGrass` enum-publication
runs have the same header-bundle SHA-256
`5432d5bcfc1c3d9f09f2b5025ae2ed0b0e94926b8fae7721596bcf59e78e0603`;
the first run's MSVC report therefore checks the second run's identical header bytes.
MSVC attempted all 62 standalone headers: 50 passed, 12 failed, zero timed out, zero `C1003`
abort units; aggregate compilation failed. The immediately preceding no-enum `rGrass` probe
passed 40 of 60 headers. This is a bounded improvement, not full-corpus acceptance.

The source-bound `nDraw` request in `real-nDraw-enum-publication/ps4-02020005/` published
57 headers. Its namespace header includes the shared enum definitions once; the enum-only
headers and both namespace-root headers pass standalone. Bundle MSVC attempted all 57:
40 passed, 17 failed, zero timeouts and zero `C1003` abort units; aggregate failed.
The preceding no-publication request passed 30 of 54 with three `C1003` units. The report's
`C2371` examples concern `uint64_t` aliases, not duplicate enum definitions.

Retained SHA-256 identities: `real-rGrass-enum-publication-2` manifest
`4876c6307c50483f6b6e12db2d0ad701dfdaaaa53aac3be34a1a7c8b3cc90196`,
`real-rGrass-enum-publication-validation` MSVC report
`0894cab52b7988d1732a530225196d8d0a210167e5d5ed92200515c742d76180`,
`real-nDraw-enum-publication` manifest
`1716c3991e4139f0af77be200d04f8c02e89177dbd0f395a88ea2116e5c73e2b`,
and `real-nDraw-enum-publication-validation` MSVC report
`905e27edb6281539b00d5706dad0a52ec43dd8000f73b3992f13671b06a11bd6`.
The final source additionally rejects a mismatch between a namespace-root definition and
its separately selected shared definition; that rejection has focused tests but no fresh
real-source MSVC rerun after the conflict-check-only edit. T009-T013 remain open.

### T010 source-identity and alias-visibility increment: September 24

Evidence root: `output/compilation-repair-022/t010-20260924/`. A source-bound `cDraw` trace
found distinct `cDraw::SHADER_STATE` (DIE 613436620, 24 bytes) and `nDraw::SHADER_STATE`
(DIE 613440298, 16 bytes) in CU 613377789. The dependency extractor retained the latter
offset, but the single-root hierarchy path deduplicated by short name. Single-root generation
now uses the same identity-preserving union path as multi-root generation. The canonical graph
also maps every original source DIE to its final merged definition, including cross-CU
equivalent definitions. A reduced two-owner, cross-CU test failed before that fix and passes
after it. The prior parser shortcut that cloned a same-named, same-sized class from another CU
without checking members or owner was removed; two tests reproduced its layout loss first.

The bounded `cDraw` probe went from 39/48 standalone MSVC passes with `nDraw::SHADER_STATE`
absent to 42/49 with that definition published and `cDraw.h` passing. The aggregate remains
failed. The post-clone-removal `cDraw` bundle retained exactly the same header-bundle SHA-256,
`b6e023b29153480f9581665960c6ac35e39ec682cd5831e75cb59426b6a3f5a8`, for that
root. These are different header populations, not a percentage claim about the full corpus.

The initial `rGrass` source-edge bundle attempted 63 headers: 53 passed, ten failed, no
timeouts, aggregate failed. It showed two independent alias-visibility failures:
`sce::Gnm::AlignmentType` and `nDraw::HIndexBuffer` were used with qualified names but
declared as global typedefs. Source references now place such aliases in their evidenced
namespace and reject conflicting same-local-name scopes. The first new source-bound bundle
attempted 68 headers: 58 passed, ten failed, no timeouts, aggregate failed;
`gpumem.h` and `nDrawIndexBuffer.h` changed from failure to pass. Its expanded population
also exposes duplicate `MtMatrix` definitions, which remain a publication-identity defect.

The first alias repair still flattened cross-namespace targets. For example, it emitted
`nDraw::GPUFORMAT_TYPE` as an alias to unqualified `DataFormat`, although the generated
definition is `sce::Gnm::DataFormat`. The renderer now uses the alias target's structured,
source-derived spelling and keeps legacy typedef text only when no typed namespace alias
exists. A focused regression covers this cross-namespace target and same-local-name ambiguity.
The v5 `rGrass` bundle passed 59/68 standalone headers; `nDrawTexture.h` newly passed, but
`nDrawShader.h` still emitted `struct nDraw::HInputLayout;` after declaring that name as an
alias. A reduced test reproduced the invalid forward declaration. The v6 producer omits
aggregate forwards for typed alias identities; MSVC passed 60/68 standalone headers with
zero timeouts and zero `C1003` abort units. `nDrawShader.h` passed, but aggregate compilation
and the root status remained partial.

The v6 bundle also exposed two `MtMatrix` complete definitions in different CUs: DIEs
25261899 and 613391546, both from `MtMath.h:1612`. Their rendered 64-byte fields and other
declarations matched; the former had one additional method. The canonical graph now merges
same-qualified observations only when the full non-method fingerprint agrees and one exact
method-signature multiset contains every other observation. It selects the richer definition,
retains both source identities, and leaves incompatible methods or layouts as explicit
conflicts. Both positive and negative reduced tests were red/green. The v7 `rGrass` bundle
published 65 headers and 146 classes, down from v6's 68 and 148; the duplicate `MtMatrix`
definition no longer appears, and no `MtMatrix` conflict diagnostic remains.

MSVC 19.51 attempted all 65 v7 headers: 60 passed, five failed, zero timed out, zero `C1003`
abort units; aggregate compilation failed. The remaining failures are `cBVHGrass.h`,
`cPawnActInterface.h`, `nDDOUtility.h`, `rGrass.h`, and `uGrass.h`. They trace to nested-owner
and template declaration scheduling, not the repaired namespace aliases. The `rGrass` root
remains `partial`; no full 289-root or ABI claim follows from this bounded probe. V7 manifest
SHA-256: `6ae3466d1e487954d6ecca0fcc5a063bed10ee19e34a1e7e5f7adb1d7c1b21fb`;
MSVC report SHA-256: `5a5e4696c889dbad1b6cd1c23bfe78de2c864bd3204bf8fe973b91e1b2087d02`;
header-bundle SHA-256: `a3ad5dfae3dd744915f5bdecf78d681d129b6f8f71ebbb4303b4881be3213f63`.

V7 deterministic gates under `t010-20260924/method-subset-v7-*` passed: 1,431 unit tests,
1,426 default tests, `check` including strict Zensical, coverage at 85.1% lines and 70.3%
branches with every scoped gate passing, and zero Prospector audit messages. API pages were
regenerated. These are final gates for this slice, not T018 full-corpus completion. T009 and
T010 remain open: typed completeness requirements, nested owners, SCC scheduling, and full
diagnostic closure still need work.

### T011 nested-template scheduling probe

The v7 residuals expose two include cycles that cannot be solved by reordering the current
explicit-specialization headers. `rGrass` embeds `cTree<rGrass::cCluster>` by value after
defining nested `cCluster`; `cPawnActInterDisableMgr` embeds
`nDDOUtility::cArray<cPawnActInterDisableMgr::cNode, 16>` by value after defining nested
`cNode`. Each generated specialization header needs the nested argument's enclosing class,
while the enclosing class needs the specialization complete for the by-value field.

Three Clang C++17 syntax probes are retained under
`output/compilation-repair-022/t011-20260924/`: an explicit specialization declared after
the outer class failed because the outer member used an incomplete specialization; a primary
template instantiated before its nested argument definition failed because the argument was
incomplete; a defined primary template with the nested argument defined before the member
compiled. These establish a legal scheduling shape, not that the DDON primary template body
has been recovered. T011 must inspect source-bound template-family evidence and require a
compilable, justified primary or another lawful declaration plan. An enclosing shell or an
opaque byte replacement would change C++ identity or member semantics and is not accepted.

Read-only source-bound Doris definition-index queries were complete below a 100-row ceiling:
`cArray` and `nDDOUtility::cArray` had no definition rows, while the exact nested-node
`cArray<...>` specialization had 27 class-type rows. `cTree` had one subprogram row and no
class-type row; the exact `cTree<rGrass::cCluster>` specialization had ten class-type rows.
This does not prove the C++ source lacked primary templates: a compiler may omit their
uninstantiated declarations from DWARF. It does mean this lookup cannot justify synthesizing
a primary definition by itself. A bounded comparison of multiple specialization layouts and
method signatures, followed by compiler evidence, is the next experiment.

That comparison began with bounded source queries. A grouped `cArray<%` index query hit its
201-name ceiling, so the displayed names are explicitly partial. A separate source-bound
aggregate counted 252 distinct names and 28,837 definition-index rows for this family.
Complete exact-name windows returned 27
`cArray<cPawnActInterDisableMgr::cNode, 16>` rows, 27 `cArray<MtVector3, 3>` rows, and 378
`cArray<u32, 8>` rows below a 1,000-row ceiling. One hydrated DIE from each has `T` and
unsigned `N` template-parameter children and an `elems` array member; class byte sizes were
512, 48, and 32 respectively. The `u32,8` observation also has `operator[]` and `fill`
declarations that the two others do not expose. A complete grouped `cTree<%` query found
three spellings. Hydrated `cTree<rGrass::cCluster>`, `cTree<uGrassWind>`, and
`cTree<MtTriangle>` observations each have a 56-byte class with virtual pointer,
`mParamNum`, `mpRoot`, nested `cNode`, and `mParams`; their method observations differ.
This supports investigating a guarded primary-template model but does not yet establish
identical source-level methods, nested-node layouts, or all family variants. The next query
must finish the `cArray` family inventory and compare normalized typed member/method IR
before promotion.

### T009/T010 CU-bound dependency identity increment

The dependency name planner no longer falls back from an explicitly qualified type such as
`ns::Leaf` to an unrelated unqualified `Leaf`. Offset-based edges now use CU/DIE pairs, prefer
the resolved type reference's target CU when evidenced, retain offset zero, and omit ambiguous
offset-only matches. Complete unqualified typedef targets also normalize return-type identity
for method declaration compatibility. Focused regressions cover these cases; the helpers were
separated into `header_dependency_names.py` to meet the module and test line budgets.

The fresh source-bound `rGrass` output is under
`output/compilation-repair-022/t009-20260924/real-rGrass-cu-identity-v7/ps4-02020005/`.
All 65 header bytes and the generation manifest are identical to the preceding v7 canary;
the manifest SHA-256 remains
`6ae3466d1e487954d6ecca0fcc5a063bed10ee19e34a1e7e5f7adb1d7c1b21fb`.
The new MSVC report is
`output/compilation-repair-022/t009-20260924/real-rGrass-cu-identity-v7-validation/msvc-header-validation.json`
(SHA-256 `73a2e1ca17663fcd255a3c274605568fe238c6b5fdf4722e02c534e42587dda4`):
65/65 standalone attempts, 60 passed, five failed, no timeout or `C1003`, and aggregate
failed. The failure classes and diagnostic-code counts match v7. The producer still reports
`rGrass` partial; unchanged output is a no-regression observation, not compilation closure.

Settled-tree gates under `t009-20260924-*.log` passed: 47 focused tests, 1,434 unit tests,
1,429 default tests, `just check` including structure and strict documentation build,
`coverage-ci` at 85.2% lines and 70.3% branches with all scoped gates passing, and `just audit`
with zero messages. API pages were regenerated. T009 and T010 remain open for the complete
source-to-rendered declaration contract and typed visibility/completeness edges; T011's
nested-template cycle remains the observed real-root blocker.

### T010/T011 lexical-owner requirement and cycle witnesses

The dependency planner now derives lexical-owner requirements from complete, source-bound
`TypeScope` ancestry for member, static, method, alias, and nested-class type references.
These requirements survive pointer and method-signature shortcuts. It retains owner edges in
the immutable plan but withholds edges internal to an SCC from generated includes until a legal
declaration schedule exists. This avoids introducing an include loop as a speculative repair.
Focused tests cover the provenance requirement, an acyclic external owner include, and a cyclic
owner edge that remains diagnosed rather than silently forgotten.

The current v8 `rGrass` canary is under
`output/compilation-repair-022/t010-20260924/real-rGrass-owner-scc-v8/ps4-02020005/`
(manifest SHA-256 `35aa8f060b82782e543e26c6989f3068422feb276633e5c4a2550ccd6045f7ad`).
It publishes 65 headers and 146 classes with a partial root and nine generation diagnostics.
Two diagnostics give CU/DIE-bound owner-cycle witnesses: `cTree<rGrass::cCluster>`,
`rGrass`, and `uGrass` form one component; `nDDOUtility::cArray<cPawnActInterDisableMgr::cNode,
16>` and `cPawnActInterDisableMgr` form the other. The 65 header bytes match the preceding
SCC-scheduled v7 probe. Against the earlier v7 canary, `nDDOUtility.h` changed by removing a
cyclic include; the count of failing headers did not improve.

The v8 MSVC report at
`output/compilation-repair-022/t010-20260924/real-rGrass-owner-scc-v8-validation/msvc-header-validation.json`
has SHA-256 `8c40b561ec3f52a386da8fd723670c27817cdbcef5e19b444906a66749560b55`.
All 65 headers were attempted: 60 passed, five failed (`cBVHGrass.h`,
`cPawnActInterface.h`, `nDDOUtility.h`, `rGrass.h`, and `uGrass.h`); none timed out or hit
`C1003`, and aggregate compilation failed. This is a bounded diagnostic result, not T010/T011
closure or full-corpus acceptance.

The settled v8 tree passed `just test-unit` (1,437 passed), `just check`, `just test`
(1,432 passed), `just coverage-ci` (85.2% total lines, 70.4% branches; all scoped gates),
and `just audit` (zero messages). Logs are retained under
`output/compilation-repair-022/t010-20260924-v8-*.log`; API pages were regenerated.

### T010 ambiguous-name correction and source-bound inheritance

The old header name index used first-wins lookup for duplicate spellings. In this root,
`cUnit` has two conflicting complete definitions with different CU/DIE identities. A v9
probe that rejected first-wins selection exposed the missing requirement: `uCoord.h`,
`uGrass.h`, and `uWind.h` lost a complete base include, and standalone results fell to
58/65 passing. That probe remains under `real-rGrass-ambiguous-index-v9` as failed
diagnostic evidence, not an accepted repair.

The v10 planner retains ambiguous spellings separately and resolves inheritance using the
recorded base-type DIE offset plus the class CU. It does not assume that the base-offset
list is positionally aligned with base-name strings. The current output is
`output/compilation-repair-022/t010-20260924/real-rGrass-base-offset-v10/ps4-02020005/`
(manifest SHA-256 `67fd8475d1814b84622c418aff2624d5b632881388355af9d7b6805f7b773d9c`).
`uGrass.h` and `uWind.h` now include `cUnit-2090e0ae.h`, the definition in their CU;
`uCoord.h` retains `cUnit-fc0269ab.h` from its different CU. These are the only two
header-byte differences from v8. A focused regression proves ambiguous bare-name lookup
does not choose the first class, while by-value and inheritance edges with matching CU/DIE
evidence select the intended source identity.

The v10 MSVC report is at
`output/compilation-repair-022/t010-20260924/real-rGrass-base-offset-v10-validation/msvc-header-validation.json`
(SHA-256 `747ff2ab9b23d921c0bc547618e59afead3605e4d6799b2e9499ead2e35d7425`).
All 65 headers were attempted: 60 passed, the same five failed, zero timed out, zero
`C1003`, and aggregate compilation failed. The root remains partial with 146 classes and
nine generation diagnostics. There is no improvement in compiler acceptance count, but
the emitted base dependencies now follow the recorded source identities. This v10 result
predates the following diagnostic-only v11 increment.

Settled v10 gates passed: 1,438 unit tests, `just check`, 1,433 default tests,
`coverage-ci` at 85.2% lines and 70.4% branches with all scoped thresholds, and
`just audit` with zero messages. The logs are retained under
`output/compilation-repair-022/t010-20260924-v10-*.log`.

The subsequent v11 plan records an explicit `ambiguous complete base requirement`
diagnostic when a duplicate base spelling has no matching source-bound base DIE. A focused
regression checks both that witness and its propagation into symbol-generation diagnostics.
The v11 source-bound `rGrass` output is under
`output/compilation-repair-022/t010-20260924/real-rGrass-base-ambiguity-v11/ps4-02020005/`
(manifest SHA-256 `7014fc93eed690fe1b1b1ca438a32b92f8d10deebeb8b1b0892bbe7226195534`).
All 65 C++ headers are byte-identical to v10, and this root has no new unresolved-base
witness: it remains partial with nine diagnostics. The fresh MSVC report at
`output/compilation-repair-022/t010-20260924/real-rGrass-base-ambiguity-v11-validation/msvc-header-validation.json`
(SHA-256 `7712c3d7340e111e27dbd556026cef4b2b804c86ed24a94bcd23643ed970e869`)
attempted all 65 headers: 60 passed, five failed, zero timed out, zero `C1003`, and
aggregate failed. Other ambiguous requirements, incomplete search, and fully typed edge
reasons remain T010 work.

Settled v11 gates passed: 1,439 unit tests, `just check`, 1,434 default tests,
`coverage-ci` at 85.2% lines and 70.5% branches with all scoped thresholds, and
`just audit` with zero messages. Logs are retained under
`output/compilation-repair-022/t010-20260924-v11-*.log`.

### T009 CU-bound cache and base-name increment: September 24–26

The v12 producer `ddon-dwarf-reconstructor.symbols.compilation-repair-v12` uses
complete CU/DIE keys for nested aggregate base-name lookup and request-owned type
reference caches. Equal DIE offsets in different CUs and incomplete CU evidence
have focused regressions. The source is SHA-256
`4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0`.

The bounded `rGrass` output is
`output/compilation-repair-022/t009-20260924/real-rGrass-cu-cache-v12/ps4-02020005/`;
its manifest SHA-256 is
`f7000c22a34eab07b1ce5578e90d36c211ff17b2d0d557ae3a6ae2618358c943`.
The root remains `partial`: 146 classes, 65 emitted headers, and nine generation
diagnostics. All 65 header bytes match v11. The v12 MSVC report at
`output/compilation-repair-022/t009-20260924/real-rGrass-cu-cache-v12-validation/msvc-header-validation.json`
has SHA-256
`3f743191a37d39c6a376ecdfce996cc4f3de1b4147b8b24cdfbd43075ce849d7`.
It attempted all 65 headers: 60 passed, five failed, none timed out, zero
`C1003`, and aggregate compilation failed. The failures remain in
`cBVHGrass.h`, `cPawnActInterface.h`, `nDDOUtility.h`, `rGrass.h`, and
`uGrass.h`; they do not show a new enum error or a compiler-count improvement.

The retained v12 gate logs under `output/compilation-repair-022/t009-20260924-v12-*.log`
show 1,441 unit tests and 1,436 default tests passing, `just check` passing,
and `coverage-ci` at 85.2% total lines and 70.5% branches with all scoped
thresholds satisfied. A September 26 `uv run just audit` rerun reported zero
messages, but has no retained v12 log. These gates and the bounded compiler
probe do not close T009–T020 or the full 289-root acceptance matrix.

### T009/T011 scheduler diagnostics and source probe: September 26

The v13 producer changes incomplete-CU offset matching and labels deterministic
cycle emission as unschedulable rather than recovered. Nested by-value cycles
now raise instead of falling back to source order. Focused tests cover these
rules and a cycle identity whose template argument contains a comma.

The fresh source-bound `rGrass` probe is
`output/compilation-repair-022/t009-20260926/real-rGrass-scheduler-v13/ps4-02020005/`
(manifest SHA-256
`9d108c059edd1349e8d09efcbcc7ca7eab1adea1b606afee897dbe126a92a3b8`).
All 65 header hashes match v12 exactly; 146 classes and nine diagnostics
remain, with the root `partial`. The MSVC report at
`output/compilation-repair-022/t009-20260926/real-rGrass-scheduler-v13-validation/msvc-header-validation.json`
has SHA-256
`1a32070896ee2838d16e9ed8a2df261b688207d52a20810864e983fda3d6092c`.
It attempted all 65 standalone headers: 60 passed, five failed, zero timed
out, zero `C1003`, and aggregate failed. This demonstrates no header-byte or
compiler-count change for this one root, not full-corpus acceptance.

Read-only complete definition-index queries against the promoted source found
zero rows for the nested-primary spelling `uGrass::cRenderOperatorCDRAW` and
ten rows for `cTree<rGrass::cCluster>` below a 1,000-row ceiling. Direct DIE
hydration found `uGrass::cRenderOperatorCDRAW<rGrass::cCluster>` at CU
613377789/DIE 613379568, parent `uGrass` at DIE 613377831, and a template
type-parameter child `_NODE_` at DIE 613380113. This establishes a real nested
template specialization and a parameter observation, not a generic body or a
legal cross-owner schedule. The exact nested-node `cArray` spelling returned
zero definition-index rows despite its direct CU 25252129/DIE 25268804 class
DIE; indexed-name absence cannot be used as proof of source absence. Broad
`MtProperty` and `cUnit` exact-name windows each hit the 1,000-row safety
ceiling, so neither result is complete conflict evidence.

### T011/T014 nested-owner blocker and publication accounting: September 26

The current producer is
`ddon-dwarf-reconstructor.symbols.compilation-repair-v14`. The fresh
source-bound `rGrass` result is under
`output/compilation-repair-022/t011-20260926/real-rGrass-v14/ps4-02020005/`
(manifest SHA-256
`66db3ea52112a5282509fbaa373d13d1d4e2f8a4ba03e657785805190f55c040`).
Its 65 header hashes are byte-identical to v13. All nine generation diagnostics
remain and the root is `partial`. The new manifest-bound MSVC validator report
is under `output/compilation-repair-022/t011-20260926/real-rGrass-v14-validation/`
(report SHA-256
`234930ea3304dd7411426af417f833d62f0065fe3bed19a1c36c05fb39d81a38`).
It reconciled all 65 attempted headers with the publisher's manifest and
reported 60 passes, five failures, no timeout or `C1003`, and aggregate failure.
The validator now marks a missing, changed, extra, or skipped published header
as incomplete even if remaining compiler markers and aggregate compilation pass.
This closes a validator-accounting gap, not declaration closure or T014's entire
include-order and acceptance scope.

Provisional blocker `022-NESTED-BY-VALUE-001` affects the requested `rGrass`
root. The promoted store manifest SHA-256 is
`bbe354bf3f838c8a1da6da501b9829a1bedf533f4834f0a4710dcbb574886078`;
its source SHA-256 is
`4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0`.
Direct source-bound hydration, retained in
`output/compilation-repair-022/t011-20260926/owner-evidence.json`
(SHA-256 `cb74bb6cd91565b83ababa2f0c807cdafe158d32d39ea881374b6ab01fcdac13`),
observed the following exact requirements:

| Enclosing definition | Nested argument | By-value member and type target | Explicit specialization |
| --- | --- | --- | --- |
| `rGrass` CU 613377789 / DIE 613467425 | `cCluster` DIE 613467621 | `mCluster` DIE 613467607 targets DIE 613471923 | `cTree<rGrass::cCluster>` DIE 613471923 |
| `cPawnActInterDisableMgr` CU 25252129 / DIE 25602499 | `cNode` DIE 25602620 | `mNodes` DIE 25602594 targets alias `cNodes` DIE 25602608, which targets DIE 25268804 | `nDDOUtility::cArray<cPawnActInterDisableMgr::cNode, 16>` DIE 25268804 |

For each explicit specialization, owner-first emission makes the by-value
member incomplete; specialization-first emission cannot name the nested
argument of an incomplete owner. Four minimized C++17 source variants under
`output/compilation-repair-022/t011-20260926/` reproduced these two orders
for both families with Clang and MSVC. The positive
`nested-explicit-specialization.cpp` compiled under both profiles: a real owner
may declare a nested template primary and define an explicit specialization
later when only reference use precedes it. That positive case does not provide
the complete by-value specialization needed here. Exact commands, return codes,
source and log hashes are retained in `owner-canaries.json` (SHA-256
`ffac69a189da32278b5b16c2f0d623487a71828b0455edde14de26e5c5b96f11`).
The profiles were local Clang C++17 syntax-only and MSVC 19.51 C++17 `/Zs`;
neither is PS4 ABI evidence.

The current explicit-specialization representation has no legal declaration
schedule for these two observed cycles. This does **not** prove the original
source lacked lawful primary-template definitions: uninstantiated source
templates need not appear as DWARF class definitions. A fresh bounded
source-index inventory in `template-family-inventory.json` (SHA-256
`f3caf26c1b26332394fe2553830b62a4936f221f4a7a5c01d5621781f1cfed5e`)
completed all 252 indexed `cArray<...>` spellings and 28,837 rows below a
501-name ceiling, plus all three `cTree<...>` spellings. The nested `nDDOUtility`
specialization remains absent from this name index despite its directly
hydrated class DIE, so name-index completeness is not source completeness.
One first complete class DIE per indexed spelling, recorded in
`template-family-observations.json` (SHA-256
`b2854e308a2c574232bed81f3deda0243b8142de50e0f550a2ce4b176de2a4fd`),
found an `elems` member in all 252 `cArray` observations but 14 distinct
direct-child shapes. The three indexed `cTree` observations each had a 56-byte
class and the same direct-child names. This samples one complete CU observation
per spelling, not every CU variant or normalized semantic method signature.
A generic body, opaque storage substitution, fake enclosing shell, or renamed
nested type has therefore not been promoted. The next falsifiable experiment is
to normalize typed member/method/layout observations across all relevant CU
variants, including the directly hydrated nested `nDDOUtility` case, then
compile a guarded candidate primary against all observed specializations and
reject any semantic or layout divergence. Feature 023 T001 owns the research
gate and T007 the
declaration-event prototype if Feature 022 T013/T019 confirm the handoff;
T015-T020 and final zero-error acceptance remain open.

After the v14 producer-ID update, `test-unit` passed 1,453 tests, `check`
passed, `test` passed 1,448 tests, `coverage-ci` passed at 85.3% total lines /
70.6% branches with all scoped thresholds met, and `audit` reported zero
messages. These gates cover this partial slice; T018 remains open until the
final producer and acceptance corpus are ready.

This record is for reviewers distinguishing the September 20 review from future repair results.
All observations below were gathered during the preceding review in this conversation, before
these spec packages were authored. They are not a post-repair acceptance run. Recheck mutable
service state before implementation. Large snapshots, logs, and generated artifacts remain local.

## Reviewed Working State

Observed 52 tracked modified files, eight new production modules, seven new test/support modules,
and untracked `scratch/` and `resources/.cache/`. The dirty implementation includes structured
references/scopes, explicit family planning, alias work, and unfinished publication/validation.
Preserve it. Feature 022 T001 must create its own identified implementation snapshot; HEAD alone
does not identify this producer.

`scratch/test_roots.txt` contains `rCharacterEditCameraParam` and `rGrassWind`. It is a diagnostic
subset, not the 289-root acceptance request. Scratch scripts include ad hoc configuration and
raw-source inspection; their existence does not establish a supported generation workflow.

## Repository Checks Observed During Review

| Command/check | Observed result | Boundary |
| --- | --- | --- |
| `uv run --no-sync just test-unit` | 1 failed, 1,277 passed, 7 deselected; 46.89 seconds | Existing alias self-cycle test did not raise `AliasDeclarationError` |
| `uv run --no-sync ruff check --no-fix src tests tools/sonar` | Passed | No source auto-fixes |
| Structure checker | Passed | Gemini's two complexity failures were stale |
| `uv run --no-sync pyrefly check` | Zero errors; five suppressed | Does not establish generated C++ validity |
| API reference check | Passed; 378 modules in six pages | Generated docs already matched reviewed source |
| `uv run --no-sync just check` | Failed at format-check | Three files require formatting; later recipe steps did not run |

Formatting failures: `src/ddon_dwarf_reconstructor/domain/services/generation/alias_rendering.py`,
`header_member_rendering.py`, and `src/ddon_dwarf_reconstructor/domain/services/parsing/class_parser_context.py`.
The failed test is `tests/domain/services/generation/test_alias_rendering.py::test_alias_conflict_missing_target_and_cycle_fail_explicitly`.
These session observations are not retained full acceptance reports; rerun and retain outputs
under the implementation snapshot before closing the corresponding tasks. They are historical:
the specification-time recheck below supersedes the earlier alias and format observations.

## Doris: Live at the Review Boundary

Read-only Docker inspection showed FE and BE running. `SHOW BACKENDS` reported `Alive=true`,
empty `ErrMsg`, version `doris-4.1.3-rc02-7126cf65d96`, and 259 tablets. Bounded source/name queries
for `cArcLoader01` and `rGrassWind` succeeded. This proves liveness and those queries, not complete
lookup or full-store semantic integrity.

Observed SQL port: 29030. Database: `dwarf`, with `dwarf_records_*` tables. The proposal's
`ddon.dwarf_dies` query does not match this deployment. Registry rows were complete with matching
recorded counts; those metadata counts are not an independent new whole-table audit.

Observed BE storage bind:
`C:/DorisRecovery/ddon-analytical-dwarf/recovery-20260917-1315/doris-be-4.1.3`.
No marker was deleted, permissions changed, volume replaced, or service restarted. Historical I/O
failure evidence remains relevant to outage diagnosis, not proof of a current blocker.

Source SHA-256:
`4236f598acc8f15893181455ed195e39dfa4dbfda4eeda8b56fcbd82312c63c0`.

## Retained Compiler Reports

Paths in this table are beneath `output/template-family-review/`. Counts were read from retained
JSON, not produced by this documentation change. Both full bundles' 753 recorded header hashes
were checked against files: no missing or mismatching header hashes were found.

| Report | Requested roots / headers | Standalone | Aggregate | Units reporting C1003 |
| --- | --- | --- | --- | --- |
| `current-validation/msvc-header-validation.json` | 289 / 753 | 683 pass, 70 fail | Failed | 9 |
| `recovery-20260916-223850/baseline-retry/validation/msvc-header-validation.json` | 289 / 753 | 526 pass, 227 fail | Failed | 29 |
| `recovery-20260916-223850/alias-probe-20260917/retry/validation/msvc-header-validation.json` | 1 / 24 | 20 pass, 4 fail | Failed | 0 |

The first report started September 15; the retry and alias probe reports started September 17.
The first two identify different producers (`template-families-v1` and `template-families-v2`);
the probe identifies `typed-recovery-v3`. These numbers do not alone prove a current regression
or improvement. Reconcile source snapshots, configuration, identities, and unchanged baselines.

Generation manifest SHA-256 values, in table order:

```text
0db9c56c8205adf6cd656c577503e7a8819970fd1eae163dd1e5e59b9e3c3a4a
3266296557e3e85a0b9bdba59ce80951af9c48dacf5d18afa36f2861cf364db2
b3cf98ded823a526b5f98a9dfc615d73aa0119367febf591fae9487e8ae8c963
```

Their generation roots are respectively `current-generation/ps4-02020005`,
`recovery-20260916-223850/baseline-retry/generation/ps4-02020005`, and
`recovery-20260916-223850/alias-probe-20260917/retry/generation/ps4-02020005`.
The two-root 493-header probe retained by Feature 021 is also a reduced probe, not a full baseline.

## Minimal Semantic Probes

Session probes reproduced specialization identity collapse, nested-definition validation losing
qualification, skipped nested-owner dependencies for pointers, alias self-cycle behavior, and
anonymous-enum alias loss. Clang 22.1.8 C++17 syntax probes rejected outer redefinition and
exception-only overloads, and accepted alias pointers to incomplete classes. The nested generic
counterexample in [research](research.md) distinguishes a language limit from an actual DDON
blocker. These probes motivate regression tasks; they are not yet the feature's retained canary suite.

## Acceptance State

| Dimension | State | Next evidence |
| --- | --- | --- |
| Current semantic repair | partial in bounded roots | T009-T013 typed closure and owner scheduling; v7 `rGrass` still has five failing headers |
| Full current-producer standalone/aggregate | not_observed | T015 fresh all-root generation and validation |
| Fresh/warm and context-mode determinism | not_observed | T016 matching process/mode comparisons |
| Matched performance | not_observed | T017 baseline-bound p50/p95 |
| Final root quality/coverage/audit | slice gates passed; final not_observed | T018 gates after full accepted producer; v7 slice gates do not close acceptance |
| New PS4 ABI/layout evidence | not_observed | Separate Feature 001 authority and layout checks |
| Source-bound irreducible blocker | not_observed | T019 minimal actual-source reproduction if needed |

No implementation task is closed by these historical observations.

## Specification-Package Validation on September 20

The two packages and Feature 021/roadmap links were authored without changing production, test,
or tooling files. SHA-256 comparisons covered all 628 files enumerated under `src/`, `tests/`,
and `tools/` before and after authoring; all matched at the comparison boundary.

- `uv run --no-sync just docs-check`: passed; API current at 378 modules, Markdownlint passed,
  17 Mermaid diagrams validated across 69 Markdown files, and strict Zensical build passed.
- `uv run --no-sync just check`: lock checks and Ruff passed; stopped at two pre-existing
  formatting failures in `header_member_rendering.py` and `class_parser_context.py`.
- Focused alias suite: seven passed in 0.12 seconds. Current `_sort_alias_dependencies` retains
  self edges; the earlier failing test is now repaired in the pre-existing working tree.
- `uv run --no-sync just test-unit`: 1,278 passed, seven deselected in 35.28 seconds. This
  supersedes the earlier unit failure; semantic and full-corpus acceptance remain separate.
- Explicit Markdownlint for both spec packages and changed Feature 021 pages: passed. This
  separate invocation is necessary because default Markdown globs do not include `specs/`.
- Local link/task audit: zero errors; 20 repair tasks and 18 IR tasks with valid local dependencies.

These are documentation-delivery and current-state observations, not completion of Feature 022.
No real-asset generation, service recovery, ABI validation, full coverage, audit, or performance
acceptance was performed while authoring these packages.
