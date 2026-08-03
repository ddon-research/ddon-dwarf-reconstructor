# Feature Specification: Source-bound external tool evidence

**Status**: Implemented; external SDK and proprietary loader checks remain explicit

## Goal

Add a goal-oriented, provenance-preserving path for bounded one-time exports from PS4 Orbis,
LLVM, GNU Binutils, elfutils, and libdwarf toolchains. The resulting metadata must be reusable by
knowledge export and future indexes without replacing deterministic DWARF producer facts or making
unsupported PS4 ABI claims.

## Requirements

- **TEE-001**: The repository MUST expose typed tool profiles with explicit arguments, output
  format, description, and authority boundary.
- **TEE-002**: A tool probe MUST capture bounded `--version` and `--help` output with a stable
  executable identity and atomic publication.
- **TEE-003**: A source-bound export MUST stream raw output, fingerprint source and tool, include
  schema/profile/authority metadata, and publish only after successful completion.
- **TEE-004**: Manifest loading MUST reject incomplete, stale, duplicate, checksum-invalid, and
  path-escaping artifacts before knowledge export.
- **TEE-005**: Knowledge export MUST represent complete external exports as additive `Tool`,
  `SourceArtifact`, and `Evidence` records without overwriting `Type`, `Field`, `Method`, source,
  or producer facts.
- **TEE-006**: Matching Orbis tools MUST remain the PS4 ABI/SCE authority. LLVM, GNU, elfutils,
  libdwarf, pyelftools, LIEF, and OpenOrbis outputs MUST retain explicit additive/reference
  authority until PS4 behavior is validated.
- **TEE-007**: A non-proprietary Docker Compose baseline MUST provide common generic inspection
  tools and read-only input/output mounts without packaging Sony SDKs, credentials, SELF loading,
  or decryption.
- **TEE-008**: Copilot, Codex/AGENTS, Python, Claude, README, architecture, generation, testing,
  knowledge-base, and goal-workflow guidance MUST describe the workflow and boundaries.

## Non-goals

- Parsing every raw external output during every lookup.
- Adding LIEF as a runtime dependency before PS4 custom ELF behavior is validated.
- Replacing `ElfDwarfSession`, pyelftools, the source identity catalog, or Orbis disassembly.
- Executing `elfldr`, loading payloads, decrypting/signing SELF files, or modifying binaries.
- Committing proprietary ELFs, SDK binaries, raw dumps, caches, credentials, or generated output.

## Acceptance

- `artifacts list-tool-profiles`, `probe-tool`, and `export-tool-evidence` are typed, tested, and
  reachable from the canonical CLI.
- A warm export reuses a validated content key; stale source, invalid checksum, duplicate, and
  path-escape cases fail closed.
- Knowledge export tests prove additive provenance nodes and unchanged deterministic DWARF records.
- The actual PS4 ELF accepts Orbis and generic LLVM profiles, with the authority distinction
  recorded in the research and knowledge-base documents.
- `uv run just test-unit`, `uv run just check`, and `uv run just test` pass; coverage/audit and
  package, Docker, and nested specification checks are recorded separately when their
  prerequisites are available.
