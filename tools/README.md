# Repository Tools

This directory contains development and research tools that support the DDON
DWARF reconstructor without becoming part of the runtime package.

## Tools

- [`dwarf_spec_pipeline/`](dwarf_spec_pipeline/) converts the official DWARF
  2, 3, and 4 source documents into deterministic, structured JSON and clean
  Markdown artifacts.
- [`sonar/`](sonar/) contains the root checkout's typed SonarQube/MSVC
  preparation adapter. Invoke it through `uv run just sonar-validate`,
  `uv run just sonar-capture`, or its Python module; it is not a separately
  installed runtime tool.

The DWARF specification pipeline owns its own Python project metadata, lockfile,
tests, and operational documentation. Repository-wide behavior and durable
artifacts remain documented in `docs/` and the relevant Spec Kit feature
directory.
