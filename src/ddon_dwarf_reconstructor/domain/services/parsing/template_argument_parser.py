"""Canonical bounded delimiter-aware template argument splitter."""

from __future__ import annotations

__all__ = ["split_template_arguments"]


def split_template_arguments(arguments: str) -> list[str]:
    """Split comma-separated template arguments respecting nested brackets, parens, and braces."""
    parts: list[str] = []
    start = 0
    depths = {"<": 0, "(": 0, "[": 0, "{": 0}
    matching = {">": "<", ")": "(", "]": "[", "}": "{"}
    for index, character in enumerate(arguments):
        if character in depths:
            depths[character] += 1
        elif character in matching:
            opener = matching[character]
            depths[opener] = max(0, depths[opener] - 1)
        elif character == "," and not any(depths.values()):
            parts.append(arguments[start:index].strip())
            start = index + 1
    final = arguments[start:].strip()
    if final:
        parts.append(final)
    return parts
