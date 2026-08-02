# Canonical DWARF Artifact Contract

## JSON

Each `dwarf{2,3,4}.json` validates against
`tools/dwarf_spec_pipeline/schema/dwarf-specification.schema.json` and contains:

- `specification`: family, version, and title;
- `source`: source ID, filename, format, URL, source page, and SHA-256;
- `sections`: ordered hierarchy with paragraph, code, list, and table-reference
  blocks plus source locations;
- `tables`: stable ID, caption, headers, rows, merged-cell spans, and source;
- `constants`: namespace, name, integer value, normalized hex, original value
  text, meaning, aliases, table reference, and source;
- `omissions`: typed reason, description, and count;
- `statistics`: source block, section, table, row, constant, and omission
  counts;
- `schema_version` and `parser_version`.

Source locations use `source_id`, `intermediate` (`html` or `docx`), and the
ordered intermediate block index. Numeric values may be `null` when the
original value is symbolic or malformed; `value_text` is always retained.

## Markdown

The Markdown renderer consumes the validated JSON model. It emits stable
headings, readable escaped tables, fenced code, lists, source metadata, legal
notices, forewords, appendices, and examples. It does not emit image/media
links or reparse the raw converter output.

## Manifest

`generated/manifest.json` contains the schema/parser versions, the locked
source manifest entries, and sorted SHA-256 entries for each JSON and Markdown
artifact. It is deterministic and is checked by the `validate` CLI command.
