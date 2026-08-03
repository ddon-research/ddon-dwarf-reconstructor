# Implementation Plan: Source-bound external tool evidence

## Evidence baseline

The local PS4 ELF is an ELF64 little-endian x86-64 FreeBSD-ABI image with Sony type `0xfe10`.
Orbis `objdump` identifies the target as `elf64-x86-64-freebsd` and preserves SCE program types;
generic LLVM/GNU readers accept the file but render generic or unknown SCE values. The existing
pyelftools session and Orbis disassembly adapter therefore remain authoritative boundaries.

Local help/version inventory covered Orbis 8.0 host tools, MSYS2 LLVM/GNU tools, libdwarf
`dwarfdump`, and the OpenOrbis/reference source locations. LIEF is not installed in the managed
Python environment, and `elfldr` is intentionally treated as loader research rather than an
inspection dependency.

## Design

1. Model a complete `ToolExport` and `ToolExportOutput` in the domain, independent of subprocesses
   and filesystems.
2. Keep named profiles and bounded execution in infrastructure. Reuse `SourceIdentityCatalog`,
   stream output to staged files through `toolchain_process.py`, hash outputs, validate before
   reuse, and publish atomically.
3. Load manifests once at the application boundary and pass typed exports through the generator to
   the knowledge exporter. Project only additive provenance records.
4. Provide a generic Debian/Compose baseline for GNU Binutils, LLVM, elfutils, libdwarf headers,
   Python/pyelftools, and zstd. Keep Orbis binaries host-specific and read-only.
5. Document the goal loop, authority matrix, uncertainty record, commands, tests, and exact
   validation tiers across repository instruction surfaces and the active Spec Kit feature.

## Exact paths and validation tiers

| Slice | Production paths | Test/evidence paths | Validation |
| --- | --- | --- | --- |
| Typed export contract | `domain/models/tool_evidence.py` | model/manifest tests | root unit/check |
| Tool profiles and runner | `infrastructure/toolchain_profiles.py`, `toolchain_exports.py` | `tests/infrastructure/test_toolchain_exports.py` | root unit, explicit local probes |
| CLI boundary | `artifact_cli.py`, `cli.py`, `main.py` | `tests/test_artifact_cli.py`, `tests/test_cli.py`, `tests/test_main.py` | root unit/acceptance |
| Knowledge projection | `application/exporters/knowledge_export_*.py`, generators | exporter and generator tests | root unit/integration |
| Generic container | `tools/binary_toolchain/{Dockerfile,compose.yaml}` | `just binary-toolchain-config`, explicit build | Docker availability |
| Guidance and contract | `AGENTS.md`, `.github/`, `CLAUDE.md`, `docs/`, `specs/010-*` | documentation review and Spec Kit checks | root check/nested checks |

## Risk controls

- Never infer PS4 ABI semantics from a generic reader's normalized label when Orbis reports a
  vendor value; retain both outputs with authority labels.
- Never ingest a partial export as complete evidence. A timeout, non-zero process, truncation, or
  stale checksum is a failed artifact, not a best-effort graph fact.
- Keep raw outputs outside source control and do not make expensive tool scans part of every lookup.
- Preserve deterministic ordering and existing DWARF/Orbis facts; only add graph records for
  validated tool artifacts.

## Handoff status

The implementation and validation slices are complete. The remaining boundary is intentional:
Sony SDK binaries and proprietary ELF/SELF inputs stay on the host, while generic Docker tooling
is a reproducible fallback. `elfldr`, SELF decryption/signing, LIEF promotion, and any claim that
generic output establishes PS4 ABI semantics remain separate follow-up work.
