# Resume the architecture refactoring

This how-to serves the implementing agent. Read spec, tasks, handoff, measured evidence, and
the three contracts before changing production files. The pre-refactor output gate is required.

1. Confirm `git status --short` and the baseline snapshot; preserve unrelated changes.
2. Use regular CPython 3.14.7 and `uv sync --python 3.14.7 --locked`.
3. Use `.specify/scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks`.
4. Complete the current task's named tests and retain commands/results in measured-evidence.
5. After each slice run `uv run just test-unit`, `uv run just check`, and `uv run just test`.
6. Run `uv run just coverage-ci` and `uv run just audit` before final handoff. Run applicable
   packaging and nested gates from their project boundary.
7. Update tasks and handoff before ending an iteration. Do not mark absent evidence complete.

Use `--no-fix` on read-only Ruff probes because the project currently configures `fix = true`.
The normal `just lint` recipe already supplies `--no-fix`. Use the established docs tooling
installation and docs-api/docs-api-check/docs-check recipes for authored or module moves.
