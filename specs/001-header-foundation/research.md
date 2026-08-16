# Research: ABI-Oriented Header Foundation

## Decision: Use a streaming SQLite sidecar for compressed DWARF lookup

**Rationale**: The expanded PS4 DWARF dump is larger than practical in-memory
representation. A single streaming pass can collect class definition metrics and
method implementation references, while SQLite provides warm fresh-process lookup.
The sidecar is published through a temporary file and atomic replacement.

**Alternatives considered**:

- Retain the whole expanded dump in memory: rejected because it violates the
  repository performance constraint and scales poorly for the real corpus.
- Reopen and rescan the compressed dump for every query: rejected because batch and
  dependency resolution would repeat the dominant cost.
- Build a new external database service: rejected because the workflow is local,
  offline, and already has a durable artifact policy.

## Decision: Bind indexes and caches to source identity, not timestamps or path alone

**Rationale**: ELF and dump paths can be replaced or relocated. Size and boundary
fingerprints provide a cheap warm key, while the source catalog records a strong
SHA-256 identity. Metadata also includes producer, schema, and configuration
identity. Timestamp-only changes do not invalidate immutable source artifacts.

**Alternatives considered**:

- Use modification time: rejected because copying or touching an immutable input
  creates false invalidation and does not prove content identity.
- Use the resolved path: rejected because relocation and same-path replacement are
  normal operational cases.
- Hash every source on every lookup: rejected because it repeats expensive work that
  the source catalog already makes explicit and auditable.

## Decision: Centralize evidence selection before expanding renderer fidelity

**Rationale**: Duplicate DIE definitions can differ in completeness. A common
selection contract is required before adding namespaces, aggregate kinds, access,
bitfields, templates, and ABI qualifiers; otherwise renderer improvements can lock
in inconsistent roots.

**Alternatives considered**:

- Keep independent scoring in parser, dump parser, and dependency traversal:
  rejected because tie-breaking becomes path-dependent and nondeterministic.
- Always choose the first definition: rejected because forward declarations and
  partial definitions are common in multi-CU DWARF.

## Decision: Treat assembly as validation evidence in this feature

**Rationale**: Orbis reports can confirm method ownership, address ranges, vtable
signals, and member-offset hypotheses, but assembly alone cannot recover every C++
source declaration. Keeping it joinable but independent prevents inferred facts from
being presented as DWARF evidence.

**Alternatives considered**:

- Synthesize missing declarations immediately from assembly: deferred because the
  confidence model and source-generation contract are not yet defined.
- Keep assembly entirely disconnected: rejected because the user needs a way to
  catch incorrect DWARF-derived hypotheses.

## Decision: Use explicit compiler validation as an environment-gated quality tier

**Rationale**: Generated headers must be compilable. Visual Studio Community 2026
with MSVC x64 is available and has been verified with a standalone C++23 probe. The
first real sample run shows that isolated declarations compile with minimal stubs,
while the complete bundle exposes missing closure and nested-template rendering
defects. The compiler gate is therefore active, not deferred.

**Alternatives considered**:

- Treat substring assertions as proof of C++ validity: rejected because they cannot
  detect invalid arrays, qualifiers, includes, or inheritance declarations.
- Install a compiler implicitly during this feature: rejected because the verified
  Visual Studio toolchain is already available and its ABI limitations are recorded.

## Decision: Keep Spec Kit artifacts versioned and runtime artifacts local

**Rationale**: Constitution, specifications, plans, contracts, and tasks are shared
project intent. ELF inputs, expanded dumps, SQLite sidecars, generated headers, logs,
and caches are source-bound runtime products and remain outside Git.

**Alternatives considered**:

- Store generated headers and caches with the feature spec: rejected because it mixes
  mutable outputs with durable intent and makes cleanup ambiguous.
- Keep specifications only in chat: rejected because they cannot be reviewed,
  validated, or resumed by another agent.

## Decision: Use the installed ddon-hook MSVC environment for header compilation

**Rationale**: `vswhere.exe` reports a complete Visual Studio Community 2026
installation with the x64 VC tools component. `VsDevCmd.bat -arch=x64` resolves
MSVC `cl.exe` version `19.51.36252.0`, and CMake/Ninja are installed. The external
`ddon-hook` project provides the repository's relevant C++ conventions: C++23,
VS2026 presets, and warning configuration. This gives generated headers a real
compiler gate instead of relying only on string assertions.

**Alternatives considered**:

- Treat the presence of Visual Studio as sufficient without invoking `cl`: rejected
  because include closure and declaration syntax need an executable check.
- Use the existing `ddon-hook` full build: deferred because it requires external
  vcpkg/FetchContent dependencies and is broader than header verification.
- Compile reconstructed headers as a complete DDON implementation: rejected for
  this phase because framework types and method bodies are not reconstructed yet.

## Validation sample: random candidates plus IDA anchors

The recorded validation run uses the random non-template candidates
`rTextureMemory`, `rTexture`, and `rTutorialDialogMessage`, plus the IDA-reference
anchors `cSetInfoOmBreakTarget` and `rLayout`. The random set probes ordinary
resource types; the anchors test direct comparison against
`sample-ida-dump-cSetInfoOmBreakTarget.h` and `sample-ida-dump-rLayout.h`.

The comparison must distinguish recoverable facts (class kind, inheritance, field
names/types/offsets, method names/signatures, sizes, and vtable evidence) from IDA
presentation choices and unavailable source details. A compile failure caused by a
missing external DDON type is a closure gap, not proof that the DWARF fact itself is
wrong; it must be recorded with the missing dependency and a minimal verification
stub or closure task.

## Finding: Standalone Closure Is Complete For The Sample Corpus

The standalone five-header MSVC probes now return exit code 0 for
`rTexture`, `rTextureMemory`, `cSetInfoOmBreakTarget`, `rLayout`, and
`rTutorialDialogMessage`. T045 preserves the containing class definition and emits a
legal primary-template declaration. T046 distinguishes pointer-only forward
declarations from bases and by-value types, resolves the required structural closure,
and orders definitions before their uses. The `rLayout` probe retains two C4201
nameless-union warnings from recovered aggregate layout. This result is separate from
the aggregate multi-header translation unit, which exits with code 2. Repeated shared
declarations are the current root-cause hypothesis only; the raw compiler stdout and
stderr were not retained, so no C2011 or other duplicate-declaration diagnostic is
confirmed.

## Decision: Use one canonical implementation evidence index

The implementation report is the sole structured evidence authority for the post-header chain. It
retains all DWARF candidates, status transitions, exact method-range Orbis text, decoded
instructions, raw bytes, source/file offsets, instruction-owned references, tool invocations, and
structured limitations. The source-bound Orbis cache remains the authority for complete profile
stdout/stderr.

The default derived profile is `canonical-assembly`. It emits bounded original Orbis text as
`.raw.asm`, one exact-byte `.s` compiler input, a deterministic `implementation-context/1.0`
`.context.json` packet, and an SDK-produced `.o` when `orbis-as` accepts it, together with a
schema-`3.1` atomic publication manifest. `.raw.asm` is evidence only and is never passed to
`orbis-as`. It does not emit duplicate disassembly, reference JSON, free-form notes, empty files,
or `.cpp` files. A later agentic workflow can translate the canonical assembly into C++ without
rerunning Orbis.

This removes the previous duplication observed in the `rLayout` bundle: the report already held
the raw disassembly and structured references while the sibling files repeated them. The manifest
is intentionally retained because it binds the report hash, header identity, source identity, and
aggregate bundle digest for atomic publication; it is not a second evidence index.

Open points remain explicit: Orbis-to-GNU/Clang inline-assembly acceptance is not established;
the known-invalid combined symbol/dynamic-relocation profiles and the redundant full DWARF info
profile are documented capability decisions rather than runtime evidence; optimized source-line
mappings may be imprecise; external declarations and PS4 ABI/semantic equivalence are not inferred.
The context packet is now a bounded JSON sibling that records those unavailable dimensions rather
than inventing them.

## Decision: Use dual-authority PS4 ELF evidence

The target ELF contains SCE relocation metadata even though it does not expose conventional
`.rel.*` or `.rela.*` sections. Orbis `-r -C -w -F` is therefore an independent conventional
relocation cross-check and is `empty` for the current file. Orbis `-R -C -w -F` is known to return
`Invalid operation` in the observed Orbis SDK and is capability-filtered from normal generation.
Neither the documented limitation nor an empty conventional relocation view is evidence that the
ELF lacks relocations.

The implementation uses three authorities plus an additive target-aware cross-check:

1. Matching Orbis binutils owns PS4 instruction decoding, demangling, and textual disassembly.
2. LLVM 22.1.8 `llvm-readobj` is an opt-in generic ELF/DWARF structural cross-check. Its JSON
   output preserves unknown numeric `0x610000xx` SCE tags, but it does not replace Orbis output.
3. The in-repository `OrbisSceMetadataReader` reads `PT_SCE_DYNLIBDATA`, `.dynamic`, SCE tags,
   and 24-byte RELA records, validates segment/file ranges, and preserves raw fields, signed
   addends, unknown codes, and symbol resolution status without applying relocations.
4. LLVM 22.1.8 `llvm-objdump` is an opt-in per-method comparison producer invoked with
   `--triple=x86_64-scei-ps4`; it contributes address/byte comparison summaries only.

The local LLVM 22.1.8 help surface accepts `--triple` for `llvm-objdump` and rejects it for
`llvm-readobj`. Therefore `llvm-readobj` remains generic (`not_applicable` target status), while
target-aware slices are independently cached with their capability probe, range, command, output
hashes, and diagnostics. `llvm-tli-checker` is not used for ELF extraction because it checks target
library availability rather than decoding ELF methods.

The official SDK6500/n267 source was inspected directly. It defines
`PT_SCE_DYNLIBDATA=0x61000000`, `PT_SCE_PROCPARAM=0x61000001`, `PT_SCE_COMMENT=0x6fffff00`,
`PT_SCE_LIBVERSION=0x6fffff01`, standard `PT_GNU_RELRO`, and
`R_X86_64_ORBIS_GOTPCREL_LOAD=40` with four-byte signed 32-bit PC-relative GOT-load properties.
It does not define `PT_SCE_RELRO`. The typed runtime definitions retain source hashes for
`common.h`, `x86-64.h`, `elf64-x86-64.c`, and `README-ORBIS`; the source package is research input,
not a runtime dependency.

The current ELF reports `DT_SCE_RELASZ / DT_SCE_RELAENT = 172404` and
`DT_SCE_PLTRELSZ / DT_SCE_RELAENT = 539`, or `172943` complete cache entries. The complete table
is a source/tool/parser-bound streaming JSONL projection; the historical implementation report
schema was `3.2`; the schema-`4.0` validation report contains table descriptors and only
method-relevant entries linked by stable IDs. The Orbis cache
schema is `2.4` with parser identity `orbis-objdump-text-v7`; the SCE parser identity is
`orbis-sce-metadata-v3`. The cache key also contains the typed SDK-definition identity, so a
definition change invalidates the parsed relocation evidence.

Research references are [ps4_module_loader](https://github.com/SocraticBliss/ps4_module_loader/tree/657f9d380abfec9097bc4bddbc63551b3cd5e47b)
at commit `657f9d380abfec9097bc4bddbc63551b3cd5e47b`, path `ps4_module.py`, license `GPL-3.0`,
for SCE tag/segment and RELA conventions, and [GhidraOrbis](https://github.com/astrelsky/GhidraOrbis/tree/2d6e3fac23ae9830e941c32826e97100ed603311)
at commit `2d6e3fac23ae9830e941c32826e97100ed603311`, path `OrbisElfHeader.java`, license `GPL-3.0`,
for independent Orbis ELF-header handling. The SDK 8.0 source package at
`D:\SCE\ORBIS SDKs\8.000\license\src_package\binutils-orbis-2_22_1-src-SDK6500-n267`
is the local authority for the adopted ELF and relocation definitions. These external references
remain optional validation concepts, not runtime dependencies or vendored code; loader rebasing
and IDA calling-convention settings are not adopted. The aerolib.csv names may be ingested as
source-pinned community candidate evidence, but they are not official NID authority and require
NID hash and encoded library/module context checks before promotion.

Remaining uncertainty is intentionally narrower: runtime relocation base/application and loader
mutation, NID authority, optimized/inlined source-line precision, ABI/register/stack behavior,
host compiler acceptance of the Orbis dialect, semantic equivalence, and whether a newer Orbis
tool exposes `-R` or useful DWARF payloads. Additional open points are whether LLVM's accepted
target triple models Sony-specific ABI/relocations (it is not assumed to), whether host GNU/Clang
accepts the recovered Orbis operand dialect, whether a future agent workflow needs isolated
per-method context packets, and whether an Orbis-specific compiler validation environment becomes
available. `llvm-tli-checker` remains deferred until an SDK library/sysroot is explicitly supplied.
