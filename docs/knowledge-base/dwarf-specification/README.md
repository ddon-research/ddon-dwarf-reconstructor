# DWARF Specification Knowledge Base

The authoritative DWARF 2, 3, and 4 specifications are published here as
deterministic, machine-readable JSON and readable Markdown. The source
documents remain official `.mm` and `.doc` downloads; PDFs, DOCX exports,
Rust constant modules, and the retired shell pipeline are not part of the
artifact contract.

## Published artifacts

The checked-in deliverables are under [`generated/`](generated/):

| Version | Canonical JSON | Markdown rendering |
| --- | --- | --- |
| DWARF 2 | [`dwarf2.json`](generated/dwarf2.json) | [`dwarf2.md`](generated/dwarf2.md) |
| DWARF 3 | [`dwarf3.json`](generated/dwarf3.json) | [`dwarf3.md`](generated/dwarf3.md) |
| DWARF 4 | [`dwarf4.json`](generated/dwarf4.json) | [`dwarf4.md`](generated/dwarf4.md) |

[`manifest.json`](generated/manifest.json) records the source identity and
SHA-256 of every published JSON/Markdown artifact, including the derived semantic index. The
JSON shape is defined
by the [DWARF specification JSON schema](https://github.com/ddon-research/ddon-dwarf-reconstructor/blob/main/tools/dwarf_spec_pipeline/schema/dwarf-specification.schema.json).

The review-oriented [`semantic-index.json`](generated/semantic-index.json) and
[`semantic-index.md`](generated/semantic-index.md) normalize the DWARF 2/3/4 vocabulary into
versioned namespaces, attribute encodings, attribute-class descriptions, and tag applicability.
This is especially important for DWARF2, where the converter preserves some normative tables as
paragraph blocks rather than normalized table rows.

Each JSON document preserves ordered sections, paragraphs, lists, code,
normalized tables and merged-cell spans, structured constants, source
locations, omissions, and extraction statistics. Markdown is rendered from
that model and therefore does not perform a second presentation-level parse.

## Rebuild

Run from the repository root:

```text
docker compose -f tools/dwarf_spec_pipeline/compose.yaml run --rm dwarf-spec-pipeline
```

The Debian container supplies LibreOffice Writer for `.doc` → `.docx` and
Groff for `.mm` → HTML. Python parsing, normalization, rendering, and schema
validation run from the locked standalone `uv` project. Downloads and
conversion intermediates are stored in the ignored
`.cache/dwarf_spec_pipeline/` cache (or the named Compose volume).

For local parser work on pre-converted fixtures:

```text
uv sync --directory tools/dwarf_spec_pipeline --python 3.14.7 --locked
uv run --directory tools/dwarf_spec_pipeline just test
uv run --directory tools/dwarf_spec_pipeline just check
```

`--offline` makes a build require an already cached, checksum-verified source.
The locked inputs live in the repository's [sources.json](https://github.com/ddon-research/ddon-dwarf-reconstructor/blob/main/tools/dwarf_spec_pipeline/config/sources.json).

## Provenance and scope

The source catalog is maintained by the DWARF Standards Committee:

- [Official downloads](https://dwarfstd.org/download.html)
- [Official document index](https://dwarfstd.org/doc/)

The pipeline removes only table-of-contents/index material, repeated page
furniture, decorative media, and converter-only control text. Legal notices,
forewords, introductions, appendices, examples, and meaningful prose remain
in the generated artifacts. The outputs are reference material for the
reconstructor and are not imported as runtime Python dependencies.
