"""Application-level completeness guards for published generation bundles."""

from __future__ import annotations

from collections.abc import Mapping

from .options import GenerationOptions


def reject_source_bound_placeholder(
    options: GenerationOptions, headers: Mapping[str, str], symbol_name: str
) -> None:
    """Prevent a source-bound full-hierarchy run from publishing a placeholder bundle."""
    if options.dwarf_store_manifest is None or not options.full_hierarchy:
        return
    placeholder = headers.get("UncategorizedDefinitions.h")
    if (
        len(headers) != 1
        or placeholder is None
        or "not found in DWARF information" not in placeholder
    ):
        return
    raise RuntimeError(
        f"Source-bound generation for {symbol_name} produced an unresolved placeholder; "
        "the analytical lookup is incomplete or the source store is missing the root"
    )


__all__ = ["reject_source_bound_placeholder"]
