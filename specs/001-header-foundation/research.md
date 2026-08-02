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
