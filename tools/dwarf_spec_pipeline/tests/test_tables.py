from __future__ import annotations

import pytest

from dwarf_spec_pipeline.models import SourceLocation, Table, TableSpan
from dwarf_spec_pipeline.tables import extract_constants, normalize_table


@pytest.mark.unit
def test_table_normalization_detects_headers_and_preserves_spans(
    source_location: SourceLocation,
) -> None:
    table = normalize_table(
        "dwarf2-table-001",
        (("Name", "Value", "Meaning"), ("DW_TAG_compile_unit", "0x11", "unit")),
        (TableSpan(start_row=0, end_row=0, start_column=0, end_column=2),),
        source_location,
        "Table 1. Tags",
    )

    assert table.headers == ["Name", "Value", "Meaning"]
    assert table.rows == [["DW_TAG_compile_unit", "0x11", "unit"]]
    assert table.spans[0].end_column == 2
    assert table.source == source_location


@pytest.mark.unit
def test_constant_extraction_handles_continuations_duplicate_values_and_aliases(
    source_location: SourceLocation,
) -> None:
    table = Table(
        id="dwarf2-table-002",
        caption="Forms",
        headers=["Name", "Value", "Meaning"],
        rows=[
            ["DW_FORM_addr", "0x01", "address"],
            ["DW_FORM_ref_addr", "0x01", "reference address"],
            ["DW_AT_name"],
            ["0x03", "name"],
        ],
        spans=[],
        source=source_location,
    )

    constants = extract_constants([table])

    assert [(constant.name, constant.value, constant.value_text) for constant in constants] == [
        ("DW_AT_name", 3, "0x03"),
        ("DW_FORM_addr", 1, "0x01"),
        ("DW_FORM_ref_addr", 1, "0x01"),
    ]
    form_constants = [constant for constant in constants if constant.namespace == "DW_FORM"]
    assert form_constants[0].aliases == ["DW_FORM_ref_addr"]
    assert form_constants[1].aliases == ["DW_FORM_addr"]
    assert form_constants[0].source == source_location
