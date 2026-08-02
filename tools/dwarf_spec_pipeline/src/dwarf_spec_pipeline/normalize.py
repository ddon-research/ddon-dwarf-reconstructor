"""Turn converter-specific blocks into the canonical DWARF document model."""

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
        number = match.group("number").replace(".", ".").strip()
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


def build_document(source: SourceSpec, raw_blocks: list[RawBlock]) -> SpecificationDocument:
    intermediate: Literal["html", "docx"] = "html" if source.format == "mm" else "docx"
    common_texts = Counter(_clean_text(block.text) for block in raw_blocks if block.text.strip())
    repeated_layout = {
        text for text, count in common_texts.items() if count >= 3 and len(text) < 90
    }
    sections: list[Section] = []
    tables: list[Table] = []
    omissions: Counter[str] = Counter()
    current: Section | None = None
    in_toc = False
    in_index = False
    pending_caption: str | None = None

    def ensure_section() -> Section:
        nonlocal current
        if current is None:
            current = Section(
                id="front-matter", number=None, title="Front matter", level=0, blocks=[]
            )
            sections.append(current)
        return current

    for block in raw_blocks:
        text = _clean_text(block.text)
        if block.kind == "media":
            omissions["decorative_media"] += 1
            continue
        if block.kind == "table":
            section = ensure_section()
            table_id = f"{source.source_id}-table-{len(tables) + 1:03d}"
            figure = (
                pending_caption if pending_caption and _FIGURE_RE.match(pending_caption) else None
            )
            table_source = _source_location(source, block, intermediate, figure=figure)
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
                block.caption or pending_caption,
            )
            tables.append(table)
            section.blocks.append(TableReferenceBlock(table_id=table_id, source=table_source))
            pending_caption = None
            continue

        if not text and block.kind != "code":
            if block.text.strip():
                omissions["converter_artifact"] += 1
            continue
        if _is_page_furniture(text) or text in repeated_layout:
            omissions["page_furniture"] += 1
            continue
        if text.lower() in {"table of contents", "contents", "list of figures", "list of tables"}:
            in_toc = True
            omissions["table_of_contents"] += 1
            continue

        heading = _heading(text, block.level) if block.kind == "heading" or block.level else None
        if heading:
            number, title = heading
            if in_toc and (number == "1" or title.upper() == "INTRODUCTION"):
                in_toc = False
            if in_index:
                omissions["index"] += 1
                continue
            if title.upper() == "INDEX":
                in_index = True
                omissions["index"] += 1
                continue
            level = block.level or (number.count(".") + 1 if number and number[0].isdigit() else 1)
            current = Section(
                id=_section_id(number, title, len(sections)),
                number=number,
                title=title,
                level=min(level, 6),
                blocks=[],
                source=_source_location(source, block, intermediate),
            )
            sections.append(current)
            pending_caption = None
            continue
        if in_toc:
            omissions["table_of_contents"] += 1
            continue
        if in_index:
            omissions["index"] += 1
            continue

        section = ensure_section()
        source_location = _source_location(source, block, intermediate)
        if block.kind == "code":
            section.blocks.append(CodeBlock(text=block.text.strip(), source=source_location))
        elif block.kind == "list_item":
            ordered = block.ordered
            if (
                section.blocks
                and isinstance(section.blocks[-1], ListBlock)
                and section.blocks[-1].ordered == ordered
            ):
                section.blocks[-1].items.append(text)
            else:
                section.blocks.append(
                    ListBlock(ordered=ordered, items=[text], source=source_location)
                )
        else:
            section.blocks.append(ParagraphBlock(text=text, source=source_location))
            pending_caption = text if _FIGURE_RE.match(text) else None

    constant_values: list[ConstantDefinition] = extract_constants(tables)
    omissions_models = [
        Omission(
            kind=cast(OmissionKind, kind),
            description=_omission_description(kind),
            count=count,
        )
        for kind, count in sorted(omissions.items())
        if count
    ]
    statistics = ExtractionStatistics(
        source_block_count=len(raw_blocks),
        section_count=len(sections),
        table_count=len(tables),
        table_row_count=sum(len(table.rows) for table in tables),
        constant_count=len(constant_values),
        omission_count=sum(omissions.values()),
    )
    return SpecificationDocument(
        schema_version=1,
        parser_version=PARSER_VERSION,
        specification=SpecificationIdentity(version=source.standard_version, title=source.title),
        source=source_metadata(source),
        sections=sections,
        tables=tables,
        constants=constant_values,
        omissions=omissions_models,
        statistics=statistics,
    )


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
