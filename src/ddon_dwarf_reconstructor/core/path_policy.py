"""Deterministic, technology-neutral output naming policy."""

from __future__ import annotations

import re
import string


def sanitize_for_filesystem(name: str, replacement: str = "_") -> str:
    """Return a stable filename component for a C++ qualified name."""
    if not name:
        return "unnamed"

    sanitized = name.replace("::", "__").replace("<", "_").replace(">", "_")
    valid_chars = set(string.ascii_letters + string.digits + "_-.")
    sanitized = "".join(char if char in valid_chars else replacement for char in sanitized)
    if replacement in sanitized:
        sanitized = re.sub(re.escape(replacement) + "+", replacement, sanitized)
    sanitized = sanitized.strip(replacement)
    if not sanitized:
        return "unnamed"
    return sanitized[:200].rstrip(replacement)


def create_header_filename(class_name: str, suffix: str = "") -> str:
    """Return the canonical generated-header filename."""
    base_name = sanitize_for_filesystem(class_name)
    if suffix:
        base_name = f"{base_name}_{sanitize_for_filesystem(suffix)}"
    return f"{base_name}.h"
