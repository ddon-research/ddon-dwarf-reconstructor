"""Typed public models for the generated DWARF specification artifacts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceLocation(StrictModel):
    source_id: str
    intermediate: Literal["html", "docx"]
    block_index: int | None = None
    page: int | None = None
    figure: str | None = None


class ParagraphBlock(StrictModel):
    kind: Literal["paragraph"] = "paragraph"
    text: str
    source: SourceLocation | None = None


class CodeBlock(StrictModel):
    kind: Literal["code"] = "code"
    text: str
    language: str | None = None
    source: SourceLocation | None = None


class ListBlock(StrictModel):
    kind: Literal["list"] = "list"
    ordered: bool
    items: list[str]
    source: SourceLocation | None = None


class TableReferenceBlock(StrictModel):
    kind: Literal["table_ref"] = "table_ref"
    table_id: str
    source: SourceLocation | None = None


ContentBlock = ParagraphBlock | CodeBlock | ListBlock | TableReferenceBlock


class Section(StrictModel):
    id: str
    number: str | None
    title: str
    level: int = Field(ge=0, le=6)
    blocks: list[ContentBlock]
    source: SourceLocation | None = None


class TableSpan(StrictModel):
    start_row: int = Field(ge=0)
    end_row: int = Field(ge=0)
    start_column: int = Field(ge=0)
    end_column: int = Field(ge=0)


class Table(StrictModel):
    id: str
    caption: str | None
    headers: list[str]
    rows: list[list[str]]
    spans: list[TableSpan]
    source: SourceLocation | None = None


class ConstantDefinition(StrictModel):
    namespace: str
    name: str
    value: int | None
    value_hex: str | None
    value_text: str
    meaning: str | None
    aliases: list[str]
    table_id: str
    source: SourceLocation | None = None


OmissionKind = Literal[
    "table_of_contents", "index", "page_furniture", "decorative_media", "converter_artifact"
]


class Omission(StrictModel):
    kind: OmissionKind
    description: str
    count: int = Field(ge=1)


class ExtractionStatistics(StrictModel):
    source_block_count: int = Field(ge=0)
    section_count: int = Field(ge=0)
    table_count: int = Field(ge=0)
    table_row_count: int = Field(ge=0)
    constant_count: int = Field(ge=0)
    omission_count: int = Field(ge=0)


class SpecificationIdentity(StrictModel):
    family: Literal["DWARF"] = "DWARF"
    version: int = Field(ge=2, le=4)
    title: str


class SourceMetadata(StrictModel):
    source_id: str
    filename: str
    format: Literal["mm", "doc"]
    url: str
    source_page: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SpecificationDocument(StrictModel):
    schema_version: int = Field(ge=1)
    parser_version: str
    specification: SpecificationIdentity
    source: SourceMetadata
    sections: list[Section]
    tables: list[Table]
    constants: list[ConstantDefinition]
    omissions: list[Omission]
    statistics: ExtractionStatistics
