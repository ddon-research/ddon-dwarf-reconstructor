"""Doris-backed method context hydration for implementation generation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from ...domain.models.analytical_dwarf import QueryResult, QueryStatus
from ...domain.models.implementation_context import MethodContextPacket
from ...domain.models.implementation_evidence import (
    MethodAssemblyEvidence,
    MethodImplementationCandidate,
)
from ...domain.ports.analytical_store import DwarfQueryPort
from ..generation.runtime import GenerationRuntime


def attach_analytical_context(
    runtime: GenerationRuntime,
    methods: tuple[MethodAssemblyEvidence, ...],
) -> tuple[MethodAssemblyEvidence, ...]:
    """Attach bounded location/CFI/ABI rows through the active analytical port."""
    query_port = runtime.class_parser.query_port
    if query_port is None:
        return methods
    return tuple(
        replace(method, dwarf_context=_method_context(query_port, method)) for method in methods
    )


def _method_context(
    query_port: DwarfQueryPort,
    method: MethodAssemblyEvidence,
) -> MethodContextPacket:
    implementation_offset = method.selected_implementation_die_offset
    if implementation_offset is None:
        candidate = _selected_candidate(method)
        implementation_offset = candidate.implementation_die_offset if candidate else None
    diagnostics = list(method.diagnostics)
    if implementation_offset is None:
        diagnostics.append("method has no implementation DIE for analytical context")
        return _empty_context(method, diagnostics)

    try:
        locations_result = query_port.find_locations(implementation_offset)
        locations = _rows(locations_result.items)
        _record_status(locations_result, "method locations", diagnostics)
        die_result = query_port.get_die(implementation_offset)
        die = die_result.items[0] if die_result.items else None
        _record_status(die_result, "implementation DIE", diagnostics)
        abi_facts, parameter_locations = _abi_facts(query_port, die, diagnostics)
        locations = tuple((*locations, *parameter_locations))
        cfi_result = _cfi_rows(query_port, method, diagnostics)
        abi_facts["cfi_status"] = _query_status(cfi_result)
        return MethodContextPacket(
            declaration_die_offset=method.declaration_die_offset,
            implementation_die_offset=implementation_offset,
            declaration_cu_offset=method.declaration_cu_offset,
            implementation_cu_offset=_implementation_cu_offset(method, implementation_offset),
            code_ranges=_ranges(method),
            locations=locations,
            cfi=_rows(cfi_result.items),
            disassembly_addresses=tuple(item.address for item in method.instructions),
            relocation_ids=method.relocation_ids,
            abi_facts=abi_facts,
            diagnostics=tuple(dict.fromkeys(diagnostics)),
        )
    except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
        diagnostics.append(f"analytical method context query failed: {type(error).__name__}")
        return _empty_context(method, diagnostics)


def _abi_facts(
    query_port: DwarfQueryPort,
    die: Any,
    diagnostics: list[str],
) -> tuple[dict[str, object], tuple[dict[str, object], ...]]:
    if die is None:
        diagnostics.append("implementation DIE was not found in analytical store")
        return {}, ()
    attributes = getattr(die, "attributes", {})
    object_pointer = _object_pointer_name(die)
    parameter_facts, parameter_locations = _parameter_facts(query_port, die, object_pointer)
    facts: dict[str, object] = {
        "calling_convention": _attribute_text(attributes, "DW_AT_calling_convention"),
        "object_pointer": object_pointer,
        "return_location": _location_summary(query_port, die.offset, "DW_AT_return_location"),
        **parameter_facts,
    }

    return facts, parameter_locations


def _parameter_facts(
    query_port: DwarfQueryPort,
    die: Any,
    object_pointer: str | None,
) -> tuple[dict[str, object], tuple[dict[str, object], ...]]:
    parameter_locations: list[dict[str, object]] = []
    parameter_names: list[str] = []
    artificial: list[str] = []
    hidden: list[str] = []
    for child in die.iter_children():
        observation = _parameter_observation(query_port, child, object_pointer)
        if observation is None:
            continue
        name, child_offset, is_artificial, is_hidden, child_rows = observation
        if is_artificial:
            artificial.append(name)
        if is_hidden:
            hidden.append(name)
        parameter_locations.extend(
            {
                **row,
                "parameter_name": name,
                "parameter_die_offset": child_offset,
                "artificial": is_artificial,
            }
            for row in child_rows
        )
        if child_rows:
            parameter_names.append(name)
    return (
        {
            "parameter_locations": tuple(parameter_names),
            "artificial_parameters": tuple(artificial),
            "hidden_parameters": tuple(hidden),
            "hidden_return": (
                any("sret" in name.lower() or "return" in name.lower() for name in hidden) or None
            ),
        },
        tuple(parameter_locations),
    )


def _parameter_observation(
    query_port: DwarfQueryPort,
    child: Any,
    object_pointer: str | None,
) -> tuple[str, int, bool, bool, tuple[dict[str, object], ...]] | None:
    if getattr(child, "tag", None) != "DW_TAG_formal_parameter":
        return None
    child_attributes = getattr(child, "attributes", {})
    child_offset = getattr(child, "offset", None)
    if not isinstance(child_offset, int):
        return None
    name = _attribute_text(child_attributes, "DW_AT_name") or f"die:0x{child_offset:x}"
    is_artificial = _attribute_bool(child_attributes, "DW_AT_artificial") is True
    is_hidden = is_artificial and name != object_pointer and name.lower() not in {"this", "__this"}
    child_rows = _rows(query_port.find_locations(child_offset).items)
    return name, child_offset, is_artificial, is_hidden, child_rows


def _cfi_rows(
    query_port: DwarfQueryPort,
    method: MethodAssemblyEvidence,
    diagnostics: list[str],
) -> Any:
    start = method.selected_function_address
    size = method.selected_function_size
    if start is None or size is None or size <= 0 or start + size >= 1 << 64:
        diagnostics.append("method range is incomplete for analytical CFI")
        return _empty_result()
    result = query_port.find_frames(start_address=start, end_address=start + size)
    _record_status(result, "method CFI", diagnostics)
    if not result.items:
        diagnostics.append("analytical store has no CFI row covering the method range")
    return result


def _location_summary(query_port: DwarfQueryPort, die_offset: int, attribute: str) -> str | None:
    rows = _rows(query_port.find_locations(die_offset, attribute_name=attribute).items)
    if not rows:
        return None
    value = rows[0].get("expression") or rows[0].get("details") or rows[0].get("decoded_value")
    return str(value) if value is not None else None


def _empty_context(
    method: MethodAssemblyEvidence, diagnostics: Iterable[str]
) -> MethodContextPacket:
    return MethodContextPacket(
        declaration_die_offset=method.declaration_die_offset,
        implementation_die_offset=method.selected_implementation_die_offset,
        declaration_cu_offset=method.declaration_cu_offset,
        implementation_cu_offset=None,
        code_ranges=_ranges(method),
        disassembly_addresses=tuple(item.address for item in method.instructions),
        relocation_ids=method.relocation_ids,
        diagnostics=tuple(dict.fromkeys(diagnostics)),
    )


def _ranges(method: MethodAssemblyEvidence) -> tuple[tuple[int, int, str], ...]:
    return tuple(
        (item.start_address, item.end_address, item.source)
        for candidate in method.candidates
        for item in candidate.code_ranges
    )


def _implementation_cu_offset(
    method: MethodAssemblyEvidence, implementation_offset: int
) -> int | None:
    candidate = next(
        (
            item
            for item in method.candidates
            if item.implementation_die_offset == implementation_offset
        ),
        None,
    )
    return candidate.implementation_cu_offset if candidate is not None else None


def _selected_candidate(method: MethodAssemblyEvidence) -> MethodImplementationCandidate | None:
    if len(method.candidates) != 1:
        return None
    return method.candidates[0]


def _object_pointer_name(die: Any) -> str | None:
    getter = getattr(die, "get_DIE_from_attribute", None)
    target = getter("DW_AT_object_pointer") if callable(getter) else None
    if target is None:
        return None
    return _attribute_text(getattr(target, "attributes", {}), "DW_AT_name")


def _attribute_text(attributes: Any, name: str) -> str | None:
    value = getattr(attributes.get(name), "value", None) if isinstance(attributes, dict) else None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value) if value is not None else None


def _attribute_bool(attributes: Any, name: str) -> bool | None:
    value = getattr(attributes.get(name), "value", None) if isinstance(attributes, dict) else None
    return value if isinstance(value, bool) else None


def _rows(items: Iterable[Any]) -> tuple[dict[str, object], ...]:
    return tuple(dict(item) for item in items if isinstance(item, dict))


def _record_status(result: Any, label: str, diagnostics: list[str]) -> None:
    status = _query_status(result)
    if status == "complete":
        return
    diagnostics.extend(str(item) for item in getattr(result, "diagnostics", ()))
    diagnostics.append(f"{label} query status: {status}")


def _query_status(result: Any) -> str:
    status = getattr(result, "status", "unavailable")
    return str(getattr(status, "value", status))


def _empty_result() -> QueryResult:
    return QueryResult(QueryStatus.NOT_FOUND)


__all__ = ["attach_analytical_context"]
