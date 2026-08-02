# DWARF Specification Pipeline

This standalone tool converts the official DWARF 2, 3, and 4 source documents
into deterministic, machine-readable JSON and clean Markdown. The source
documents are retained only in a checksum-verified local cache; they are not
repository artifacts.

The supported runtime is regular CPython 3.14.6 managed by uv.

## Full build

The full build uses Docker Compose so the legacy `.doc` and `.mm` converters are
consistent on Windows and Ubuntu:

```text
docker compose -f tools/dwarf_spec_pipeline/compose.yaml run --rm dwarf-spec-pipeline
```

The container downloads the locked sources, converts `.doc` to `.docx` with
LibreOffice and `.mm` to HTML with Groff, then runs the Python readers and
publishes to `docs/knowledge-base/dwarf-specification/generated/`.

## Local development

```text
uv sync --project tools/dwarf_spec_pipeline --python 3.14.6 --extra dev
uv run --directory tools/dwarf_spec_pipeline --python 3.14.6 --extra dev pytest
uv run --directory tools/dwarf_spec_pipeline --python 3.14.6 --extra dev ruff check src tests
uv run --directory tools/dwarf_spec_pipeline --python 3.14.6 --extra dev mypy src
```

The Python package can also parse pre-converted HTML and DOCX fixtures without
Docker. Raw-source conversion requires the tools supplied by the Compose image.

## Source and artifact contracts

- `config/sources.json` locks the official URL, source filename, format, and
  SHA-256 for each specification.
- `schema/dwarf-specification.schema.json` defines the published JSON shape.
- `generated/dwarf{2,3,4}.json` is the canonical structured artifact.
- `generated/dwarf{2,3,4}.md` is the human- and AI-readable rendering.
- `generated/manifest.json` records deterministic artifact hashes and source
  identity.

Use `--offline` to require an already verified source cache. Updating a source
checksum is an intentional manifest change, not an automatic fallback.
