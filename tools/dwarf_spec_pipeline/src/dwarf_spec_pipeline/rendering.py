"""Deterministic JSON and Markdown renderers for the canonical model."""

from __future__ import annotations

import json
import re

from .models import (
    CodeBlock,
    ListBlock,
    ParagraphBlock,
    SpecificationDocument,
    TableReferenceBlock,
)


def render_json(document: SpecificationDocument) -> str:
    return (
        json.dumps(document.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def _fence(text: str) -> str:
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def render_markdown(document: SpecificationDocument) -> str:
    table_by_id = {table.id: table for table in document.tables}
    lines = [
        f"# DWARF Debugging Information Format, Version {document.specification.version}",
        "",
        f"> Source: `{document.source.filename}`",
        f"> Source URL: {document.source.url}",
        f"> Source catalog: {document.source.source_page}",
        f"> SHA-256: `{document.source.sha256}`",
        f"> Canonical schema: `{document.schema_version}`; parser: `{document.parser_version}`",
        "",
    ]
    for section in document.sections:
        heading_level = min(section.level + 1, 6)
        lines.extend([f"{'#' * heading_level} {section.title}", ""])
        for block in section.blocks:
            if isinstance(block, ParagraphBlock):
                lines.extend([block.text, ""])
            elif isinstance(block, CodeBlock):
                fence = _fence(block.text)
                language = block.language or "text"
                lines.extend([f"{fence}{language}", block.text.rstrip(), fence, ""])
            elif isinstance(block, ListBlock):
                for index, item in enumerate(block.items, start=1):
                    prefix = f"{index}." if block.ordered else "-"
                    lines.append(f"{prefix} {item}")
                lines.append("")
            elif isinstance(block, TableReferenceBlock):
                table = table_by_id[block.table_id]
                if table.caption:
                    lines.extend([f"**{table.caption}**", ""])
                lines.append("| " + " | ".join(_escape_cell(cell) for cell in table.headers) + " |")
                lines.append("| " + " | ".join("---" for _ in table.headers) + " |")
                for row in table.rows:
                    padded = row + [""] * (len(table.headers) - len(row))
                    lines.append("| " + " | ".join(_escape_cell(cell) for cell in padded) + " |")
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"
