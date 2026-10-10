"""Resolve aggregate aliases without manufacturing aggregate definitions."""

from dataclasses import dataclass

from ....core.dwarf import DwarfEntry
from ...models.dwarf.type_reference import TypeReference
from ...ports.type_resolution import TypeResolverPort
from .type_scope import die_key, referenced_die

AGGREGATE_KINDS = {
    "DW_TAG_class_type": "class",
    "DW_TAG_structure_type": "struct",
    "DW_TAG_union_type": "union",
    "DW_TAG_namespace": "namespace",
}


class AggregateEvidenceError(ValueError):
    """A requested aggregate has missing, cyclic, or incompatible type evidence."""


@dataclass(frozen=True, slots=True)
class AggregateTarget:
    """An actual aggregate and the distinct aliases through which it was reached."""

    die: DwarfEntry
    aliases: tuple[TypeReference, ...] = ()


def resolve_aggregate_target(die: DwarfEntry, resolver: TypeResolverPort) -> AggregateTarget:
    """Follow typedef references with source/CU identity and a finite chain bound."""
    aliases: list[TypeReference] = []
    visited: set[tuple[int | None, int | None]] = set()
    current = die
    while current.tag == "DW_TAG_typedef":
        identity = die_key(current)
        if identity in visited or len(visited) >= 128:
            raise AggregateEvidenceError(f"cyclic or excessive aggregate alias chain: {identity}")
        visited.add(identity)
        aliases.append(resolver.resolve_type_reference(current))
        target = referenced_die(current)
        if target is None:
            raise AggregateEvidenceError(f"missing aggregate alias target: {identity}")
        current = target
    if current.tag not in AGGREGATE_KINDS:
        raise AggregateEvidenceError(f"unsupported aggregate tag {current.tag}: {die_key(current)}")
    return AggregateTarget(current, tuple(aliases))
