# Implementation Plan: Tooling Modernization

## Source and boundary changes

- Root CLI code lives in `src/ddon_dwarf_reconstructor/cli.py` and
  `src/ddon_dwarf_reconstructor/artifact_cli.py`; generation behavior remains in
  `src/ddon_dwarf_reconstructor/main.py` behind `GenerationOptions`.
- The standalone CLI remains under `tools/dwarf_spec_pipeline/src/dwarf_spec_pipeline/cli.py`.
- Root and nested `pyproject.toml` files own runtime dependencies, PEP 735 groups, Pyrefly, and
  deptry configuration. Each project retains its own lockfile.
- `justfile` and `tools/dwarf_spec_pipeline/justfile` own local automation; GitHub workflows call
  those recipes.

## Validation tiers

- Tier 1: focused Typer/CliRunner and existing unit tests, Ruff, Pyrefly warning checks, deptry,
  structure, and boundary checks.
- Tier 2: full non-performance tests, coverage group thresholds, package builds, and nested tool
  tests.
- Tier 3: explicit real-ELF, compiler, cold-index, and warm-cache determinism validation using
  external local paths.

## Documentation synchronization

The active README, architecture/testing documentation, CLI contract, quickstart, Python and agent
instructions, constitution, nested-tool README, workflows, and Langfuse recipes describe the same
Typer/just/Pyrefly/deptry loop. Completed historical evidence records retain their original
verification claims.
