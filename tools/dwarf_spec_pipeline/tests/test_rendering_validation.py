from __future__ import annotations

import json

import pytest

from dwarf_spec_pipeline.models import (
    CodeBlock,
    Section,
    SourceLocation,
    SourceMetadata,
    SpecificationDocument,
    SpecificationIdentity,
    Table,
    TableReferenceBlock,
)
from dwarf_spec_pipeline.rendering import render_json, render_markdown
from dwarf_spec_pipeline.validation import validate_document


@pytest.mark.unit
def test_renderers_are_deterministic_and_json_matches_schema(schema_path) -> None:  # type: ignore[no-untyped-def]
    location = SourceLocation(source_id="dwarf2", intermediate="html", block_index=1)
    document = SpecificationDocument(
        schema_version=1,
        parser_version="0.1.0",
        specification=SpecificationIdentity(version=2, title="DWARF Version 2"),
        source=SourceMetadata(
            source_id="dwarf2",
            filename="dwarf.v2.mm",
            format="mm",
            url="https://dwarfstd.org/doc/dwarf.v2.mm",
            source_page="https://dwarfstd.org/doc/",
            sha256="0" * 64,
        ),
        sections=[
            Section(
                id="section-1",
                number="1",
                title="Introduction",
                level=1,
                blocks=[
                    CodeBlock(text="DW_OP_const1u 0x01\nDW_OP_drop", source=location),
                    TableReferenceBlock(table_id="dwarf2-table-001", source=location),
                ],
                source=location,
            )
        ],
        tables=[
            Table(
                id="dwarf2-table-001",
                caption="Table 1. Operations",
                headers=["Name", "Value"],
                rows=[["DW_OP_drop", "0x13"]],
                spans=[],
                source=location,
            )
        ],
        constants=[],
        omissions=[],
        statistics={
            "source_block_count": 2,
            "section_count": 1,
            "table_count": 1,
            "table_row_count": 1,
            "constant_count": 0,
            "omission_count": 0,
        },
    )

    json_text = render_json(document)
    markdown_text = render_markdown(document)

    assert json_text == render_json(document)
    assert markdown_text == render_markdown(document)
    assert json.loads(json_text)["specification"]["version"] == 2
    assert "DW_OP_const1u" in markdown_text
    assert "Table 1. Operations" in markdown_text
    assert "![" not in markdown_text
    validate_document(document, schema_path)
