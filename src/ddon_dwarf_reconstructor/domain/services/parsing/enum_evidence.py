"""Recover enum-specific facts without treating representation as source syntax."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from ....core.dwarf import DwarfEntry, decode_dwarf_string
from ...models.dwarf.type_reference import TypeReference
from ...ports.type_resolution import TypeResolverPort
from .type_scope import die_key, referenced_die

ScopedEvidence = Literal["present", "explicit_false", "absent", "unavailable"]
EnumEvidence = ScopedEvidence | Literal["legacy_fixed", "legacy_nonfixed", "legacy_inconsistent"]
_PS4_CLANG35 = "clang version 3.5.0 (PS4 clang version 2.50.0.2333)"


@dataclass(frozen=True)
class EnumSemantics:
    """Distinguish raw DWARF flags from producer-conditioned source semantics."""

    scoped: bool | None
    scopedness_evidence: EnumEvidence
    enum_class_flag: bool | None
    fixed_base_evidence: bool | None
    producer_profile: str | None


def scopedness(die: DwarfEntry) -> tuple[bool | None, ScopedEvidence]:
    """An absent type-safe flag is not an observed false flag."""
    attribute = die.attributes.get("DW_AT_enum_class")
    if attribute is None:
        if "DW_AT_name" not in die.attributes:
            return False, "unavailable"  # C++ requires a name for a scoped enumeration.
        return None, "absent"
    value = attribute.value
    if value in (True, 1) and isinstance(value, (bool, int)):
        return True, "present"
    if value in (False, 0) and isinstance(value, (bool, int)):
        return False, "explicit_false"
    return None, "unavailable"


def classify_enum(die: DwarfEntry) -> EnumSemantics:
    """Apply the observed PS4 Clang 3.5 emission rule only to matching C++ CUs."""
    raw_flag, evidence = scopedness(die)
    flag = raw_flag if evidence in ("present", "explicit_false") else None
    profile = _legacy_profile(die)
    if profile is None:
        return EnumSemantics(raw_flag, evidence, flag, None, None)
    return _legacy_semantics(die, evidence, flag, profile)


def _legacy_semantics(
    die: DwarfEntry, evidence: ScopedEvidence, flag: bool | None, profile: str
) -> EnumSemantics:
    has_base = "DW_AT_type" in die.attributes
    if evidence == "explicit_false":
        return EnumSemantics(False, evidence, False, has_base, profile)
    if evidence == "present" and has_base:
        return EnumSemantics(None, "legacy_fixed", True, True, profile)
    if evidence == "absent" and not has_base:
        return EnumSemantics(False, "legacy_nonfixed", None, False, profile)
    if evidence == "unavailable" and not has_base and "DW_AT_name" not in die.attributes:
        return EnumSemantics(False, evidence, None, False, profile)
    return EnumSemantics(None, "legacy_inconsistent", flag, None, profile)


def _legacy_profile(die: DwarfEntry) -> str | None:
    cu = getattr(die, "cu", None)
    if _dwarf_version(getattr(cu, "header", None)) != 4:
        return None
    current = die
    for _ in range(32):
        if current.tag == "DW_TAG_compile_unit":
            producer = current.attributes.get("DW_AT_producer")
            language = current.attributes.get("DW_AT_language")
            if (
                producer is not None
                and language is not None
                and decode_dwarf_string(producer.value) == _PS4_CLANG35
                and language.value == 4
            ):
                return "ps4-clang35-dwarf4-cxx"
            return None
        parent = current.get_parent()
        if parent is None or not isinstance(getattr(parent, "tag", None), str):
            return None
        current = parent
    return None


def _dwarf_version(header: object) -> int | None:
    if not isinstance(header, Mapping):
        return None
    value = header.get("version")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    items = header.get("items")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, list) and len(item) == 2 and item[0] == "version":
                return item[1] if isinstance(item[1], int) else None
    return None


def representation(
    die: DwarfEntry, resolver: TypeResolverPort
) -> tuple[TypeReference | None, int | None]:
    """DW_AT_type gives implementation representation, not fixed-base syntax."""
    target = referenced_die(die)
    if target is None:
        return None, None
    offset = die_key(target)[1]
    if target.tag != "DW_TAG_base_type":
        return None, offset
    reference = resolver.resolve_type_reference(target)
    return (reference if isinstance(reference, TypeReference) else None), offset
