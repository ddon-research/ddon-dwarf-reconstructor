"""Source-bound candidate selection hints for analytical stores."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, TypeVar

from ...domain.models.analytical_dwarf import MaterializationManifest
from ...domain.ports.cache import SymbolCachePort
from ...domain.repositories.cache import PersistentSymbolCache


class _OffsetItem(Protocol):
    """Minimum materialized definition shape needed for cache reordering."""

    offset: int


_Item = TypeVar("_Item", bound=_OffsetItem)


def load_selection_cache(
    manifest: MaterializationManifest,
    cache_path: Path | None,
    *,
    source_fingerprint: dict[str, int | str] | None = None,
) -> SymbolCachePort | None:
    """Load an optional cache whose fingerprint must match the store source."""
    if cache_path is None:
        return None
    fingerprint = source_fingerprint or manifest.source_identity.as_fingerprint()
    selected_path = _find_source_bound_cache(cache_path, fingerprint)
    if selected_path is None:
        return None
    return PersistentSymbolCache(selected_path, fingerprint)


def _find_source_bound_cache(cache_path: Path, fingerprint: dict[str, int | str]) -> Path | None:
    """Find a source-bound sibling when a relocated source changed the path key."""
    preferred = cache_path.resolve()
    if preferred.exists():
        return preferred
    for candidate in sorted(preferred.parent.glob("*-dwarf-cache.json")):
        try:
            cache = PersistentSymbolCache(candidate, fingerprint)
        except OSError, ValueError:
            continue
        if cache.data.get("source_fingerprint") == fingerprint:
            return candidate.resolve()
    return None


def prefer_cached_definition(
    name: str,
    items: Sequence[_Item],
    cache: SymbolCachePort | None,
) -> tuple[_Item, ...]:
    """Put a validated historical primary definition before other candidates."""
    ordered = tuple(items)
    if cache is None:
        return ordered
    preferred_offset = cache.get_symbol_offset(name)
    if not isinstance(preferred_offset, int):
        return ordered
    preferred_index = next(
        (index for index, item in enumerate(ordered) if item.offset == preferred_offset),
        None,
    )
    if preferred_index is None or preferred_index == 0:
        return ordered
    return (ordered[preferred_index], *ordered[:preferred_index], *ordered[preferred_index + 1 :])
