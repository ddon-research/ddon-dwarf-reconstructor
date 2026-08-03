# DWARF Specification Pipeline

Standalone tool that converts the locked DWARF 2, 3, and 4 source documents into deterministic
JSON and Markdown artifacts. Source documents stay in a checksum-verified local cache and are not
repository artifacts.

## Local development

```text
uv sync --python 3.14.6
uv run just test-unit
uv run just test-integration
uv run just test
uv run just test-official
uv run just check
uv run dwarf-spec-pipeline --help
```

Run the commands below from the repository root. `--directory` changes the command's working
directory to this project, so paths back to the root use `../../`:

```text
uv run --directory tools/dwarf_spec_pipeline dwarf-spec-pipeline build --offline \
  --manifest config/sources.json \
  --output-dir ../../docs/knowledge-base/dwarf-specification/generated \
  --work-dir ../../.cache/dwarf_spec_pipeline \
  --schema schema/dwarf-specification.schema.json
uv run --directory tools/dwarf_spec_pipeline dwarf-spec-pipeline validate \
  --output-dir ../../docs/knowledge-base/dwarf-specification/generated
uv run --directory tools/dwarf_spec_pipeline dwarf-spec-pipeline sources
uv run --directory tools/dwarf_spec_pipeline dwarf-spec-pipeline audit \
  --output-dir ../../docs/knowledge-base/dwarf-specification/generated --source-root ../../src
```

`--manifest`, `--output-dir`, `--work-dir`, `--schema`, repeated `--version 2|3|4`, and
`--cache-dir` retain their existing meanings. Use Docker Compose for the `.doc` and `.mm`
conversion environment:

```text
docker compose -f compose.yaml run --rm dwarf-spec-pipeline
```

## Contracts

- `config/sources.json` locks source URLs, filenames, formats, and SHA-256 values.
- `schema/dwarf-specification.schema.json` defines the published JSON shape.
- `generated/dwarf{2,3,4}.json` and `.md` are deterministic published artifacts.
- `generated/semantic-index.json` and `.md` are derived, searchable vocabulary and relationship
  artifacts. They recover paragraph-form DWARF2 tables as well as normal tables from DWARF3/4.
- `generated/manifest.json` records output hashes and source identity, including the semantic index.

`audit` validates the canonical JSON documents, records version availability for `DW_TAG`,
`DW_AT`, `DW_FORM`, `DW_OP`, and `DW_LANG` names, extracts attribute encodings and tag
applicability, and inventories source-code references. It does not make the runtime import the
specification project.

The project uses Ruff, Pyrefly, deptry, and just through its frozen uv environment. Tests and
quality checks do not download sources unless an explicit build requests it; `--offline` requires
an already verified local cache. The test suite uses the shared project vocabulary: `unit`,
`integration`, and `acceptance` scopes plus `functional`, `regression`, and `non_functional`
purposes. `just test` includes deterministic local integration tests; `just test-official` is an
explicit check for generated official artifacts.
