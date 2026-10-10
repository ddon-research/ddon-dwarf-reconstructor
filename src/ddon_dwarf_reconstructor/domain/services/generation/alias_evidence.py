"""Preserve distinct alias observations when compatible aggregate observations merge."""

from collections.abc import Iterable

from ...models.dwarf import ClassInfo, TypeReference


def source_aliases(infos: Iterable[ClassInfo]) -> tuple[TypeReference, ...]:
    """Keep every alias identity and target, ordered independently of discovery."""
    observations = {alias for info in infos for alias in info.source_aliases}
    return tuple(sorted(observations, key=repr))
