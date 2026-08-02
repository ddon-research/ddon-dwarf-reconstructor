# Feature Specification: Tooling Script Retirement

**Feature Branch**: `005-tooling-script-retirement`
**Status**: Implemented

## Goal

Keep repository maintenance aligned with the just/Python workflow while making the reconstructor
usable as an isolated uv-installed command-line tool.

## Requirements

- **TSR-001**: The repository-owned root `scripts/` directory MUST not contain maintenance or
  platform workflow entry points. Spec Kit-owned `.specify/scripts` and `.github/skills` assets are
  outside this requirement.
- **TSR-002**: Standard checks MUST be orchestrated by the root `justfile`; custom Python checks
  MUST be invokable as Python modules from the checkout.
- **TSR-003**: Sonar/MSVC preparation MUST preserve wrapper discovery, Visual Studio discovery,
  validation-directory defaults, compilation-database checks, and truthful failure behavior.
- **TSR-004**: `uv tool install . --python 3.14.6` MUST expose the packaged
  `ddon-dwarf-reconstructor` command independently of the checkout source path.
- **TSR-005**: Active instructions, documentation, CI, tests, and Spec Kit artifacts MUST use the
  same just/Python/module-based workflow.

## Non-goals

- Changing DWARF traversal, generated evidence, cache formats, artifact semantics, or runtime
  Typer commands.
- Removing the root `main.py` native-build launcher.
- Making Sonar/MSVC validation part of the default test path on machines without Visual Studio.

## Acceptance

The feature is complete when the moved helper tests, Sonar adapter tests, isolated uv-tool smoke
test, root quality gate, non-packaging test and coverage gates, package build, and documentation
references pass. The root `scripts/` path is absent from tracked project files except for the
literal `project.scripts` TOML key and Spec Kit-owned tooling paths.
