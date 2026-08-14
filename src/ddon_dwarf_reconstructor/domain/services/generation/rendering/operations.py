"""Typed host surface shared by the composed header rendering services."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeVar

from ....ports.class_parser import ClassParserPort
from ....ports.dwarf_lookup import DwarfLookupPort

T = TypeVar("T")


class HeaderRenderingHost(Protocol):
    """Minimal typed host for the explicitly bound rendering operations.

    The concrete service methods are intentionally kept in their cohesive
    modules.  Their cross-service calls resolve on the per-renderer host at
    runtime; the generic callable return lets each cohesive algorithm retain its
    precise result type without introducing another giant private protocol.
    """

    dwarf_index: DwarfLookupPort
    class_parser: ClassParserPort | None
    _base_type_names: dict[int, str]
    _known_render_type_names: set[str]
    _forward_declaration_kind_cache: dict[str, str | None]

    def __getattr__(self, name: str) -> Callable[..., T]:
        raise AttributeError(name)
