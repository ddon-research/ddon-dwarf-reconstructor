"""Immutable inputs shared by the header rendering collaborators."""

from __future__ import annotations

from dataclasses import dataclass

from ....ports.class_parser import ClassParserPort
from ....ports.dwarf_lookup import DwarfLookupPort


@dataclass(frozen=True, slots=True)
class HeaderRenderContext:
    """Dependencies required to render a header.

    Rendering state such as ordering maps remains private to one renderer
    invocation.  The context is immutable so callers cannot mutate the
    renderer's collaborators after construction.
    """

    dwarf_index: DwarfLookupPort
    class_parser: ClassParserPort | None = None
