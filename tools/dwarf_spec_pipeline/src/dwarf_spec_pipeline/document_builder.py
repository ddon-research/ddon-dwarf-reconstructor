"""Stateful construction of canonical documents from converter blocks."""

from __future__ import annotations

import re
from collections import Counter
from typing import Literal, cast

from .cleaning import clean_converter_text
from .models import (
    CodeBlock,
    ConstantDefinition,
    ExtractionStatistics,
    ListBlock,
    Omission,
    OmissionKind,
    ParagraphBlock,
    Section,
    SourceLocation,
    SourceMetadata,
    SpecificationDocument,
    SpecificationIdentity,
    Table,
    TableReferenceBlock,
    TableSpan,
)
from .readers import RawBlock
from .source_manifest import SourceSpec
from .tables import extract_constants, normalize_table

PARSER_VERSION = "0.1.0"
_SECTION_RE = re.compile(
    r"^\s*(?P<number>(?:Appendix\s+[A-Z0-9]+|\d+(?:\.\d+)*))\s*(?:[.:-]|\s)+(?P<title>.+?)\s*$",
    re.IGNORECASE,
)
_PAGE_RE = re.compile(r"^(?:page\s+)?\d+(?:\s+of\s+\d+)?$", re.IGNORECASE)
_FIGURE_RE = re.compile(r"^(?:figure|table)\s+[^.]+\.", re.IGNORECASE)


def _clean_text(text: str) -> str:
    return clean_converter_text(text)


def _heading(text: str, level: int | None) -> tuple[str | None, str] | None:
    match = _SECTION_RE.match(text)
    if match:
        number = match.group("number").strip()
        title = re.sub(r"\s+", " ", match.group("title")).strip(" .:-")
        return number, title if title else number
    if level is not None and text and len(text) < 160:
        return None, text.strip(" .")
    if text.upper() in {"FOREWORD", "INTRODUCTION", "INDEX"}:
        return None, text.title() if text != "INTRODUCTION" else text
    return None


def _is_page_furniture(text: str) -> bool:
    lowered = text.lower()
    return bool(
        _PAGE_RE.fullmatch(text)
        or lowered.startswith("december ")
        and "page" in lowered
        or lowered.startswith("june ")
        and "page" in lowered
        or text == "DWARF Debugging Information Format"
        or re.fullmatch(r"[-_. ]{5,}", text)
    )


def _source_location(
    source: SourceSpec,
    block: RawBlock,
    intermediate: Literal["html", "docx"],
    *,
    figure: str | None = None,
) -> SourceLocation:
    return SourceLocation(
        source_id=source.source_id,
        intermediate=intermediate,
        block_index=block.index,
        figure=figure,
    )


def _section_id(number: str | None, title: str, index: int) -> str:
    if number:
        return "section-" + re.sub(r"[^a-z0-9]+", "-", number.lower()).strip("-")
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "section"
    return f"section-{slug}-{index}"


class DocumentBuilder:
    """Build one document while keeping normalization state explicit."""

    def __init__(self, source: SourceSpec) -> None:
        self.source = source
        self.intermediate: Literal["html", "docx"] = "html" if source.format == "mm" else "docx"
        self.sections: list[Section] = []
        self.tables: list[Table] = []
        self.omissions: Counter[str] = Counter()
        self.current: Section | None = None
        self.in_toc = False
        self.in_index = False
        self.pending_caption: str | None = None

    def build(self, raw_blocks: list[RawBlock]) -> SpecificationDocument:
        common_texts = Counter(
            _clean_text(block.text) for block in raw_blocks if block.text.strip()
        )
        repeated_layout = {
            text for text, count in common_texts.items() if count >= 3 and len(text) < 90
        }
        for block in raw_blocks:
            self._consume(block, repeated_layout)
        constant_values: list[ConstantDefinition] = extract_constants(self.tables)
        omissions = [
            Omission(
                kind=cast(OmissionKind, kind),
                description=_omission_description(kind),
                count=count,
            )
            for kind, count in sorted(self.omissions.items())
            if count
        ]
        statistics = ExtractionStatistics(
            source_block_count=len(raw_blocks),
            section_count=len(self.sections),
            table_count=len(self.tables),
            table_row_count=sum(len(table.rows) for table in self.tables),
            constant_count=len(constant_values),
            omission_count=sum(self.omissions.values()),
        )
        return SpecificationDocument(
            schema_version=1,
            parser_version=PARSER_VERSION,
            specification=SpecificationIdentity(
                version=self.source.standard_version, title=self.source.title
            ),
            source=source_metadata(self.source),
            sections=self.sections,
            tables=self.tables,
            constants=constant_values,
            omissions=omissions,
            statistics=statistics,
        )

    def _consume(self, block: RawBlock, repeated_layout: set[str]) -> None:
        text = _clean_text(block.text)
        if block.kind == "media":
            self.omissions["decorative_media"] += 1
            return
        if block.kind == "table":
            self._append_table(block)
            return
        if not text and block.kind != "code":
            if block.text.strip():
                self.omissions["converter_artifact"] += 1
            return
        if _is_page_furniture(text) or text in repeated_layout:
            self.omissions["page_furniture"] += 1
            return
        if text.lower() in {"table of contents", "contents", "list of figures", "list of tables"}:
            self.in_toc = True
            self.omissions["table_of_contents"] += 1
            return
        heading = _heading(text, block.level) if block.kind == "heading" or block.level else None
        if heading:
            self._append_heading(block, heading)
            return
        if self.in_toc:
            self.omissions["table_of_contents"] += 1
            return
        if self.in_index:
            self.omissions["index"] += 1
            return
        self._append_content(block, text)

    def _append_table(self, block: RawBlock) -> None:
        section = self._ensure_section()
        table_id = f"{self.source.source_id}-table-{len(self.tables) + 1:03d}"
        figure = (
            self.pending_caption
            if self.pending_caption and _FIGURE_RE.match(self.pending_caption)
            else None
        )
        table_source = _source_location(self.source, block, self.intermediate, figure=figure)
        table = normalize_table(
            table_id,
            block.rows,
            tuple(
                TableSpan(
                    start_row=span.start_row,
                    end_row=span.end_row,
                    start_column=span.start_column,
                    end_column=span.end_column,
                )
                for span in block.spans
            ),
            table_source,
            block.caption or self.pending_caption,
        )
        self.tables.append(table)
        section.blocks.append(TableReferenceBlock(table_id=table_id, source=table_source))
        self.pending_caption = None

    def _append_heading(self, block: RawBlock, heading: tuple[str | None, str]) -> None:
        number, title = heading
        if self.in_toc and (number == "1" or title.upper() == "INTRODUCTION"):
            self.in_toc = False
        if self.in_index:
            self.omissions["index"] += 1
            return
        if title.upper() == "INDEX":
            self.in_index = True
            self.omissions["index"] += 1
            return
        level = block.level or (number.count(".") + 1 if number and number[0].isdigit() else 1)
        self.current = Section(
            id=_section_id(number, title, len(self.sections)),
            number=number,
            title=title,
            level=min(level, 6),
            blocks=[],
            source=_source_location(self.source, block, self.intermediate),
        )
        self.sections.append(self.current)
        self.pending_caption = None

    def _append_content(self, block: RawBlock, text: str) -> None:
        section = self._ensure_section()
        source = _source_location(self.source, block, self.intermediate)
        if block.kind == "code":
            section.blocks.append(CodeBlock(text=block.text.strip(), source=source))
        elif block.kind == "list_item":
            ordered = block.ordered
            if (
                section.blocks
                and isinstance(section.blocks[-1], ListBlock)
                and section.blocks[-1].ordered == ordered
            ):
                section.blocks[-1].items.append(text)
            else:
                section.blocks.append(ListBlock(ordered=ordered, items=[text], source=source))
        else:
            section.blocks.append(ParagraphBlock(text=text, source=source))
            self.pending_caption = text if _FIGURE_RE.match(text) else None

    def _ensure_section(self) -> Section:
        if self.current is None:
            self.current = Section(
                id="front-matter", number=None, title="Front matter", level=0, blocks=[]
            )
            self.sections.append(self.current)
        return self.current


def build_document(source: SourceSpec, raw_blocks: list[RawBlock]) -> SpecificationDocument:
    """Build a canonical document with a source-bound normalization state."""
    return DocumentBuilder(source).build(raw_blocks)


def source_metadata(source: SourceSpec) -> SourceMetadata:
    return SourceMetadata(
        source_id=source.source_id,
        filename=source.filename,
        format=source.format,
        url=source.url,
        source_page=source.source_page,
        sha256=source.sha256,
    )


def _omission_description(kind: str) -> str:
    return {
        "converter_artifact": "Converter-only markup or control text",
        "decorative_media": "Decorative images without specification text",
        "index": "Generated index and its page-oriented entries",
        "page_furniture": "Repeated headers, footers, page numbers, and rules",
        "table_of_contents": "Generated table of contents and list-of-figures entries",
    }.get(kind, kind)
