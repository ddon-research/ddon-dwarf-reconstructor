"""Emit typed DWARF side tables while the owning CU is still available."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from ...domain.models.analytical_dwarf import DwarfRecordKind, QueryStatus
from .json_codec import tag_value
from .record_sink import RecordWriter

_NAME_ATTRIBUTES = {
    "DW_AT_name",
    "DW_AT_linkage_name",
    "DW_AT_MIPS_linkage_name",
}
_LOCATION_ATTRIBUTES = {
    "DW_AT_location",
    "DW_AT_data_member_location",
    "DW_AT_frame_base",
    "DW_AT_vtable_elem_location",
    "DW_AT_string_length",
    "DW_AT_return_addr",
    "DW_AT_static_link",
}
_LOCATION_LIST_FORMS = {
    "DW_FORM_loclistx",
    "DW_FORM_sec_offset",
}
_RECOVERABLE_DWARF_ERRORS = (
    AttributeError,
    IndexError,
    KeyError,
    NotImplementedError,
    RuntimeError,
    ValueError,
)


class DwarfSemanticEmitter:
    """Emit ranges, locations, lines, abbreviations, names, and frames."""

    def __init__(self, source_id: str, writer: RecordWriter, dwarf_info: Any = None) -> None:
        self.source_id = source_id
        self.writer = writer
        self.dwarf_info = dwarf_info
        self._active_cu: Any = None
        self._active_unit_offset: int | None = None

    def begin_unit(self, unit_offset: int) -> None:
        """Cache the current CU offset for the hot per-DIE emission loop."""
        self._active_cu = None
        self._active_unit_offset = unit_offset

    def write_unit_side_tables(self, cu: Any) -> None:
        """Emit CU-local tables without requesting another DIE traversal."""
        self._activate_cu(cu)
        self._write_abbreviations(cu)
        self._write_lines(cu)

    def write_parse_error(self, cu: Any, details: dict[str, Any]) -> None:
        """Preserve a malformed abbreviation as a queryable raw diagnostic."""
        self._activate_cu(cu)
        self.writer.write(
            {
                "record_type": DwarfRecordKind.ABBREVIATION.value,
                "source_id": self.source_id,
                "unit_offset": self._active_unit_offset,
                "record_offset": details.get("failure_offset"),
                "abbrev_code": details.get("abbrev_code"),
                "tag": None,
                "has_children": None,
                "parser_status": QueryStatus.PARTIAL.value,
                "details": details,
            }
        )

    def write_attribute_side_tables(
        self,
        cu: Any,
        die: Any,
        name: str,
        attribute: Any,
    ) -> None:
        """Decode one attribute's range/location payload when supported."""
        self._activate_cu(cu)
        if name in _NAME_ATTRIBUTES:
            self._write_name(die, name, attribute)
        if name == "DW_AT_ranges":
            self._write_ranges(cu, die, name, attribute)
        if name in _LOCATION_ATTRIBUTES:
            self._write_locations(die, name, attribute)

    def write_die_side_tables(self, cu: Any, die: Any) -> None:
        """Emit a derived low/high-PC range without revisiting the DIE."""
        self._activate_cu(cu)
        attributes = getattr(die, "attributes", {})
        if not isinstance(attributes, Mapping):
            return
        low = attributes.get("DW_AT_low_pc")
        high = attributes.get("DW_AT_high_pc")
        if low is None or high is None:
            return
        low_value = _integer_or_none(getattr(low, "value", None))
        high_value = _integer_or_none(getattr(high, "value", None))
        if low_value is None or high_value is None:
            return
        if str(getattr(high, "form", "")).endswith("addr"):
            end = high_value
        else:
            end = low_value + high_value
        self.writer.write(
            {
                "record_type": DwarfRecordKind.RANGE.value,
                "source_id": self.source_id,
                "unit_offset": self._active_unit_offset,
                "die_offset": _integer(die, "offset"),
                "ordinal": 0,
                "attribute_name": "DW_AT_low_pc/DW_AT_high_pc",
                "record_offset": _integer_or_none(getattr(low, "offset", None)),
                "record_length": None,
                "entry_kind": "low_high_pc",
                "start_address": low_value,
                "end_address": end,
                "base_address": None,
                "is_absolute": True,
                "parser_status": QueryStatus.COMPLETE.value,
                "details": {
                    "low_form": str(getattr(low, "form", "")),
                    "high_form": str(getattr(high, "form", "")),
                },
            }
        )

    def write_global_records(self) -> None:
        """Emit frame tables once, after all CU-local records are published."""
        if self.dwarf_info is None:
            return
        self._write_frames(".debug_frame", "CFI_entries")
        self._write_frames(".eh_frame", "EH_CFI_entries")

    def write_macro_section(
        self,
        section_name: str,
        size: int,
        raw_path: str,
        raw_sha256: str,
    ) -> None:
        """Preserve macro sections explicitly when pyelftools has no macro API."""
        if section_name not in {
            ".debug_macro",
            ".debug_macinfo",
            ".zdebug_macro",
            ".zdebug_macinfo",
        }:
            return
        self.writer.write(
            {
                "record_type": DwarfRecordKind.MACRO.value,
                "source_id": self.source_id,
                "section_name": section_name,
                "record_offset": 0,
                "record_length": size,
                "macro_kind": "raw_section",
                "raw_path": raw_path,
                "raw_sha256": raw_sha256,
                "parser_status": "raw_only",
                "details": {
                    "reason": "pyelftools-0.33 exposes no public macro decoder",
                    "section_preserved": True,
                },
            }
        )

    def _activate_cu(self, cu: Any) -> None:
        if self._active_cu is cu:
            return
        self._active_cu = cu
        if self._active_unit_offset is None:
            self._active_unit_offset = _integer(cu, "cu_offset")

    def _write_abbreviations(self, cu: Any) -> None:
        getter = getattr(cu, "get_abbrev_table", None)
        if not callable(getter):
            return
        table = getter()
        declarations = getattr(table, "_abbrev_map", {})
        if not isinstance(declarations, Mapping):
            return
        table_offset = _integer_or_none(getattr(table, "offset", None))
        for code, declaration in sorted(declarations.items(), key=lambda item: int(item[0])):
            specs = getattr(declaration, "iter_attr_specs", None)
            attributes = list(cast(Any, specs)()) if callable(specs) else []
            self.writer.write(
                {
                    "record_type": DwarfRecordKind.ABBREVIATION.value,
                    "source_id": self.source_id,
                    "unit_offset": self._active_unit_offset,
                    "record_offset": table_offset,
                    "abbrev_code": _integer_or_none(code),
                    "tag": _text_or_none(_mapping_value(declaration, "tag")),
                    "has_children": bool(
                        declaration.has_children()
                        if callable(getattr(declaration, "has_children", None))
                        else False
                    ),
                    "parser_status": QueryStatus.COMPLETE.value,
                    "details": {"attribute_specs": attributes},
                }
            )

    def _write_lines(self, cu: Any) -> None:
        if self.dwarf_info is None:
            return
        getter = getattr(self.dwarf_info, "line_program_for_CU", None)
        if not callable(getter):
            return
        try:
            program = cast(Any, getter(cu))
        except (AttributeError, IndexError, KeyError, RuntimeError, ValueError) as error:
            self._write_partial_line(error)
            return
        if program is None:
            return
        entries = program.get_entries()
        header = getattr(program, "header", {})
        program_offset = _integer_or_none(getattr(program, "program_start_offset", None))
        self._write_line_directories(header, program_offset)
        self._write_line_files(header, program_offset)
        for ordinal, entry in enumerate(entries):
            state = getattr(entry, "state", None)
            self.writer.write(
                {
                    "record_type": DwarfRecordKind.LINE.value,
                    "source_id": self.source_id,
                    "unit_offset": self._active_unit_offset,
                    "ordinal": ordinal,
                    "entry_kind": "state",
                    "program_offset": program_offset,
                    "record_offset": ordinal,
                    "command": _integer_or_none(getattr(entry, "command", None)),
                    "address": _integer_or_none(getattr(state, "address", None)),
                    "file_index": _integer_or_none(getattr(state, "file", None)),
                    "source_file": _line_file_name(header, state),
                    "directory": _line_directory(header, state),
                    "line": _integer_or_none(getattr(state, "line", None)),
                    "column": _integer_or_none(getattr(state, "column", None)),
                    "op_index": _integer_or_none(getattr(state, "op_index", None)),
                    "is_stmt": _bool_or_none(getattr(state, "is_stmt", None)),
                    "basic_block": _bool_or_none(getattr(state, "basic_block", None)),
                    "end_sequence": _bool_or_none(getattr(state, "end_sequence", None)),
                    "prologue_end": _bool_or_none(getattr(state, "prologue_end", None)),
                    "epilogue_begin": _bool_or_none(getattr(state, "epilogue_begin", None)),
                    "isa": _integer_or_none(getattr(state, "isa", None)),
                    "discriminator": _integer_or_none(getattr(state, "discriminator", None)),
                    "details": {
                        "command": _integer_or_none(getattr(entry, "command", None)),
                        "is_extended": bool(getattr(entry, "is_extended", False)),
                        "args": tag_value(getattr(entry, "args", [])),
                    },
                }
            )

    def _write_line_directories(self, header: Any, program_offset: int | None) -> None:
        directories = _mapping_value(header, "include_directory")
        if not isinstance(directories, (list, tuple)):
            return
        for index, directory in enumerate(directories, 1):
            self.writer.write(
                {
                    "record_type": DwarfRecordKind.LINE.value,
                    "source_id": self.source_id,
                    "unit_offset": self._active_unit_offset,
                    "ordinal": index - 1,
                    "entry_kind": "directory",
                    "program_offset": program_offset,
                    "record_offset": index - 1,
                    "directory_index": index,
                    "directory": _text_value(directory),
                }
            )

    def _write_line_files(self, header: Any, program_offset: int | None) -> None:
        entries = _mapping_value(header, "file_entry")
        if not isinstance(entries, (list, tuple)):
            return
        for index, entry in enumerate(entries, 1):
            directory_index = _integer_or_none(_mapping_value(entry, "dir_index"))
            self.writer.write(
                {
                    "record_type": DwarfRecordKind.LINE.value,
                    "source_id": self.source_id,
                    "unit_offset": self._active_unit_offset,
                    "ordinal": index - 1,
                    "entry_kind": "file",
                    "program_offset": program_offset,
                    "record_offset": index - 1,
                    "file_index": index,
                    "directory_index": directory_index,
                    "source_file": _text_value(_mapping_value(entry, "name")),
                    "directory": _line_directory_for_entry(header, entry),
                }
            )

    def _write_partial_line(self, error: Exception) -> None:
        self.writer.write(
            {
                "record_type": DwarfRecordKind.LINE.value,
                "source_id": self.source_id,
                "unit_offset": self._active_unit_offset,
                "ordinal": 0,
                "program_offset": None,
                "record_offset": 0,
                "parser_status": QueryStatus.PARTIAL.value,
                "details": _error_details(error),
            }
        )

    def _write_name(self, die: Any, name: str, attribute: Any) -> None:
        value = getattr(attribute, "value", None)
        text = _text_value(value)
        if text is None:
            return
        self.writer.write(
            {
                "record_type": DwarfRecordKind.NAME.value,
                "source_id": self.source_id,
                "unit_offset": self._active_unit_offset,
                "die_offset": _integer(die, "offset"),
                "ordinal": 0,
                "name": text,
                "name_kind": "die_attribute",
                "attribute_name": name,
                "parser_status": QueryStatus.COMPLETE.value,
                "details": {
                    "raw_value": tag_value(getattr(attribute, "raw_value", value)),
                    "decoded_value": tag_value(value),
                },
            }
        )

    def _write_ranges(self, cu: Any, die: Any, name: str, attribute: Any) -> None:
        raw = _integer_or_none(getattr(attribute, "raw_value", None))
        if raw is None:
            raw = _integer_or_none(getattr(attribute, "value", None))
        range_lists = getattr(self.dwarf_info, "range_lists", None)
        lists = range_lists() if callable(range_lists) else None
        if raw is None or lists is None:
            self._write_range_partial(die, name, attribute, "range_list_unavailable")
            return
        try:
            entries = cast(Any, lists).get_range_list_at_offset(raw, cu=cu)
        except _RECOVERABLE_DWARF_ERRORS as error:
            self._write_range_partial(die, name, attribute, _error_details(error))
            return
        for ordinal, entry in enumerate(entries):
            self._write_range_entry(die, name, ordinal, entry)

    def _write_range_entry(self, die: Any, name: str, ordinal: int, entry: Any) -> None:
        start = _integer_or_none(getattr(entry, "begin_offset", None))
        end = _integer_or_none(getattr(entry, "end_offset", None))
        base = _integer_or_none(getattr(entry, "base_address", None))
        self.writer.write(
            {
                "record_type": DwarfRecordKind.RANGE.value,
                "source_id": self.source_id,
                "unit_offset": self._active_unit_offset,
                "die_offset": _integer(die, "offset"),
                "ordinal": ordinal,
                "attribute_name": name,
                "record_offset": _integer_or_none(getattr(entry, "entry_offset", None)),
                "record_length": _integer_or_none(getattr(entry, "entry_length", None)),
                "entry_kind": "base_address" if base is not None else "range",
                "start_address": start,
                "end_address": end,
                "base_address": base,
                "is_absolute": _bool_or_none(getattr(entry, "is_absolute", None)),
                "parser_status": QueryStatus.COMPLETE.value,
                "details": {"raw_entry": tag_value(entry)},
            }
        )

    def _write_range_partial(self, die: Any, name: str, attribute: Any, details: Any) -> None:
        self.writer.write(
            {
                "record_type": DwarfRecordKind.RANGE.value,
                "source_id": self.source_id,
                "unit_offset": self._active_unit_offset,
                "die_offset": _integer(die, "offset"),
                "ordinal": 0,
                "attribute_name": name,
                "record_offset": _integer_or_none(getattr(attribute, "offset", None)),
                "entry_kind": "unresolved",
                "parser_status": QueryStatus.PARTIAL.value,
                "details": details,
            }
        )

    def _write_locations(self, die: Any, name: str, attribute: Any) -> None:
        value = getattr(attribute, "value", None)
        if isinstance(value, (list, tuple, bytes, bytearray)):
            self._write_location_entry(die, name, 0, value, None)
            return
        # DW_AT_data_member_location commonly uses DW_FORM_data1/data2/data4
        # for a constant member offset. Those scalar forms are values, not
        # offsets into .debug_loc. Treating them as list offsets can make a
        # malformed or unrelated location list scan the entire section.
        form = str(getattr(attribute, "form", ""))
        if form not in _LOCATION_LIST_FORMS:
            self._write_location_entry(die, name, 0, value, None)
            return
        raw = _integer_or_none(getattr(attribute, "raw_value", value))
        location_lists = getattr(self.dwarf_info, "location_lists", None)
        lists = location_lists() if callable(location_lists) else None
        if raw is None or lists is None:
            self._write_location_entry(die, name, 0, value, "location_list_unavailable")
            return
        try:
            entries = cast(Any, lists).get_location_list_at_offset(raw, die=die)
        except _RECOVERABLE_DWARF_ERRORS as error:
            self._write_location_entry(die, name, 0, value, _error_details(error))
            return
        for ordinal, entry in enumerate(entries):
            self._write_location_entry(die, name, ordinal, entry, None)

    def _write_location_entry(
        self, die: Any, name: str, ordinal: int, entry: Any, error: Any
    ) -> None:
        expression = getattr(entry, "loc_expr", entry)
        status = QueryStatus.PARTIAL.value if error is not None else QueryStatus.COMPLETE.value
        self.writer.write(
            {
                "record_type": DwarfRecordKind.LOCATION.value,
                "source_id": self.source_id,
                "unit_offset": self._active_unit_offset,
                "die_offset": _integer(die, "offset"),
                "ordinal": ordinal,
                "attribute_name": name,
                "record_offset": _integer_or_none(getattr(entry, "entry_offset", None)),
                "record_length": _integer_or_none(getattr(entry, "entry_length", None)),
                "entry_kind": "expression" if isinstance(expression, (list, tuple)) else "entry",
                "start_address": _integer_or_none(getattr(entry, "begin_offset", None)),
                "end_address": _integer_or_none(getattr(entry, "end_offset", None)),
                "is_absolute": _bool_or_none(getattr(entry, "is_absolute", None)),
                "expression": tag_value(expression),
                "parser_status": status,
                "details": error,
            }
        )

    def _write_frames(self, section_name: str, method_name: str) -> None:
        getter = getattr(self.dwarf_info, method_name, None)
        if not callable(getter):
            return
        try:
            entries = cast(Any, getter)()
        except (
            AttributeError,
            IndexError,
            KeyError,
            RuntimeError,
            ValueError,
        ) as error:
            self.writer.write(
                {
                    "record_type": DwarfRecordKind.FRAME.value,
                    "source_id": self.source_id,
                    "section_name": section_name,
                    "record_offset": 0,
                    "frame_kind": "section",
                    "parser_status": QueryStatus.PARTIAL.value,
                    "details": _error_details(error),
                }
            )
            return
        for ordinal, entry in enumerate(entries):
            header = getattr(entry, "header", {})
            decoded, status, decode_details = _decoded_frame(entry)
            self.writer.write(
                {
                    "record_type": DwarfRecordKind.FRAME.value,
                    "source_id": self.source_id,
                    "section_name": section_name,
                    "record_offset": _integer_or_none(getattr(entry, "offset", None)),
                    "record_length": _integer_or_none(_mapping_value(header, "length")),
                    "frame_kind": type(entry).__name__,
                    "initial_address": _integer_or_none(_mapping_value(header, "initial_location")),
                    "address_range": _integer_or_none(_mapping_value(header, "address_range")),
                    "parser_status": status,
                    "details": {
                        "ordinal": ordinal,
                        "header": tag_value(header),
                        "instructions": tag_value(getattr(entry, "instructions", [])),
                        "decoded": decoded,
                        "decode_details": decode_details,
                    },
                }
            )


def _decoded_frame(entry: Any) -> tuple[Any, str, Any]:
    decoder = getattr(entry, "get_decoded", None)
    if not callable(decoder):
        return None, QueryStatus.COMPLETE.value, None
    try:
        return tag_value(decoder()), QueryStatus.COMPLETE.value, None
    except _RECOVERABLE_DWARF_ERRORS as error:
        return None, QueryStatus.PARTIAL.value, _error_details(error)


def _line_file_name(header: Any, state: Any) -> str | None:
    index = _integer_or_none(getattr(state, "file", None))
    entries = _mapping_value(header, "file_entry")
    if (
        index is None
        or not isinstance(entries, (list, tuple))
        or index <= 0
        or index > len(entries)
    ):
        return None
    return _text_value(_mapping_value(entries[index - 1], "name"))


def _line_directory(header: Any, state: Any) -> str | None:
    index = _integer_or_none(getattr(state, "file", None))
    entries = _mapping_value(header, "file_entry")
    directories = _mapping_value(header, "include_directory")
    if (
        index is None
        or not isinstance(entries, (list, tuple))
        or index <= 0
        or index > len(entries)
    ):
        return None
    directory_index = _integer_or_none(_mapping_value(entries[index - 1], "dir_index"))
    if directory_index is None or directory_index <= 0:
        return None
    if isinstance(directories, (list, tuple)) and directory_index <= len(directories):
        return _text_value(directories[directory_index - 1])
    return None


def _line_directory_for_entry(header: Any, entry: Any) -> str | None:
    directory_index = _integer_or_none(_mapping_value(entry, "dir_index"))
    directories = _mapping_value(header, "include_directory")
    if (
        directory_index is None
        or directory_index <= 0
        or not isinstance(directories, (list, tuple))
        or directory_index > len(directories)
    ):
        return None
    return _text_value(directories[directory_index - 1])


def _mapping_value(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    try:
        return value[key]
    except KeyError, TypeError, IndexError:
        return getattr(value, key, None)


def _integer(container: Any, key: str, default: int = 0) -> int:
    value = _mapping_value(container, key) if not isinstance(container, int) else container
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _integer_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _bool_or_none(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _text_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _text_value(value: Any) -> str | None:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value if isinstance(value, str) else None


def _error_details(error: Exception) -> dict[str, str]:
    return {"error_type": type(error).__name__, "error": str(error)[:512]}
