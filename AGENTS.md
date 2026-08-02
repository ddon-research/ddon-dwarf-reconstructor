# DDON DWARF Reconstructor contributor guidance

This project extracts deterministic evidence from very large PS4 ELF/DWARF inputs. Performance is
the first constraint: avoid repeated ELF hashing, repeated full-DIE scans, whole-dump loads, and
unbounded in-memory intermediates. Preserve stable output ordering and source offsets.

## Development

- Install the complete development environment with `uv sync --extra dev`.
- Use package-relative imports; do not import the package through the repository's `src` directory.
- Run fast tests with `uv run pytest -m unit -o addopts='-q --strict-markers'`.
- Run read-only quality checks with `uvx ruff check --no-fix src tests`,
  `uvx ruff format --check src tests`, and `uv run mypy src`.
- Use `uv run ddon-dwarf-reconstructor` as the canonical entry point. If compatibility entry points
  remain, test that they produce byte-identical exports.
- Real ELF tests are opt-in and must use explicit local paths. Never commit game binaries, dump
  files, generated headers, runtime caches, or credentials.
- The inputs for an identified DDON build are immutable. Retain deterministic SQLite indexes,
  symbol/header caches, and exports locally so fresh-process warm reruns stay fast; untracked and
  rebuildable does not mean routinely disposable.
- Key durable artifacts by source identity plus producer/schema/configuration identity, validate
  before reuse, and publish atomically. Routine cleanup must preserve them; make purge, repair, or
  rebuild narrowly targeted and explicit.

## Local acceptance artifact

- The PS4 `02020005` compressed LLVM DWARF dump is available at
  `D:\research\DDON-binaries\IDA9.3\PS4_DDON_02020005_2016_12_21\DDOORBIS.elf.llvmdwarfdump.zst`.
- It is about 1.09 GB compressed and more than 30 GB expanded. Validate compressed-dump changes
  against this artifact instead of assuming that only fixtures are available.
- The primary development machine has 64 GB RAM and a Ryzen 7800X3D. A resource-heavy explicit
  bootstrap is acceptable when it produces a persistent, source-bound index and makes subsequent
  lookups fast. Do not impose that bootstrap cost on every invocation.

## Change discipline

Preserve unrelated edits. Add focused tests for DIE traversal and evidence fidelity. Cache entries
must be fingerprinted to their inputs and written atomically. Any optimization must preserve
qualified names, inheritance, field offsets, sizes, source locations, DIE offsets, and deterministic
ordering.

## Spec-driven workflow

- Spec Kit 0.15.1 is initialized for Copilot skills mode under `.specify/` and
  `.github/skills/speckit-*/`.
- Project principles live in `.specify/memory/constitution.md`; feature intent and
  implementation artifacts live under `specs/<feature>/`.
- For cross-module behavior changes, use the feature sequence
  `/speckit-specify`, `/speckit-clarify`, `/speckit-plan`, `/speckit-tasks`,
  `/speckit-analyze`, implementation, and `/speckit-converge` as applicable.
- Keep ELF inputs, expanded dumps, SQLite sidecars, generated headers, caches, and
  logs outside Spec Kit feature directories and source control.
- Every task must name exact source/test paths and a validation tier; unresolved
  evidence and deferred compiler prerequisites belong in the feature artifacts.
