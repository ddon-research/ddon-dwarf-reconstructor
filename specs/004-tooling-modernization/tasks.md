# Tasks: Tooling Modernization

## CLI

- [x] Replace root argparse parsing with a unified Typer command tree.
- [x] Convert durable artifact operations to a typed Typer sub-application.
- [x] Convert the standalone DWARF specification CLI to Typer.
- [x] Add CliRunner coverage for help, version, typed options, invalid combinations, JSON output,
  and exact-path purge behavior.

## Toolchain

- [x] Replace mypy configuration and dependencies with curated Pyrefly configuration and stubs.
- [x] Add deptry mappings and clean dependency gates for both project boundaries.
- [x] Replace Makefile automation with root and nested justfiles.
- [x] Update uv lockfiles, CI, VS Code settings, action pinning, and Dependabot configuration.

## Documentation and acceptance

- [x] Synchronize active instructions, contracts, quickstarts, READMEs, architecture/testing docs,
  and Langfuse recipes.
- [x] Run focused CLI tests, Ruff, Pyrefly, deptry, and nested tool checks.
- [ ] Run the explicit PS4/compiler/performance tier when the local acceptance environment is
  intentionally selected.
