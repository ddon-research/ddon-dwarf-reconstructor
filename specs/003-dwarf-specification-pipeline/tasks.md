# Tasks: Rebuild the DWARF Specification Pipeline

- [x] Add the standalone tool index and project metadata/lockfile.
- [x] Lock official DWARF 2 `.mm`, DWARF 3 `.doc`, and DWARF 4 `.doc` sources
  with SHA-256 provenance.
- [x] Implement checksum acquisition, offline mode, Groff/LibreOffice
  conversion, ordered DOCX/HTML readers, and converter-artifact cleanup.
- [x] Implement typed canonical models, JSON Schema validation, normalized
  tables/spans, constants, aliases, omissions, and extraction statistics.
- [x] Implement deterministic JSON/Markdown rendering and manifest hashes.
- [x] Implement atomic output-directory publication and rollback coverage.
- [x] Add unit, deterministic integration, CLI/error-path, and opt-in
  official-artifact tests.
- [x] Add Debian Dockerfile, Compose configuration, and CI quality job.
- [x] Regenerate DWARF 2/3/4 JSON, Markdown, and manifest artifacts from the
  locked official sources.
- [x] Remove the legacy heredoc/Rust shell pipeline and stale generated Rust/
  constant outputs.
- [x] Synchronize architecture, testing, README, tool, and feature
  documentation.

## Validation record

- `uv run --project tools/dwarf_spec_pipeline --extra dev pytest`: passed.
- Standalone Ruff check/format and mypy: passed.
- `docker compose ... config`: passed.
- Official-source Compose build for DWARF 2/3/4: passed.
- `DWARF_SPEC_OFFICIAL=1` integration assertion: passed.
