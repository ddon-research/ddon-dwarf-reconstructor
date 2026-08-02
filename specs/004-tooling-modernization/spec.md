# Feature Specification: Tooling Modernization

**Feature Branch**: `004-tooling-modernization`
**Status**: Implemented

## Goal

Provide one reproducible, typed development loop for the root reconstructor and the standalone
DWARF specification pipeline without changing generated evidence or durable-artifact semantics.

## Requirements

- **TM-001**: The root package MUST expose one Typer command tree with `generate`,
  `export-knowledge`, and `artifacts` commands. Repeated `--symbol` and `--symbols-file` MUST be
  mutually exclusive.
- **TM-002**: The specification pipeline MUST expose its `build`, `validate`, and `sources`
  commands through Typer.
- **TM-003**: Pyrefly MUST be the authoritative type checker for `src`, typed test support, and
  checkout-local operational Python modules;
  both projects MUST pass at warning severity without a legacy-mode fallback.
- **TM-004**: deptry MUST pass for both project boundaries with explicit first-party and
  package-to-module mappings.
- **TM-005**: just MUST be the canonical task runner, and CI MUST invoke locked uv environments
  through just recipes. The Makefile MUST NOT remain as a second task-runner source of truth.
- **TM-006**: Active instructions, contracts, quickstarts, READMEs, CI workflows, and testing
  documentation MUST describe the same commands and validation loop.

## Non-goals

- Changing DWARF traversal, evidence authority, cache schemas, generated-header syntax, knowledge
  export formats, or source identity behavior.
- Making real PS4 assets part of the default test or CI path.
- Raising Pyrefly to strict/all presets in this migration.

## Acceptance

The feature is complete when `uv lock --check`, `uv sync --frozen`, `uv run just check`, the
non-performance test suite, coverage gates, root and nested deptry/Pyrefly checks, and package
builds pass. Focused CLI tests MUST cover help, version, command mapping, invalid option
combinations, artifact JSON, and exact-path purge protection.
