"""Source-bound diagnostics for unresolved complete base requirements."""

from __future__ import annotations

from collections.abc import Iterator, Mapping

from ...models.dwarf import ClassInfo
from .header_type_planning import HeaderTypePlanningService


def _classes(info: ClassInfo) -> Iterator[ClassInfo]:
    yield info
    for nested in info.nested_classes:
        yield from _classes(nested)


def ambiguous_base_requirements(
    infos: Mapping[str, ClassInfo],
    ambiguous: Mapping[str, tuple[str, ...]],
    offset_names: Mapping[tuple[int | None, int], str],
) -> tuple[str, ...]:
    """Report base spellings that cannot select one observed complete definition."""
    diagnostics: set[str] = set()
    for class_key, info in sorted(infos.items()):
        for owner in _classes(info):
            observed_bases = {
                target
                for offset in owner.base_class_offsets
                if (target := offset_names.get((owner.cu_offset, offset))) is not None
            }
            for base_name in owner.base_classes:
                spelling = HeaderTypePlanningService._lookup_type_name(base_name)
                candidates = ambiguous.get(spelling)
                if candidates is None or observed_bases.intersection(candidates):
                    continue
                identity = (
                    f"{owner.qualified_name or owner.name}|{owner.cu_offset}|{owner.die_offset}"
                )
                diagnostics.add(
                    f"ambiguous complete base requirement for {class_key} ({identity}): "
                    f"{spelling} candidates {', '.join(candidates)}; no matching base type DIE"
                )
    return tuple(sorted(diagnostics))
