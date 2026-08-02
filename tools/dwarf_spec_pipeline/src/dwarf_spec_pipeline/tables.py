"""Normalize tables and derive structured DWARF constant definitions."""

from __future__ import annotations

import re
from collections import defaultdict

from .cleaning import clean_converter_text
from .models import ConstantDefinition, SourceLocation, Table, TableSpan

_NAME_RE = re.compile(r"\bDW_[A-Za-z0-9]+_[A-Za-z0-9_]+\b")
_VALUE_RE = re.compile(r"(?<![A-Za-z0-9_])(?:0x[0-9A-Fa-f]+|-?[0-9]+)(?![A-Za-z0-9_])")
_HEADER_WORDS = {
    "attribute",
    "classes",
    "code",
    "description",
    "encoding",
    "form",
    "meaning",
    "name",
    "opcode",
    "operand",
    "tag",
    "value",
}


def normalize_table(
    table_id: str,
    rows: tuple[tuple[str, ...], ...],
    spans: tuple[TableSpan, ...],
    source: SourceLocation | None,
    caption: str | None,
) -> Table:
    cleaned = [[_clean_cell(cell) for cell in row] for row in rows]
    cleaned = [row for row in cleaned if any(cell for cell in row)]
    width = max((len(row) for row in cleaned), default=1)
    padded = [row + [""] * (width - len(row)) for row in cleaned]
    if padded and _looks_like_header(padded[0]):
        headers = padded[0]
        data = padded[1:]
    else:
        headers = [f"column_{index + 1}" for index in range(width)]
        data = padded
    return Table(
        id=table_id,
        caption=_clean_cell(caption) if caption else None,
        headers=headers,
        rows=data,
        spans=[span for span in spans],
        source=source,
    )


def _clean_cell(value: str) -> str:
    return clean_converter_text(value)


def _looks_like_header(row: list[str]) -> bool:
    words = {cell.lower().strip(" :") for cell in row if cell}
    if words & _HEADER_WORDS:
        return True
    return bool(row) and all(not _NAME_RE.fullmatch(cell) for cell in row if cell)


def _parse_value(value_text: str) -> int | None:
    try:
        return int(value_text, 0) if value_text.lower().startswith("0x") else int(value_text, 10)
    except ValueError:
        return None


def _namespace(name: str) -> str:
    parts = name.split("_")
    return "_".join(parts[:2])


def _meaning(row: list[str], names: list[str], values: list[str]) -> str | None:
    pieces: list[str] = []
    for cell in row:
        remainder = _NAME_RE.sub("", cell)
        remainder = _VALUE_RE.sub("", remainder)
        remainder = re.sub(r"[‡†]+", "", remainder)
        if remainder.strip():
            pieces.append(remainder.strip(" ,;:-"))
    meaning = " ".join(piece for piece in pieces if piece)
    return meaning or None


def extract_constants(tables: list[Table]) -> list[ConstantDefinition]:
    records: list[tuple[str, str, str, int | None, str | None, str, SourceLocation | None]] = []
    for table in tables:
        pending_names: list[str] = []
        for row in table.rows:
            joined = " ".join(row)
            names = _NAME_RE.findall(joined)
            values = _VALUE_RE.findall(joined)
            if names and values:
                pairs = (
                    zip(names, values, strict=True)
                    if len(names) == len(values)
                    else ((names[0], values[0]),)
                )
                for name, value_text in pairs:
                    records.append(
                        (
                            table.id,
                            name,
                            value_text,
                            _parse_value(value_text),
                            _meaning(row, names, values),
                            _namespace(name),
                            table.source,
                        )
                    )
                pending_names = []
            elif names:
                pending_names.extend(names)
            elif values and pending_names:
                for name, value_text in zip(pending_names, values, strict=False):
                    records.append(
                        (
                            table.id,
                            name,
                            value_text,
                            _parse_value(value_text),
                            None,
                            _namespace(name),
                            table.source,
                        )
                    )
                pending_names = pending_names[len(values) :]

    unique: dict[
        tuple[str, str, str],
        tuple[str, str, str, int | None, str | None, str, SourceLocation | None],
    ] = {}
    for record in records:
        table_id, name, value_text, value, meaning, namespace, source = record
        unique[(table_id, name, value_text)] = (
            table_id,
            name,
            value_text,
            value,
            meaning,
            namespace,
            source,
        )

    aliases_by_value: defaultdict[tuple[str, str, str], list[str]] = defaultdict(list)
    for table_id, name, value_text, *_ in unique.values():
        aliases_by_value[(table_id, value_text, _namespace(name))].append(name)

    constants: list[ConstantDefinition] = []
    for table_id, name, value_text, value, meaning, namespace, source in sorted(
        unique.values(), key=lambda record: (record[0], record[5], record[1], record[2])
    ):
        aliases = sorted(set(aliases_by_value[(table_id, value_text, namespace)]) - {name})
        constants.append(
            ConstantDefinition(
                namespace=namespace,
                name=name,
                value=value,
                value_hex=f"0x{value:x}" if value is not None else None,
                value_text=value_text,
                meaning=meaning,
                aliases=aliases,
                table_id=table_id,
                source=source,
            )
        )
    return constants
