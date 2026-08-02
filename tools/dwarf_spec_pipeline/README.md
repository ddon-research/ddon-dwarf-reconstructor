# DWARF Specification Pipeline

Standalone tool that converts the locked DWARF 2, 3, and 4 source documents into deterministic
JSON and Markdown artifacts. Source documents stay in a checksum-verified local cache and are not
repository artifacts.

## Local development

```text
uv sync --python 3.14.6
uv run just test
uv run just check
uv run dwarf-spec-pipeline --help
```

The command tree is typed with Typer:

```text
uv run dwarf-spec-pipeline build --offline
uv run dwarf-spec-pipeline validate
uv run dwarf-spec-pipeline sources
```

`--manifest`, `--output-dir`, `--work-dir`, `--schema`, repeated `--version 2|3|4`, and
`--cache-dir` retain their existing meanings. Use Docker Compose for the legacy `.doc` and `.mm`
conversion environment:

```text
docker compose -f compose.yaml run --rm dwarf-spec-pipeline
```

## Contracts

- `config/sources.json` locks source URLs, filenames, formats, and SHA-256 values.
- `schema/dwarf-specification.schema.json` defines the published JSON shape.
- `generated/dwarf{2,3,4}.json` and `.md` are deterministic published artifacts.
- `generated/manifest.json` records output hashes and source identity.

The project uses Ruff, Pyrefly, deptry, and just through its frozen uv environment. Tests and
quality checks do not download sources unless an explicit build requests it; `--offline` requires
an already verified local cache.
