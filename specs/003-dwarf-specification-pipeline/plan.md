# Implementation Plan: Rebuild the DWARF Specification Pipeline

## Architecture

```text
locked manifest
    -> checksum-verified source cache
    -> Docker converter (.mm -> HTML, .doc -> DOCX)
    -> ordered intermediate readers
    -> canonical Pydantic model
    -> table/constant normalization
    -> JSON Schema validation
    -> Markdown + JSON + manifest
    -> atomic directory publication
```

## Source layout

- `tools/README.md`: repository tool index.
- `tools/dwarf_spec_pipeline/pyproject.toml` and `uv.lock`: standalone
  dependency and quality boundary.
- `config/sources.json`: source lock and provenance inputs.
- `src/dwarf_spec_pipeline/`: typed acquisition, conversion, readers,
  normalization, rendering, validation, CLI, and orchestration modules.
- `schema/dwarf-specification.schema.json`: public JSON contract.
- `tests/`: isolated and deterministic integration tests.
- `Dockerfile` and `compose.yaml`: canonical converter environment.
- `docs/knowledge-base/dwarf-specification/generated/`: authoritative
  checked-in deliverables.

## Publication design

Each build writes all selected version artifacts to a sibling temporary
directory. The previous output directory is renamed to a temporary backup,
then the complete stage is renamed into place; a failed swap restores the
previous directory. Every artifact is UTF-8 with LF line endings and the
manifest hashes the exact bytes.

## Validation tiers

- Tier 1: standalone locked `uv` Ruff, formatting, Pyrefly, deptry, and unit tests through `just`.
- Tier 2: deterministic mocked-converter build and schema validation.
- Tier 3: `docker compose config` and official-source Compose build for all
  three locked sources, followed by the opt-in coverage assertion.

## Documentation synchronization

The implementation updates the dwarf-specification README, knowledge-base
index, docs index, architecture, testing guide, Copilot adapter, tool index,
CI workflow, and this feature directory. The runtime package remains a
consumer of neither presentation files nor generated Rust modules.
