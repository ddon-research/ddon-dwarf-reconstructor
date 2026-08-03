# Feature Specification: Rebuild the DWARF Specification Pipeline

## Status

Implemented. The feature records the contract for the standalone tool and its
checked-in DWARF 2/3/4 artifacts.

## Problem

The previous pipeline mixed shell orchestration, embedded heredoc programs,
PDF extraction, host package installation, and an obsolete Rust-generation
path. Its output retained presentation garbage and did not provide one stable
machine-readable representation for all supported specification versions.

## Goals

1. Preserve the official DWARF 2, 3, and 4 source content and provenance.
2. Produce deterministic, parseable JSON and readable Markdown artifacts.
3. Keep source acquisition, conversion, parsing, normalization, extraction,
   rendering, validation, and publication separately testable.
4. Make full conversion reproducible in Debian Docker Compose on Windows and
   Ubuntu while keeping Python development ordinary and `uv`-managed.
5. Publish source and artifact checksums and explicit omission statistics.

## Functional requirements

- Source URLs, filenames, formats, and SHA-256 values are locked in
  `tools/dwarf_spec_pipeline/config/sources.json`.
- `.mm` sources are converted with Groff; `.doc` sources are converted with
  LibreOffice to DOCX. The host does not need either converter installed.
- The canonical document model includes identity, source metadata, ordered
  sections/content blocks, normalized tables/spans, constants, source
  locations, omissions, and extraction statistics.
- A deterministic semantic index is published beside the canonical documents.
  It derives versioned DWARF vocabulary, attribute encodings, form
  descriptions, tag applicability, and source-code references without becoming
  a runtime dependency.
- Paragraph-form DWARF2 attribute/applicability tables are included in the
  semantic index even when the converter cannot represent them as normalized
  table rows.
- Constants retain original value text, parsed numeric value when possible,
  normalized hexadecimal value, meaning, aliases, table ID, and provenance.
- Only generated table-of-contents/index material, repeated page furniture,
  decorative media, and converter-only control text are omitted.
- JSON is validated against the checked-in JSON Schema before publication.
- The semantic index is validated as a typed report and its JSON/Markdown
  hashes are included in the artifact manifest.
- A complete output directory is staged and atomically swapped into place.
- No generated Rust constants or retired `pipeline.sh` output is part of the
  public contract.

## Non-goals

- DWARF 5 support.
- Runtime dependence on the specification project.
- Committing raw downloads, expanded source documents, conversion caches, or
  converter-installed binaries.

## Acceptance criteria

- Unit tests cover DOCX order/merged cells, HTML cleanup, Groff artifacts,
  headings, table continuation, constants, aliases, malformed inputs,
  checksum failures, offline mode, missing tools, and atomic publication.
- Two builds from identical locked intermediates are byte-identical.
- An opt-in official-source Docker build validates DWARF 2/3/4 coverage and
  rejects converter table/media artifacts.
- The generated JSON, Markdown, manifest, schema, and repository docs are
  synchronized with this contract.
