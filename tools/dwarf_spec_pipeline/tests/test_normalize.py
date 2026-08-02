from __future__ import annotations

import pytest

from dwarf_spec_pipeline.models import CodeBlock, ParagraphBlock, TableReferenceBlock
from dwarf_spec_pipeline.normalize import build_document
from dwarf_spec_pipeline.readers import RawBlock, RawSpan


@pytest.mark.unit
def test_normalization_removes_toc_page_furniture_and_index(source) -> None:  # type: ignore[no-untyped-def]
    raw_blocks = [
        RawBlock(kind="heading", text="Table of Contents", level=1, index=0),
        RawBlock(kind="paragraph", text="1. Introduction ........ 1", index=1),
        RawBlock(kind="paragraph", text="DWARF Debugging Information Format", index=2),
        RawBlock(kind="paragraph", text="DWARF Debugging Information Format", index=3),
        RawBlock(kind="paragraph", text="DWARF Debugging Information Format", index=4),
        RawBlock(kind="heading", text="1. Introduction", level=1, index=5),
        RawBlock(kind="paragraph", text="The specification begins here.", index=6),
        RawBlock(kind="code", text="DW_OP_const1u 0x01\nDW_OP_drop", index=7),
        RawBlock(
            kind="table",
            rows=(("Name", "Value"), ("DW_TAG_compile_unit", "0x11")),
            spans=(RawSpan(0, 0, 0, 1),),
            caption="Table 1. Tags",
            index=8,
        ),
        RawBlock(kind="heading", text="Index", level=1, index=9),
        RawBlock(kind="paragraph", text="compile_unit, 42", index=10),
    ]

    document = build_document(source, raw_blocks)

    assert [section.title for section in document.sections] == ["Introduction"]
    blocks = document.sections[0].blocks
    assert isinstance(blocks[0], ParagraphBlock)
    assert isinstance(blocks[1], CodeBlock)
    assert isinstance(blocks[2], TableReferenceBlock)
    assert document.tables[0].caption == "Table 1. Tags"
    assert document.constants[0].name == "DW_TAG_compile_unit"
    omission_kinds = {omission.kind for omission in document.omissions}
    assert {"table_of_contents", "page_furniture", "index"} <= omission_kinds
    assert document.statistics.omission_count >= 5
