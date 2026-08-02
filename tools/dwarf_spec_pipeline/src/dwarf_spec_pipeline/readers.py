"""Readers for logical HTML and OOXML intermediate documents."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
from docx import Document
from docx.document import Document as DocxDocument
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph
from lxml.etree import QName

from .cleaning import clean_converter_text


@dataclass(frozen=True, slots=True)
class RawSpan:
    start_row: int
    end_row: int
    start_column: int
    end_column: int


@dataclass(frozen=True, slots=True)
class RawBlock:
    kind: str
    text: str = ""
    style: str | None = None
    level: int | None = None
    ordered: bool = False
    rows: tuple[tuple[str, ...], ...] = ()
    spans: tuple[RawSpan, ...] = ()
    caption: str | None = None
    index: int = 0


def _tag_name(element: object) -> str:
    tag = getattr(element, "tag", "")
    return QName(tag).localname if isinstance(tag, str) and "}" in tag else str(tag)


def _heading_level(style: str | None) -> int | None:
    if not style:
        return None
    name = style.lower().replace("-", " ")
    if "heading" not in name:
        return None
    suffix = name.rsplit("heading", 1)[-1].strip()
    return int(suffix) if suffix.isdigit() else None


def _docx_cell_span(cell: object, row: int, column: int) -> RawSpan | None:
    tc = getattr(cell, "_tc", None)
    tc_pr = getattr(tc, "tcPr", None)
    grid_span = getattr(getattr(tc_pr, "gridSpan", None), "val", 1) or 1
    row_span = getattr(getattr(tc_pr, "vMerge", None), "val", 1)
    if grid_span == 1 and row_span in (None, "continue", "restart", 1):
        return None
    try:
        column_count = int(str(grid_span))
    except (TypeError, ValueError):
        column_count = 1
    try:
        row_count = int(str(row_span))
    except (TypeError, ValueError):
        row_count = 1
    if column_count == 1 and row_count == 1:
        return None
    return RawSpan(row, row + row_count - 1, column, column + column_count - 1)


def _read_docx_table(table: DocxTable, index: int) -> RawBlock:
    rows: list[tuple[str, ...]] = []
    spans: list[RawSpan] = []
    recorded_span_cells: set[int] = set()
    for row_index, row in enumerate(table.rows):
        values: list[str] = []
        for column_index, cell in enumerate(row.cells):
            values.append(cell.text)
            if span := _docx_cell_span(cell, row_index, column_index):
                cell_id = id(getattr(cell, "_tc", cell))
                if cell_id not in recorded_span_cells:
                    spans.append(span)
                    recorded_span_cells.add(cell_id)
        rows.append(tuple(values))
    return RawBlock(kind="table", rows=tuple(rows), spans=tuple(spans), index=index)


def read_docx(path: Path) -> list[RawBlock]:
    document: DocxDocument = Document(str(path))
    blocks: list[RawBlock] = []
    index = 0
    for child in document.element.body.iterchildren():
        tag = _tag_name(child)
        if tag == "p":
            paragraph = Paragraph(child, document)
            style = getattr(getattr(paragraph, "style", None), "name", None)
            text = paragraph.text
            level = _heading_level(style)
            if not text.strip() and "w:drawing" in paragraph._p.xml:
                blocks.append(RawBlock(kind="media", style=style, index=index))
            elif style and style.lower().startswith("list"):
                blocks.append(
                    RawBlock(
                        kind="list_item",
                        text=text,
                        style=style,
                        ordered="number" in style.lower(),
                        index=index,
                    )
                )
            else:
                blocks.append(
                    RawBlock(
                        kind="heading" if level else "paragraph",
                        text=text,
                        style=style,
                        level=level,
                        index=index,
                    )
                )
            index += 1
        elif tag == "tbl":
            blocks.append(_read_docx_table(DocxTable(child, document), index))
            index += 1
    return blocks


def _html_text(element: Tag) -> str:
    for line_break in element.find_all("br"):
        line_break.replace_with("\n")
    return element.get_text(" ", strip=True)


def _html_span(cell: Tag, row: int, column: int) -> RawSpan | None:
    row_span = _html_int_attribute(cell.get("rowspan"), default=1)
    column_span = _html_int_attribute(cell.get("colspan"), default=1)
    if row_span == 1 and column_span == 1:
        return None
    return RawSpan(row, row + row_span - 1, column, column + column_span - 1)


def _html_int_attribute(value: object, *, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _read_html_table(table: Tag, index: int) -> RawBlock:
    rows: list[tuple[str, ...]] = []
    spans: list[RawSpan] = []
    for row_index, row in enumerate(table.find_all("tr")):
        values: list[str] = []
        for column_index, cell in enumerate(row.find_all(["th", "td"], recursive=False)):
            values.append(_html_text(cell))
            if span := _html_span(cell, row_index, column_index):
                spans.append(span)
        if values:
            rows.append(tuple(values))
    caption = table.find("caption")
    return RawBlock(
        kind="table",
        rows=tuple(rows),
        spans=tuple(spans),
        caption=_html_text(caption) if caption else None,
        index=index,
    )


def _walk_html(parent: Tag) -> Iterable[Tag]:
    for child in parent.children:
        if isinstance(child, NavigableString):
            continue
        if not isinstance(child, Tag):
            continue
        if child.name in {"h1", "h2", "h3", "h4", "h5", "h6"} or child.name in {
            "p",
            "pre",
            "table",
        }:
            yield child
        else:
            yield from _walk_html(child)


def read_html(path: Path) -> list[RawBlock]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")
    for marker in soup.select("script, style, span.indexref"):
        marker.decompose()
    body = soup.body or soup
    blocks: list[RawBlock] = []
    for index, element in enumerate(_walk_html(body)):
        if element.name == "table":
            blocks.append(_read_html_table(element, index))
        elif element.name == "pre":
            blocks.append(RawBlock(kind="code", text=element.get_text("\n"), index=index))
        elif element.name.startswith("h"):
            blocks.append(
                RawBlock(
                    kind="heading",
                    text=_html_text(element),
                    level=int(element.name[1]),
                    index=index,
                )
            )
        else:
            flat_table = _flat_table_blocks(element, index)
            if flat_table is None:
                blocks.append(RawBlock(kind="paragraph", text=_html_text(element), index=index))
            else:
                blocks.extend(flat_table)
    return _coalesce_groff_tables(blocks)


_FLAT_TABLE_HEADERS: dict[str, tuple[str, ...]] = {
    "attribute class general use and encoding": ("Attribute Class", "General Use and Encoding"),
    "attribute identifies or specifies": ("Attribute", "Identifies or Specifies"),
    "attribute name value": ("Attribute", "Name", "Value"),
    "code name value": ("Code", "Name", "Value"),
    "language name meaning": ("Language Name", "Meaning"),
    "language name value": ("Language Name", "Value"),
    "macinfo type name value": ("Macinfo Type Name", "Value"),
    "name value": ("Name", "Value"),
    "name value meaning": ("Name", "Value", "Meaning"),
    "opcode name value": ("Opcode Name", "Value"),
    "operation code no. of operands notes": (
        "Operation",
        "Code",
        "No. of Operands",
        "Notes",
    ),
    "form name value class": ("Form name", "Value", "Class"),
    "tag name value": ("Tag name", "Value"),
}


def _html_lines(element: Tag) -> list[str]:
    fragment = BeautifulSoup(element.decode_contents(), "lxml")
    for line_break in fragment.find_all("br"):
        line_break.replace_with("\n")
    text = fragment.get_text("", strip=False)
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def _flat_table_blocks(element: Tag, index: int) -> list[RawBlock] | None:
    lines = _html_lines(element)
    header_index = next(
        (
            line_index
            for line_index, line in enumerate(lines)
            if " ".join(clean_converter_text(line).split()).lower() in _FLAT_TABLE_HEADERS
        ),
        None,
    )
    if header_index is None:
        return None
    header_key = " ".join(clean_converter_text(lines[header_index]).split()).lower()
    headers = _FLAT_TABLE_HEADERS[header_key]
    rows: list[tuple[str, ...]] = []
    for line in lines[header_index + 1 :]:
        cleaned = clean_converter_text(line)
        if not cleaned:
            continue
        columns = tuple(cleaned.split(maxsplit=len(headers) - 1))
        rows.append(columns + ("",) * (len(headers) - len(columns)))
    table = RawBlock(kind="table", rows=(headers, *rows), index=index)
    prefix = clean_converter_text(" ".join(lines[:header_index]))
    if prefix:
        return [RawBlock(kind="paragraph", text=prefix, index=index), table]
    return [table]


def _table_values(block: RawBlock) -> list[str]:
    return [
        clean_converter_text(cell)
        for row in block.rows
        for cell in row
        if clean_converter_text(cell)
    ]


def _looks_like_constant_values(values: list[str]) -> bool:
    return any(value.startswith("DW_") for value in values) and any(
        value.lower().startswith("0x") or value.lstrip("-").isdigit() for value in values
    )


def _coalesced_table(header: RawBlock, data: RawBlock, headers: list[str]) -> RawBlock | None:
    values = _table_values(data)
    if len(headers) < 2 or not values or len(values) % len(headers) != 0:
        return None
    if not _looks_like_constant_values(values):
        return None
    rows = tuple(
        tuple(values[index : index + len(headers)]) for index in range(0, len(values), len(headers))
    )
    return RawBlock(
        kind="table",
        rows=(tuple(headers),) + rows,
        spans=header.spans + data.spans,
        caption=data.caption or header.caption,
        index=data.index,
    )


def _coalesce_groff_tables(blocks: list[RawBlock]) -> list[RawBlock]:
    result: list[RawBlock] = []
    index = 0
    while index < len(blocks):
        current = blocks[index]
        if current.kind == "table" and index + 2 < len(blocks):
            separator = blocks[index + 1]
            data = blocks[index + 2]
            if (
                separator.kind == "paragraph"
                and not clean_converter_text(separator.text)
                and data.kind == "table"
            ):
                headers = _table_values(current)
                merged = _coalesced_table(current, data, headers)
                if merged is not None:
                    result.append(merged)
                    index += 3
                    continue
        if current.kind == "table" and all(len(row) == 1 for row in current.rows):
            values = _table_values(current)
            if len(values) >= 4 and len(values) % 2 == 0 and _looks_like_constant_values(values):
                rows = tuple(
                    (values[row_index], values[row_index + 1])
                    for row_index in range(0, len(values), 2)
                )
                current = RawBlock(
                    kind="table",
                    rows=(("Name", "Value"),) + rows,
                    spans=current.spans,
                    caption=current.caption,
                    index=current.index,
                )
        result.append(current)
        index += 1
    return result


def read_intermediate(path: Path, intermediate: str) -> list[RawBlock]:
    if intermediate == "docx":
        return read_docx(path)
    if intermediate == "html":
        return read_html(path)
    raise ValueError(f"Unsupported intermediate format {intermediate!r}")
