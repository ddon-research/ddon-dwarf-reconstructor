"""Evidence-row helpers for source-bound implementation context queries."""

from __future__ import annotations

import json
from typing import Any

from ..domain.models.analytical_dwarf import QueryResult
from ..domain.services.cpp_reconstruction.abi import classify_return_type
from .implementation_abi_facts import acquire_return_type


def query_die(
    store: Any,
    die_offset: int,
    unit_offset: int | None = None,
    diagnostics: list[str] | None = None,
) -> Any | None:
    result = (
        store.get_die(die_offset, unit_offset=unit_offset)
        if unit_offset is not None
        else store.get_die(die_offset)
    )
    record_query_status(result, f"DIE 0x{die_offset:x}", diagnostics)
    return result.items[0] if result.items else None


def query_locations(
    store: Any,
    die_offset: int,
    attribute_name: str | None = None,
    *,
    unit_offset: int | None = None,
    diagnostics: list[str] | None = None,
) -> list[dict[str, object]]:
    result = (
        store.find_locations(
            die_offset,
            unit_offset=unit_offset,
            attribute_name=attribute_name,
        )
        if unit_offset is not None
        else store.find_locations(die_offset, attribute_name=attribute_name)
    )
    record_query_status(result, f"location DIE 0x{die_offset:x}", diagnostics)
    return [dict(item) for item in result.items if isinstance(item, dict)]


def query_frames(
    store: Any,
    start: int | None,
    end: int | None,
    diagnostics: list[str] | None = None,
) -> list[dict[str, object]]:
    result = store.find_frames(start_address=start, end_address=end)
    record_query_status(result, "CFI", diagnostics)
    return [dict(item) for item in result.items if isinstance(item, dict)]


def frame_overlaps(row: dict[str, object], start: int | None, end: int | None) -> bool:
    if start is None or end is None:
        return True
    initial = optional_int(row.get("initial_address"))
    span = optional_int(row.get("address_range"))
    return initial is not None and span is not None and initial < end and initial + span > start


def query_diagnostics(
    store: Any,
    die_offset: int,
    unit_offset: int | None,
    frames: list[dict[str, object]],
) -> list[str]:
    diagnostics: list[str] = []
    if not frames:
        diagnostics.append("analytical store has no CFI row covering the method range")
    result = (
        store.find_locations(die_offset, unit_offset=unit_offset)
        if unit_offset is not None
        else store.find_locations(die_offset)
    )
    record_query_status(result, f"location DIE 0x{die_offset:x}", diagnostics)
    if getattr(result, "truncated", False):
        diagnostics.append("analytical store location query was truncated")
    return diagnostics


def abi_facts(
    store: Any,
    die: Any,
    declaration_die: Any,
    method_locations: list[dict[str, object]],
    unit_offset: int | None,
    diagnostics: list[str],
) -> dict[str, Any]:
    attributes = getattr(die, "attributes", {})
    declaration_attributes = getattr(declaration_die, "attributes", {})
    return_facts = classify_return_type(acquire_return_type(store, declaration_die, diagnostics))
    diagnostics.extend(return_facts.diagnostics)
    calling_convention = attribute_text(attributes, "DW_AT_calling_convention")
    if calling_convention is None:
        calling_convention = attribute_text(declaration_attributes, "DW_AT_calling_convention")
    if calling_convention is None:
        calling_convention = "DW_CC_normal"
        diagnostics.append("DW_AT_calling_convention is absent; SDK12 default DW_CC_normal applied")
    object_pointer = object_pointer_name(die) or object_pointer_name(declaration_die)
    object_pointer_required = object_pointer_is_required(
        attributes, declaration_attributes, object_pointer
    )
    facts: dict[str, Any] = {
        "diagnostics": list(diagnostics),
        "calling_convention": calling_convention,
        "object_pointer": object_pointer,
        "object_pointer_required": object_pointer_required,
        "frame_base_locations": location_summaries(
            item for item in method_locations if item.get("attribute_name") == "DW_AT_frame_base"
        ),
        "return_location": location_summary_for_attribute(
            store,
            int(die.offset),
            "DW_AT_return_location",
            diagnostics,
            unit_offset,
        )
        or return_facts.return_location,
        "return_type_status": return_facts.status,
        "return_type_kind": return_facts.kind,
        "return_type_size": return_facts.size,
        "hidden_return": return_facts.hidden_return,
    }
    if object_pointer_required and object_pointer is None:
        facts["diagnostics"].append("DW_AT_object_pointer is absent")
    return facts


def parameter_evidence(
    store: Any, die: Any, unit_offset: int | None, diagnostics: list[str]
) -> tuple[list[dict[str, object]], dict[str, Any]]:
    locations: list[dict[str, object]] = []
    parameter_locations: list[str] = []
    artificial: list[str] = []
    hidden: list[str] = []
    formal_count = 0
    unlocated: list[str] = []
    object_pointer = object_pointer_name(die)
    for child in die.iter_children():
        if getattr(child, "tag", None) != "DW_TAG_formal_parameter":
            continue
        formal_count += 1
        attributes = getattr(child, "attributes", {})
        offset = getattr(child, "offset", None)
        if not isinstance(offset, int):
            continue
        name = attribute_text(attributes, "DW_AT_name") or f"die:0x{offset:x}"
        is_artificial = attribute_bool(attributes, "DW_AT_artificial") is True
        if is_artificial:
            artificial.append(name)
            if name != object_pointer and name.lower() not in {"this", "__this"}:
                hidden.append(name)
        child_locations = query_locations(
            store,
            offset,
            "DW_AT_location",
            unit_offset=unit_offset,
            diagnostics=diagnostics,
        )
        for record in child_locations:
            enriched = dict(record)
            enriched["parameter_name"] = name
            enriched["parameter_die_offset"] = offset
            enriched["artificial"] = is_artificial
            locations.append(enriched)
        if child_locations:
            parameter_locations.append(f"{name}:" + ",".join(location_summaries(child_locations)))
        else:
            unlocated.append(name)
    return locations, {
        "parameter_locations": tuple(parameter_locations),
        "formal_parameter_count": formal_count,
        "located_parameter_count": len(parameter_locations),
        "unlocated_parameters": tuple(unlocated),
        "artificial_parameters": tuple(artificial),
        "hidden_parameters": tuple(hidden),
        "hidden_return": hidden_return_value(hidden),
    }


def object_pointer_name(die: Any) -> str | None:
    target_getter = getattr(die, "get_DIE_from_attribute", None)
    target = target_getter("DW_AT_object_pointer") if callable(target_getter) else None
    if target is None:
        return None
    attributes = getattr(target, "attributes", {})
    offset = getattr(target, "offset", None)
    return attribute_text(attributes, "DW_AT_name") or (
        f"die:0x{offset:x}" if isinstance(offset, int) else "object-pointer-die"
    )


def object_pointer_is_required(
    implementation_attributes: Any,
    declaration_attributes: Any,
    object_pointer: str | None,
) -> bool:
    if object_pointer is not None:
        return True
    for attributes in (implementation_attributes, declaration_attributes):
        if attribute_bool(attributes, "DW_AT_static") is True:
            return False
        if isinstance(attributes, dict) and "DW_AT_containing_type" in attributes:
            return True
        if isinstance(attributes, dict) and "DW_AT_object_pointer" in attributes:
            return True
    return False


def location_summary_for_attribute(
    store: Any,
    die_offset: int,
    name: str,
    diagnostics: list[str],
    unit_offset: int | None = None,
) -> str | None:
    values = query_locations(
        store,
        die_offset,
        name,
        unit_offset=unit_offset,
        diagnostics=diagnostics,
    )
    summaries = location_summaries(values)
    return summaries[0] if summaries else None


def location_summaries(values: Any) -> tuple[str, ...]:
    return tuple(
        json.dumps(location_expression(value), sort_keys=True, default=str) for value in values
    )


def location_expression(value: dict[str, object]) -> object:
    """Select the logical expression from either Doris or legacy row shapes."""
    for key in ("expression", "details", "decoded_value"):
        candidate = value.get(key)
        if candidate is not None:
            return candidate
    encoded = value.get("expression_json")
    if isinstance(encoded, str):
        try:
            return json.loads(encoded)
        except json.JSONDecodeError:
            return encoded
    return None


def hidden_return_value(hidden: list[str]) -> bool | None:
    matches = [value for value in hidden if "sret" in value.lower() or "return" in value.lower()]
    return True if matches else None


def attribute_text(attributes: Any, name: str) -> str | None:
    if not isinstance(attributes, dict):
        return None
    attribute = attributes.get(name)
    value = getattr(attribute, "value", None)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value) if value is not None else None


def attribute_bool(attributes: Any, name: str) -> bool | None:
    if not isinstance(attributes, dict):
        return None
    value = getattr(attributes.get(name), "value", None)
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    return None


def optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    return None


def record_query_status(result: QueryResult, label: str, diagnostics: list[str] | None) -> None:
    if diagnostics is None:
        return
    status = result.status.value
    if status == "complete":
        return
    diagnostics.extend(result.diagnostics)
    diagnostics.append(f"{label} query status: {status}")


__all__ = [
    "abi_facts",
    "attribute_bool",
    "attribute_text",
    "frame_overlaps",
    "hidden_return_value",
    "location_expression",
    "location_summaries",
    "location_summary_for_attribute",
    "object_pointer_is_required",
    "object_pointer_name",
    "optional_int",
    "parameter_evidence",
    "query_diagnostics",
    "query_die",
    "query_frames",
    "query_locations",
    "record_query_status",
]
