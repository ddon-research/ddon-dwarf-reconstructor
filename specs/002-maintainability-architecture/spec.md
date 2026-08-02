# Feature Specification: Maintainability and Architecture Hardening

**Feature Branch**: `002-maintainability-architecture`

**Status**: Implemented and acceptance-verified

## Goal

Improve maintainability of the Python source and test suites while preserving
evidence fidelity, deterministic generated headers, source-bound artifacts, and
warm-cache performance.

## Requirements

- **MA-001**: Python modules under `src/` and `tests/` MUST be at most 400
  physical lines, classes at most 250 lines, and functions/methods at most 75
  lines.
- **MA-002**: Production and test functions MUST have McCabe complexity no
  greater than 10 unless the behavior is decomposed.
- **MA-003**: Domain code MUST NOT depend on infrastructure adapters, SQLite,
  zstd, Orbis process models, or concrete `pyelftools` orchestration.
- **MA-004**: Definition selection, source identity, type classification,
  method evidence, and special-header rendering MUST have one canonical policy
  implementation each.
- **MA-005**: Existing public generation methods and artifact wire formats MUST
  remain compatible unless a focused migration contract is added.
- **MA-006**: Fixture and real-artifact generated headers MUST remain byte-
  identical to pre-refactor baselines.
- **MA-007**: Coverage MUST reach at least 80% overall, with at least 80% line
  and 70% branch coverage for parsing, generation, orchestration, and artifact
  modules.
- **MA-008**: Unit, full non-performance, Ruff, format, Mypy, structure,
  boundary, output-regression, and explicit real-artifact checks MUST be
  documented and runnable.

## Non-goals

- Reconstructing source constructs absent from DWARF evidence.
- Changing generated header syntax, declaration ordering, cache schemas, or
  knowledge-export formats without an explicit compatibility test.
- Committing proprietary ELF files, compressed dumps, generated headers, caches,
  or runtime reports.

## Acceptance

The feature is complete only when the current unit and non-performance suites
remain green, all structural limits pass, static checks pass, output manifests
match, and the real PS4 acceptance run shows no correctness or performance
regression.

## Evidence recorded during implementation

- `394` unit tests pass; `408` non-performance tests pass with one opt-out.
- Total coverage is `88.5%` lines and `74.8%` branches. Parsing, generation,
  orchestration, and artifact groups all exceed their enforced thresholds.
- Ruff, formatting, Mypy, structure, boundary, compile, and focused Prospector
  checks pass.
- The five retained fixture headers match the pre-refactor manifest exactly
  through both `ddon-dwarf-reconstructor` and `python main.py`.
- The explicit real PS4 `rLayout` warm run produced a 20,039-byte header, and a
  second fresh process matched its SHA-256 manifest. The source identity is
  recorded externally at `D:\ddon-dwarf-reconstructor-acceptance`.
- A fresh cold sidecar rebuild completed in 295.6 seconds, published a
  206,422,016-byte source-bound SQLite index atomically, and produced a header
  whose manifest matches the warm run exactly.
- The opt-in real performance test passed in 4.74 seconds against the same
  source-bound dump/index configuration and 15-second warm budget.
