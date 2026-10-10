# Compiler feedback and C++ rule lookup

> **Archived Python project:** This page describes the frozen Python snapshot.
> Development has moved to an unpublished Rust rewrite. See [archive status](../../docs/reference/project-status.md).

This research note is for maintainers investigating Feature 022 declaration failures. It records
host-compiler observations and the source evidence needed to classify them. It does not establish
PS4 ABI/layout correctness or replace the full 289-root acceptance gate.

## Local reference

The local reference is `D:/research/cppstdmd`, cloned from
[`lefticus/cppstdmd`](https://github.com/lefticus/cppstdmd) and detached at commit
`1ef40e3d656c6e77e07ead58308e76b7b55ebf4a`. Search the converted C++23 draft with, for
example, `rg -n 'class.nest' D:/research/cppstdmd/n4950/class.md`. The chapter's stable clause
labels permit reproducible lookup without installing the repository's converter. The markdown is
a third-party conversion of a working draft, not an official ISO publication. Compare
`n4140/` or `n4659/` when the historical producer's language mode matters, and resolve any
suspected conversion issue against the underlying WG21 draft and compiler canaries.

| Requirement | `n4950` lookup | Minimal distinction |
| --- | --- | --- |
| Real nested owner | `class.md` `[class.nest]`, `[class.mem]` | `struct O { struct I; };` declares `O::I`; `struct O::I;` outside an unintroduced owner does not. An enclosing shell is already a definition of `O`. |
| Explicit specialization | `temp.md` `[temp.expl.spec]` | `template<class T> struct Box; template<> struct Box<int> {};` has a visible primary declaration. That declaration alone supplies no generic body. |
| Complete by-value member | `class.md` `[class.mem]` | `struct B; struct A { B* p; };` is legal; `struct A { B value; };` needs `B` complete. |
| Alias visibility | `dcl.md` `[dcl.typedef]` | `struct B; using P = B*;` is legal before `B` is complete; consumers need the alias declaration, not necessarily the target definition. |
| Opaque enum | `dcl.md` `[dcl.enum]` | `enum E : int;` is legal; an unscoped `enum E;` lacks the required explicit enum base. DWARF representation type alone does not prove the source spelled that base. |

These are language rules to test, not permission to manufacture source declarations that DWARF
does not establish. The local converted chapters contain the full clauses; this table only routes
investigations to them.

## Selected failing header

Run the existing bundle validator's optional selected-unit mode against a retained, manifest-bound
report. It hashes every reported header and its publication manifest before recompiling one unit.
The example below uses the existing `rGrass` v14 report and a source-bound witness; all output
stays outside source control.

```powershell
$probeOut = "output/compilation-repair-022/manual-feedback-$(Get-Date -Format yyyyMMdd-HHmmss)"
uv run python tools/sonar/validate_header_bundle.py `
  --explain-report output/compilation-repair-022/compiler-feedback-20260926/current-msvc-validation/msvc-header-validation.json `
  --explain-unit u00037 `
  --requirement-witness specs/022-cpp-compilation-repair/pawn-owner-witness.json `
  --validation-directory "$probeOut/u00037"
```

`selected-failure.json` retains the report, header, manifest, source, reference commit, compiler
binary/version, flags, first *reported* error, `/showIncludes` tree and path to that error,
`/sourceDependencies` list, and raw-log paths. It never calls the first reported error a proven
root cause. A witness must match the manifest's source hash and a hashed source-evidence artifact
containing the named CU/DIE. Without that witness the declaration requirement remains
`unclassified`. A selected probe is diagnostic evidence; it does not change the original
standalone or aggregate acceptance statuses. The extra MSVC flags are diagnostic only.

## Reduced two-compiler canaries

Run the tracked `tests/fixtures/cpp/compiler_feedback/` cases with:

```powershell
$probeOut = "output/compilation-repair-022/manual-canaries-$(Get-Date -Format yyyyMMdd-HHmmss)"
uv run python tools/sonar/run_declaration_canaries.py `
  --output-dir "$probeOut"
```

The runner checks MSVC C++17 and `c++latest` plus Clang C++17 and C++23. Both orderings for the
`rGrass::cCluster` and `cPawnActInterDisableMgr::cNode` by-value specialization cases must fail;
ordered allocator *explicit specializations* and a valid nested-pointer case must pass. Reversed
allocator explicit specializations must fail. A generic allocator example can still pass with
source order reversed because instantiation is delayed; therefore a generic example is not a
sound test for the observed explicit-specialization scheduling problem. The valid nested case
also runs bounded `clang-query` and host record-layout observations. The runner records compiler
hashes/versions, source hashes, flags, raw logs and complete/partial status. These synthetic
canaries do not prove a generic primary body for DDON or target layout equivalence.

Normal generation does not call either compiler tool. An include trace tells which files were
read; declaration legality still comes from the source-bound requirement graph and a compiler
reproduction. Retain unresolved cases for Feature 022 T019 and Feature 023's C++ to DWARF
differential fixture.
