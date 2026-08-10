"""DIE/attribute emission for the one-pass analytical producer."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ...domain.models.analytical_dwarf import DwarfRecordKind, QueryStatus
from .json_codec import tag_value
from .record_sink import RecordWriter
from .semantic_emitter import DwarfSemanticEmitter

_MAX_INLINE_VALUE_BYTES = 1024 * 1024


class DwarfUnitEmitter:
    """Emit one CU and its explicit stack-based DIE traversal to a row sink."""

    def __init__(
        self,
        source_id: str,
        writer: RecordWriter,
        raw_values_dir: Path,
        dwarf_info: Any = None,
    ) -> None:
        self.source_id = source_id
        self.writer = writer
        self.raw_values_dir = raw_values_dir
        self.semantic = DwarfSemanticEmitter(source_id, writer, dwarf_info)

    def write_unit(self, cu: Any) -> dict[str, Any] | None:
        unit_offset = _integer(cu, "cu_offset", 0)
        self.semantic.begin_unit(unit_offset)
        header = getattr(cu, "header", {})
        stack: list[int] = []
        parse_error: dict[str, Any] | None = None
        try:
            for ordinal, die in enumerate(cu.iter_DIEs()):
                self._write_die(cu, die, ordinal, stack, unit_offset)
        except KeyError as error:
            parse_error = _parse_error_details(cu, error)
            self.semantic.write_parse_error(cu, parse_error)
        finally:
            self.semantic.write_unit_side_tables(cu)
        self.writer.write(
            {
                "record_type": DwarfRecordKind.UNIT.value,
                "source_id": self.source_id,
                "unit_offset": unit_offset,
                "unit_length": _integer_or_none(header, "unit_length"),
                "unit_type": _text_or_none(_value(header, "unit_type")),
                "header": tag_value(dict(header) if isinstance(header, Mapping) else header),
                "parser_status": (
                    QueryStatus.PARTIAL.value
                    if parse_error is not None
                    else QueryStatus.COMPLETE.value
                ),
                "details": parse_error,
            }
        )
        return parse_error

    def write_global_records(self) -> None:
        """Publish non-CU tables after the single CU iterator is exhausted."""
        self.semantic.write_global_records()

    def write_macro_section(
        self,
        section_name: str,
        size: int,
        raw_path: str,
        raw_sha256: str,
    ) -> None:
        """Publish the explicit raw-only macro fallback record."""
        self.semantic.write_macro_section(section_name, size, raw_path, raw_sha256)

    def _write_die(
        self, cu: Any, die: Any, ordinal: int, stack: list[int], unit_offset: int
    ) -> None:
        is_null = _is_null_die(die)
        raw_depth = getattr(die, "depth", None)
        has_explicit_depth = isinstance(raw_depth, int) and raw_depth >= 0
        depth = raw_depth if has_explicit_depth else len(stack)
        if has_explicit_depth and depth < len(stack):
            del stack[depth:]
        parent_offset = _parent_offset(stack, depth, has_explicit_depth)
        die_offset = _integer(die, "offset", 0)
        self.writer.write(
            {
                "record_type": DwarfRecordKind.DIE.value,
                "source_id": self.source_id,
                "unit_offset": unit_offset,
                "die_offset": die_offset,
                "ordinal": ordinal,
                "tag": _text_or_none(getattr(die, "tag", None)),
                "abbrev_code": _integer_or_none(getattr(die, "abbrev_code", None)),
                "has_children": bool(getattr(die, "has_children", False)),
                "depth": depth,
                "parent_offset": parent_offset,
                "is_null": is_null,
            }
        )
        if not is_null:
            self._write_attributes(cu, die, unit_offset, die_offset)
            self._write_derived_indexes(cu, die, unit_offset, die_offset)
            if parent_offset is not None:
                self.writer.write(
                    {
                        "record_type": DwarfRecordKind.REFERENCE.value,
                        "source_id": self.source_id,
                        "unit_offset": unit_offset,
                        "die_offset": die_offset,
                        "attribute_name": "<parent>",
                        "relation": "parent",
                        "raw_target": parent_offset,
                        "target_offset": parent_offset,
                        "resolution_status": QueryStatus.COMPLETE.value,
                    }
                )
        if is_null:
            _close_parent(stack, depth, has_explicit_depth)
        elif bool(getattr(die, "has_children", False)):
            _open_parent(stack, depth, die_offset, has_explicit_depth)

    def _write_derived_indexes(self, cu: Any, die: Any, unit_offset: int, die_offset: int) -> None:
        """Publish name and method indexes without a second CU/DIE traversal."""
        attributes = getattr(die, "attributes", {})
        name_attribute = attributes.get("DW_AT_name") if isinstance(attributes, Mapping) else None
        name_value = getattr(name_attribute, "value", None)
        if name_attribute is not None and name_value is not None:
            self.writer.write(
                {
                    "record_type": DwarfRecordKind.INDEX.value,
                    "index_type": "definition",
                    "source_id": self.source_id,
                    "unit_offset": unit_offset,
                    "die_offset": die_offset,
                    "name": _text_value(name_value),
                    "tag": _text_or_none(getattr(die, "tag", None)),
                }
            )
        if getattr(die, "tag", None) != "DW_TAG_subprogram":
            return
        specification = (
            attributes.get("DW_AT_specification") if isinstance(attributes, Mapping) else None
        )
        if specification is None:
            return
        target_offset, status = _reference_target(cu, specification, unit_offset)
        self.writer.write(
            {
                "record_type": DwarfRecordKind.INDEX.value,
                "index_type": "method_implementation",
                "source_id": self.source_id,
                "unit_offset": unit_offset,
                "die_offset": die_offset,
                "name": _text_value(name_value) if name_value is not None else None,
                "raw_target": tag_value(getattr(specification, "value", None)),
                "target_offset": target_offset,
                "resolution_status": status.value,
            }
        )

    def _write_attributes(self, cu: Any, die: Any, unit_offset: int, die_offset: int) -> None:
        attributes = getattr(die, "attributes", {})
        if not isinstance(attributes, Mapping):
            return
        for ordinal, (name, attribute) in enumerate(attributes.items()):
            name_text = str(name)
            decoded = getattr(attribute, "value", None)
            raw = getattr(attribute, "raw_value", decoded)
            form = str(getattr(attribute, "form", ""))
            self.writer.write(
                {
                    "record_type": DwarfRecordKind.ATTRIBUTE.value,
                    "source_id": self.source_id,
                    "unit_offset": unit_offset,
                    "die_offset": die_offset,
                    "ordinal": ordinal,
                    "name": name_text,
                    "form": form,
                    "raw_value": self._tag_value(raw),
                    "decoded_value": self._tag_value(decoded),
                    "value_offset": _integer_or_none(getattr(attribute, "offset", None)),
                    "indirection_length": _integer_or_none(
                        getattr(attribute, "indirection_length", None)
                    ),
                }
            )
            self.semantic.write_attribute_side_tables(cu, die, name_text, attribute)
            if _is_reference_attribute(name_text, form):
                self._write_reference(cu, die, name_text, raw, unit_offset, die_offset)
        self.semantic.write_die_side_tables(cu, die)

    def _tag_value(self, value: Any) -> Any:
        """Keep ordinary values inline and externalize large byte payloads."""
        if (
            isinstance(value, (bytes, bytearray, memoryview))
            and len(value) > _MAX_INLINE_VALUE_BYTES
        ):
            payload = bytes(value)
            digest = hashlib.sha256(payload).hexdigest()
            destination = self.raw_values_dir / f"{digest}.bin"
            if not destination.is_file():
                temporary = destination.with_suffix(".partial")
                with temporary.open("wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, destination)
            return {
                "type": "external_bytes",
                "path": f"raw_values/{digest}.bin",
                "sha256": digest,
                "size": len(payload),
            }
        return tag_value(value)

    def _write_reference(
        self,
        cu: Any,
        die: Any,
        name: str,
        raw: Any,
        unit_offset: int,
        die_offset: int,
    ) -> None:
        attribute = getattr(die, "attributes", {}).get(name)
        target_offset, status = _reference_target(cu, attribute, unit_offset)
        self.writer.write(
            {
                "record_type": DwarfRecordKind.REFERENCE.value,
                "source_id": self.source_id,
                "unit_offset": unit_offset,
                "die_offset": die_offset,
                "attribute_name": name,
                "relation": "attribute_reference",
                "raw_target": tag_value(raw),
                "target_offset": target_offset,
                "resolution_status": status.value,
            }
        )


def _value(container: Any, key: str) -> Any:
    try:
        return container[key]
    except KeyError, TypeError:
        return getattr(container, key, None)


def _integer(container: Any, key: str, default: int = 0) -> int:
    value = _value(container, key) if not isinstance(container, int) else container
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _integer_or_none(value: Any, key: str | None = None) -> int | None:
    candidate = _value(value, key) if key is not None else value
    return candidate if isinstance(candidate, int) and not isinstance(candidate, bool) else None


def _parent_offset(stack: list[int], depth: int, has_explicit_depth: bool) -> int | None:
    """Return the open DIE parent for a flattened CU iterator."""
    if has_explicit_depth:
        return stack[depth - 1] if depth > 0 and depth <= len(stack) else None
    return stack[-1] if stack else None


def _close_parent(stack: list[int], depth: int, has_explicit_depth: bool) -> None:
    """Pop the DIE whose child list is terminated by this null DIE."""
    if has_explicit_depth:
        del stack[max(depth - 1, 0) :]
    elif stack:
        stack.pop()


def _open_parent(stack: list[int], depth: int, die_offset: int, has_explicit_depth: bool) -> None:
    """Record a DIE with children as the next open parent."""
    if not has_explicit_depth or len(stack) == depth:
        stack.append(die_offset)
    else:
        stack[depth] = die_offset


def _text_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _text_value(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _is_null_die(die: Any) -> bool:
    method = getattr(die, "is_null", None)
    if callable(method):
        try:
            return bool(method())
        except AttributeError, RuntimeError, TypeError, ValueError:
            return False
    return getattr(die, "tag", None) is None


def _is_reference_attribute(name: str, form: str) -> bool:
    return form.startswith("DW_FORM_ref") or name in {
        "DW_AT_type",
        "DW_AT_specification",
        "DW_AT_abstract_origin",
        "DW_AT_containing_type",
        "DW_AT_import",
        "DW_AT_signature",
    }


def _parse_error_details(cu: Any, error: KeyError) -> dict[str, Any]:
    """Describe a malformed CU while its lazy parser state is still available."""
    abbrev_code = error.args[0] if error.args and isinstance(error.args[0], int) else None
    table_getter = getattr(cu, "get_abbrev_table", None)
    table = table_getter() if callable(table_getter) else None
    declarations = getattr(table, "_abbrev_map", {}) if table is not None else {}
    valid_codes = (
        sorted(int(code) for code in declarations) if isinstance(declarations, Mapping) else []
    )
    failure_offset = _next_die_offset(cu)
    return {
        "error_type": type(error).__name__,
        "message": repr(error),
        "abbrev_code": abbrev_code,
        "valid_abbrev_min": valid_codes[0] if valid_codes else None,
        "valid_abbrev_max": valid_codes[-1] if valid_codes else None,
        "failure_offset": failure_offset,
        "parsed_die_count": _parsed_die_count(cu),
        "raw_prefix_hex": _raw_prefix(cu, failure_offset),
        "raw_section_preserved": True,
    }


def _parsed_die_count(cu: Any) -> int:
    cached = getattr(cu, "_dielist", ())
    return len(cached) if isinstance(cached, (list, tuple)) else 0


def _next_die_offset(cu: Any) -> int | None:
    cached = getattr(cu, "_dielist", ())
    if not isinstance(cached, (list, tuple)) or not cached:
        return None
    last = cached[-1]
    offset = _integer_or_none(getattr(last, "offset", None))
    size = _integer_or_none(getattr(last, "size", None))
    return offset + size if offset is not None and size is not None else None


def _raw_prefix(cu: Any, offset: int | None) -> str | None:
    if offset is None:
        return None
    dwarf_info = getattr(cu, "dwarfinfo", None)
    section = getattr(dwarf_info, "debug_info_sec", None)
    stream = getattr(section, "stream", None)
    if stream is None:
        return None
    position = stream.tell()
    try:
        stream.seek(offset)
        return stream.read(16).hex()
    finally:
        stream.seek(position)


def _reference_target(
    cu: Any, attribute: Any, unit_offset: int | None = None
) -> tuple[int | None, QueryStatus]:
    """Decode a reference offset without navigating into another CU."""
    if attribute is None:
        return None, QueryStatus.NOT_FOUND
    form = str(getattr(attribute, "form", ""))
    raw = _integer_or_none(getattr(attribute, "raw_value", None))
    if raw is None:
        raw = _integer_or_none(getattr(attribute, "value", None))
    if raw is None:
        return None, QueryStatus.PARTIAL
    if form in {
        "DW_FORM_ref1",
        "DW_FORM_ref2",
        "DW_FORM_ref4",
        "DW_FORM_ref8",
        "DW_FORM_ref",
        "DW_FORM_ref_udata",
    }:
        offset = unit_offset if unit_offset is not None else _integer(cu, "cu_offset", 0)
        return offset + raw, QueryStatus.COMPLETE
    if form == "DW_FORM_ref_addr":
        return raw, QueryStatus.COMPLETE
    return None, QueryStatus.PARTIAL
