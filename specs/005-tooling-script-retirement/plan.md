# Implementation Plan: Tooling Script Retirement

## Source and boundary changes

- Move quality checkers to `tests/support/quality/` and deterministic output manifests to
  `tests/support/regression/`.
- Replace the Sonar PowerShell entry point with `tools/sonar/prepare_msvc_analysis.py`; it remains
  a Windows-specific checkout tool and does not enter the runtime wheel.
- Keep runtime packaging rooted at `src/ddon_dwarf_reconstructor` with the existing Typer console
  script and exact CPython 3.14.6 requirement.

## Task-runner and packaging changes

- Make `just` invoke the moved Python modules and add `sonar-validate`, `sonar-capture`, and
  `package-smoke` recipes.
- Run the packaging smoke test in temporary UV tool directories from outside the checkout.
- Exclude the packaging marker from normal test/coverage recipes and run it explicitly in CI and
  the `ci` recipe.

## Documentation synchronization

- Update README, AGENTS, Copilot instructions, architecture/testing/Sonar documentation, CI, and
  affected historical feature references.
- Preserve Spec Kit-owned script paths and document the new feature in this directory.
