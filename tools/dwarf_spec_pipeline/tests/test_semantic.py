from __future__ import annotations

from pathlib import Path

import pytest

from dwarf_spec_pipeline.models import (
    ParagraphBlock,
    Section,
    SourceMetadata,
    SpecificationDocument,
    SpecificationIdentity,
    Table,
)
from dwarf_spec_pipeline.semantic import build_semantic_index, load_documents


def _document(version: int, sections: list[Section], tables: list[Table]) -> SpecificationDocument:
    return SpecificationDocument(
        schema_version=1,
        parser_version="0.1.0",
        specification=SpecificationIdentity(version=version, title=f"DWARF {version}"),
        source=SourceMetadata(
            source_id=f"dwarf{version}",
            filename=f"dwarf{version}.doc",
            format="doc",
            url="https://example.test/source",
            source_page="https://example.test/",
            sha256="0" * 64,
        ),
        sections=sections,
        tables=tables,
        constants=[],
        omissions=[],
        statistics={
            "source_block_count": 1,
            "section_count": len(sections),
            "table_count": len(tables),
            "table_row_count": sum(len(table.rows) for table in tables),
            "constant_count": 0,
            "omission_count": 0,
        },
    )


@pytest.mark.unit
@pytest.mark.regression
def test_semantic_index_extracts_paragraph_encoded_dwarf2_relationships(tmp_path: Path) -> None:
    sections = [
        Section(
            id="section-encodings",
            number="7.5.4",
            title="Attribute Encodings",
            level=1,
            blocks=[
                ParagraphBlock(
                    text=(
                        "DW_AT_containing_type 0x1d reference "
                        "DW_AT_data_member_location 0x38 block, reference"
                    )
                )
            ],
        ),
        Section(
            id="section-tags",
            number="Appendix 1",
            title="Current Attributes by Tag Value",
            level=1,
            blocks=[
                ParagraphBlock(
                    text=(
                        "TAG NAME APPLICABLE ATTRIBUTES "
                        "DW_TAG_class_type DW_AT_name DW_AT_byte_size "
                        "DW_TAG_ptr_to_member_type DW_AT_containing_type DW_AT_type"
                    )
                )
            ],
        ),
    ]
    index = build_semantic_index([_document(2, sections, [])], source_root=tmp_path)
    version = index.versions[0]

    assert version.attribute_encodings["DW_AT_containing_type"].classes == ["reference"]
    assert version.attribute_encodings["DW_AT_data_member_location"].classes == [
        "block",
        "reference",
    ]
    assert version.tag_applicability["DW_TAG_ptr_to_member_type"] == [
        "DW_AT_containing_type",
        "DW_AT_type",
    ]
    assert "DW_AT_containing_type" not in version.tag_applicability["DW_TAG_class_type"]


@pytest.mark.unit
def test_semantic_index_extracts_tabular_descriptions_and_code_references(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text('TAG = "DW_TAG_class_type"\nATTR = "DW_AT_high_pc"\n', encoding="utf-8")
    sections = [Section(id="section-1", number="1", title="Intro", level=1, blocks=[])]
    tables = [
        Table(
            id="attributes",
            caption=None,
            headers=["Attribute", "Identifies or Specifies"],
            rows=[["DW_AT_high_pc", "end of a range"]],
            spans=[],
        ),
        Table(
            id="forms",
            caption=None,
            headers=["Attribute Class", "General Use and Encoding"],
            rows=[["constant", "integer constant"]],
            spans=[],
        ),
        Table(
            id="encodings",
            caption=None,
            headers=["Attribute name", "Value", "Classes"],
            rows=[["DW_AT_high_pc", "0x12", "address, constant"]],
            spans=[],
        ),
        Table(
            id="applicability",
            caption=None,
            headers=["TAG Name", "Applicable Attributes"],
            rows=[["DW_TAG_subprogram", "DW_AT_low_pc DW_AT_high_pc"]],
            spans=[],
        ),
    ]
    index = build_semantic_index([_document(4, sections, tables)], source_root=tmp_path)
    version = index.versions[0]

    assert version.attribute_descriptions["DW_AT_high_pc"] == "end of a range"
    assert version.form_descriptions["constant"] == "integer constant"
    assert version.attribute_encodings["DW_AT_high_pc"].classes == ["address", "constant"]
    assert index.code_references["DW_TAG"]["DW_TAG_class_type"] == ["sample.py"]


@pytest.mark.integration
@pytest.mark.functional
@pytest.mark.regression
def test_checked_in_specifications_expose_the_relationships_used_by_the_audit() -> None:
    root = Path(__file__).parents[3]
    generated = root / "docs" / "knowledge-base" / "dwarf-specification" / "generated"
    index = build_semantic_index(
        load_documents(generated), source_root=root / "src", artifact_dir=generated
    )
    dwarf2 = next(version for version in index.versions if version.version == 2)
    dwarf4 = next(version for version in index.versions if version.version == 4)

    assert dwarf2.attribute_encodings["DW_AT_name"].classes == ["string"]
    assert "DW_AT_containing_type" in dwarf2.tag_applicability["DW_TAG_ptr_to_member_type"]
    assert "DW_AT_containing_type" not in dwarf2.tag_applicability["DW_TAG_class_type"]
    assert dwarf4.attribute_encodings["DW_AT_high_pc"].classes == ["address", "constant"]
