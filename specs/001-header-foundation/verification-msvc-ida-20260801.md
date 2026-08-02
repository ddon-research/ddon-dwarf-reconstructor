# MSVC and IDA Verification: 2026-08-01

## Environment

- Visual Studio Community 2026 `18.8.1`.
- MSVC x64 compiler `19.51.36252.0`.
- Discovery: `C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe`.
- Developer environment: `VsDevCmd.bat -arch=x64`.
- CMake: installed at `C:/Program Files/CMake/bin/cmake.exe`.
- Companion project: `C:/Users/morph/CLionProjects/ddon-hook`.
- Companion project convention: C++23 in `CMakeLists.txt`; VS2026 configure
  presets and MSVC warning policy in `cmake/CompilerWarnings.cmake`.
- Existing `cmake-build-debug` cache uses CLion MinGW/Ninja and was not reused for
  this MSVC verification.

## Inputs and Outputs

- ELF: `resources/DDOORBIS.elf`, 800,622,848 bytes.
- Compressed DWARF dump:
  `D:/research/DDON-binaries/IDA9.3/PS4_DDON_02020005_2016_12_21/DDOORBIS.elf.llvmdwarfdump.zst`,
  1,086,393,794 bytes.
- New source-bound sidecar:
  `output/msvc-header-validation-20260801/DDOORBIS.elf.llvmdwarfdump.index.sqlite3`,
  206,422,016 bytes.
- Validation output: `output/msvc-header-validation-20260801/ps4/`.

The first sidecar bootstrap ran from approximately 13:09:27 to 13:26:44,
about 17 minutes 17 seconds. The sidecar was published atomically and reused by
subsequent fresh processes.

## Sample Corpus

Random non-template resource candidates:

- `rTextureMemory`: 264 bytes, one member, four methods.
- `rTexture`: 264 bytes, thirteen members, sixteen methods.
- `rTutorialDialogMessage`: 152 bytes, four members, seven methods.

IDA comparison anchors:

- `cSetInfoOmBreakTarget`.
- `rLayout`.

The random candidates do not have local IDA pseudo-headers, so they are checked
against DWARF-derived facts and compiler behavior only.

## Compiler Results

### Historical Pre-T046 Baseline

The following rows preserve the initial T041-T045 baseline. They document the
failure that motivated T046 and are not the current acceptance result.

A standalone C++23 probe compiled successfully with MSVC x64 using:

```text
/std:c++latest /EHsc /W4 /Zc:__cplusplus
```

Isolated declaration checks with minimal external-type stubs:

| Header | Result | Interpretation |
| --- | --- | --- |
| `rTexture.h` + `rTextureMemory.h` | PASS | Declaration syntax is valid when the missing `cResource` closure is supplied. |
| `cSetInfoOmBreakTarget.h` | PASS | Declaration syntax is valid when `cSetInfoOm` is supplied; the conflicting `size_t` typedef was removed. |
| `rLayout.h` | PASS | Declaration syntax is valid when missing framework and by-value dependency definitions are supplied. |
| `rTutorialDialogMessage.h` | FAIL | Qualified nested `rTutorialDialogMessage::cDialogPage` template use is invalid because the nested type is not emitted. |

The isolated wrapper reported exit codes `0, 0, 0, 2` for the four rows above.
The complete five-header wrapper returned exit code `2`; the standalone compiler
probe remained successful.

The historical complete five-header translation unit failed, as expected for the
then-current single-class closure, with these interpreted categories:

- Missing complete base definitions: `rTexture`, `cResource`, `cSetInfoOm`.
- Missing or incorrectly scoped nested template type:
  `MtTypedArray<rTutorialDialogMessage::cDialogPage>`.
- Missing complete by-value types in `rLayout`: `MtArray`, `stLayoutID`, and
  `stSplitID`.
- Missing forward declarations for several `rLayout::SetInfoBuffer` pointer types.

These were reconstruction closure/rendering gaps, not MSVC installation failures.
The category list is historical analysis of the generated headers, not a retained
compiler stderr transcript; it must not be reused as current compiler diagnostics.

### Current T046 Standalone Result

The standalone probes were regenerated after T046 with bounded structural dependency
traversal and compiled independently with the same MSVC x64 C++23 flags. The wrapper
returned exit code `0` for every sample:

| Probe | Result | Notes |
| --- | --- | --- |
| `rTexture` | PASS | Complete recovered base and structural dependency closure. |
| `rTextureMemory` | PASS | Standalone declaration compiles without external stubs. |
| `cSetInfoOmBreakTarget` | PASS | `cSetInfoOm` and its base chain are emitted before the target. |
| `rLayout` | PASS | `MtArray`, `stLayoutID`, `stSplitID`, `SetInfoBuffer`, and `SetInfo` are emitted; MSVC reports two C4201 nameless-union warnings. |
| `rTutorialDialogMessage` | PASS | Nested `cDialogPage` and legal `MtTypedArray<T>` primary template are emitted. |

Method-signature-only pointer/reference types remain legal forward declarations where
complete definitions are not required by C++. This bounded structural policy avoids
expanding each standalone header into unrelated framework method dependencies.

### Current Aggregate Result

The aggregate multi-header translation unit exits with code `2`. This result is
independent of the five standalone passes and means the representative corpus is not
currently an aggregate compilation pass.

The generated headers visibly repeat shared declarations, so duplicate shared
declarations are the current root-cause hypothesis. The raw compiler stdout/stderr
was not retained for this run; therefore no C2011 or other duplicate-declaration
compiler code is confirmed. The hypothesis must remain labeled as inferred until a
future run captures the compiler streams per translation unit and for the aggregate.

The current retained result also does not provide a complete per-TU record for
`compile_tutorial.cpp`, including flags, object status, and captured diagnostics. The
standalone `rTutorialDialogMessage` probe is a pass, but this reporting gap is owned
by T052 rather than silently treated as complete validation.

## IDA Anchor Comparison

### `cSetInfoOmBreakTarget`

| Fact | DWARF/generated | IDA pseudo-header | Status |
| --- | --- | --- | --- |
| Aggregate kind | `class` | `struct __cppobj` | Representation difference; aggregate layout intent. |
| Size | 120 bytes | Implied by DWARF fixture | MATCH. |
| Direct base | `cSetInfoOm` | `cSetInfoOm` | MATCH. |
| `mBreakHitNum` | `u32`, offset 112 | `u32 mBreakHitNum` | MATCH; offset is explicit in DWARF/generated metadata. |
| Constructor/destructor | recovered declarations | `_cSetInfoOmBreakTarget`, `~cSetInfoOmBreakTarget` | MATCH by role/name normalization. |
| Core methods | `getDTI`, `createProperty`, `createToolProperty`, `load`, `save`, `applyInfo`, `applyParam`, `copy` | Same method family | MATCH. |
| Virtual slots | `getDTI[5]`, destructor `[0]`, `createProperty[4]`, `createToolProperty[6]`, `load[7]`, `save[8]`, `applyInfo[9]`, `applyParam[14]`, `copy[11]` | Not represented in the IDA pseudo-header | DWARF-only evidence preserved; no conflict. |
| Calling convention | Not emitted by header generator | `__fastcall` | IDA presentation/ABI evidence not yet rendered. |

Conclusion: the recoverable declaration and layout facts align well. T046 now emits
the `cSetInfoOm` base closure before the target, and the standalone probe passes.

### `rLayout`

| Fact | DWARF/generated | IDA pseudo-header | Status |
| --- | --- | --- | --- |
| Aggregate kind | `class`, size 528 | Nested `SetInfo`/buffer/enums are shown; no complete top-level `rLayout` struct in this artifact | Partial artifact comparison. |
| Direct base | `cResource` | Methods and nested types imply the same hierarchy context | MATCH by DWARF/IDA context. |
| `TYPE` enum | `TYPE_SCR` through `TYPE_NUM` | Same values 0 through 5 | MATCH. |
| Main field offsets | `mpArray 112`, `mArrayNum 120`, `mIndex 124`, `mSetInfoNeedNums 380`, `mpSetInfoBuffer 472`, `mSetInfoSingleNewArray 480`, `mLotType 512`, `mLayoutID 516`, `mSplitID 520` | Top-level fields are not present in the supplied IDA pseudo-header | DWARF-only facts; no contrary IDA fact. |
| Nested `SetInfo` | Complete nested definition with recovered fields | IDA defines `rLayout::SetInfo` with `mID`, `mpInfo`, `mLayoutID`, `mSplitID` | MATCH by recoverable declaration scope and fields. |
| `SetInfoBuffer` | Complete nested definition with pointer declarations and `AvailNums[22]` | IDA lists all pointer types and `AvailNums[22]` | MATCH by recoverable declaration surface; two MSVC C4201 warnings remain for nameless unions and require explicit policy classification. |
| Shared methods | `getDTI`, `getExt`, `getSetInfo`, `getSetInfoNum`, `getID` | Same methods | MATCH by name/role. |
| IDA methods not emitted | `load`, `filePath2LayoutID`, `filePath2SplitID`, `clear`, and `SetInfo` methods | Present in IDA pseudo-header | PARTIAL; selected DWARF type/method closure does not yet reproduce the full IDA declaration surface. |
| Virtual slots | `getDTI[5]`, `getExt[7]`, `getSetInfo[16]`, `getSetInfoNum[17]`, `getID[18]` | Not represented in pseudo-header | DWARF-only evidence preserved. |

Conclusion: size, base, enum, main field facts, nested scope, and structural closure
are sufficient for the standalone `rLayout` probe. Method-surface differences remain
evidence gaps rather than compiler failures.

## Available IDA Evidence Limitation

The repository contains IDA-generated pseudo-headers, not decompiler method bodies
or full pseudocode listings for these anchors. Therefore this run validates
recoverable declaration/layout facts only. It cannot yet verify method control flow,
field access sequences, calling-convention behavior, or reconstructed C++ method
bodies.

## Required Follow-up

1. Implement completeness propagation and blocking diagnostics for declaration-only,
  partial, unresolved, and conflicting dependencies (T048).
2. Preserve qualified identity, aggregate closure, collision-safe multi-file output,
  and structured declarator/template evidence (T049-T051).
3. Replace the current wrapper summary with truthful per-TU and aggregate MSVC
  reporting, including `compile_tutorial.cpp`, captured streams, flags, object status,
  and C4201 classification (T052).
4. Preserve or explicitly classify calling-convention and vtable evidence, and add
  availability metadata for IDA-only declarations versus missing method-body
  pseudocode (T047 and T053).
5. Add actual IDA pseudocode/decompiler exports as a separate later evidence input.

## Python Regression Validation

After the vtable decoder, aggregate/member/method evidence changes, typedef-scan
guard, T045/T046 renderer changes, and `size_t` emission fix, the repository unit
suite completed with **319 passed, 4 deselected** tests. Current quality and unit
results must be recorded separately from this historical snapshot.

## T045 Follow-up

T045 preserves nested class definitions and their containing qualified names in the
DWARF model. Regenerating `rTutorialDialogMessage` emits `cDialogPage` before its
`MtTypedArray<rTutorialDialogMessage::cDialogPage>` member and replaces the invalid
specialization forward declaration with a legal `MtTypedArray` primary-template
declaration.

The historical `compile_tutorial.cpp` result reached incomplete `MtDTI` and `MtObject`
base definitions; the previous invalid nested-template diagnostic was absent. T046
now emits those structural bases and the current `rTutorialDialogMessage` standalone
probe passes with exit code 0. A separately captured `compile_tutorial.cpp` row with
streams, flags, and object status is still required by T052.

## T046 Follow-up

T046 routes ordinary standalone generation through structural dependency closure,
resolves base and by-value definitions, preserves nested aggregate scope, emits
legal declarations for pointer-only dependencies and template specializations, and
orders definitions before their uses. The refreshed five standalone probe rows are
`0/0/0/0/0`; the only retained compiler diagnostics are two C4201 warnings for
recovered nameless unions in `rLayout`. The aggregate translation unit still exits
with `2`, and its duplicate-declaration explanation remains unconfirmed without
captured stderr.
