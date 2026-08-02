# Tasks: Tooling Script Retirement

## Retirement scope

- [x] Move quality and regression helpers into `tests/support` and update imports.
- [x] Convert Sonar/MSVC preparation from PowerShell to the typed Python module.
- [x] Remove the repository-owned root `scripts/` files.

## Task runner and packaging

- [x] Update `justfile`, Ruff, Pyrefly, and pytest marker configuration.
- [x] Add the isolated `uv tool install` packaging smoke test.
- [x] Add focused Sonar adapter tests for discovery, command construction, validation, and failure
  modes.

## Documentation and validation

- [x] Synchronize active documentation, instructions, CI, and Spec Kit artifacts.
- [x] Run focused tests, `just check`, package smoke, package build, and required full gates.
