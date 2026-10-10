# Contract: Repair publication, acceptance, and handoff

This contract serves implementers and reviewers deciding whether Feature 022 is complete.
It extends existing manifests and validators; field names below describe required information,
not an already deployed serialization schema.

## Run Identity

Retain source/store manifest identities, requested-root file hash and count, effective dirty
producer fingerprint, configuration/schema versions, exact command, process/cache state,
system-derived timestamp/timezone, compiler executable/version/flags, and output manifest hash.
The Git commit alone is insufficient for an uncommitted producer. Freeze tracked and relevant
untracked source in an external snapshot; preserve the working tree and existing evidence.

The request is `resources/season2-resources.txt`: 289 nonblank roots. The number of generated
headers may change legitimately after grouping; reconcile identities rather than requiring 753
files. A smaller probe never substitutes for the full request.

## Publication Integrity

Every requested root has a result and every selected declaration has a recorded owner or explicit
diagnostic. Includes, aliases, template primaries, and nested declarations must satisfy the
typed requirement graph. Record provenance and intentional substitutions; no dummy types,
guessed generic definitions, invented namespaces, or silent exclusions can satisfy completeness.

Retain atomic rollback behavior and source-bound cache validation. Equivalent requests produce
stable C++/assembly bytes. Compare deterministic payloads separately from operational timestamps;
do not silently strip fields to make a determinism test pass. Define that distinction in the
manifest schema and comparator before collecting acceptance runs.

## Acceptance Matrix

| Dimension | Passing evidence | Failure or limit |
| --- | --- | --- |
| Root/closure accounting | All 289 roots and all required identities accounted for without unexplained omission | Truncated lookup, omitted declarations, unresolved required types |
| Host standalone | Every emitted header compiled under the recorded MSVC profile | Error, timeout, uncompiled header, or C1003 |
| Host aggregate | All-header translation unit compiled under the same profile | Include-order or duplicate-definition failure |
| Language canaries | Minimal adversarial cases and selected include permutations under named profiles | Compiler/profile absence stays blocked |
| Evidence fidelity | Qualified names, type relationships, inherited/member facts and CU/DIE provenance reconcile | A compiler pass alone is insufficient |
| Determinism/modes | Matching fresh/warm runs and context-on/off C++/assembly hashes | Cache-state drift or unexplained mode difference |
| Quality | Required root tests/check/coverage/audit pass | Earlier green slice does not accept a later producer |
| Performance | Each matching workload/profile/cache-state p50 and p95 <=110% baseline | Missing/mismatched baseline, averaged ratios, traced timings |
| PS4 ABI/layout | Separate authoritative profile and layout evidence when claimed | Host compiler/triple alone never proves target ABI |

All gates required by the feature specification must pass to close it. Target-specific claims
remain separate from host compilation; unavailable independent ABI evidence must be reported
without pretending it was run. Inherit Feature 001's target acceptance obligations unchanged.

## Residual Blocker Record

Required fields: stable blocker ID; source/store/producer identity; affected roots and declaration
IDs; CU/DIE locators; observed DWARF facts and uncertainty; minimal compilable source and failing
reconstruction; tool/profile and diagnostics; reasoned requirement cycle or unsupported semantic
operation; attempted lawful repairs and their outcomes; exact successor task; next falsifiable
experiment; and retained external artifact hashes.

Distinguish a general C++ counterexample from an observed DDON blocker. A handoff is permitted
after local repair alternatives have been tested and the source-bound limitation reproduced.
It allows Feature 023 research or a targeted prototype. It does not close Feature 022, weaken
zero-error acceptance, or permit fabricated declarations. Newly available evidence can reopen
the repair route; the handoff does not prescribe a library in advance.
