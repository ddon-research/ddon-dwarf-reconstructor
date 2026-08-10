"""Generator-compatible line-program views reconstructed from analytical rows."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StoreLineFile:
    """One DWARF line-program file entry."""

    name: str
    dir_index: int = 0
    timestamp: int | None = None
    size: int | None = None


@dataclass(frozen=True, slots=True)
class StoreLineHeader:
    """Minimal line header used by declaration-file consumers."""

    file_entry: tuple[StoreLineFile, ...]
    include_directory: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StoreLineState:
    """Line state reconstructed from one normalized line row."""

    address: int | None = None
    file: int | None = None
    line: int | None = None
    column: int | None = None
    op_index: int | None = None
    is_stmt: bool | None = None
    basic_block: bool | None = None
    end_sequence: bool | None = None
    prologue_end: bool | None = None
    epilogue_begin: bool | None = None
    isa: int | None = None
    discriminator: int | None = None


@dataclass(frozen=True, slots=True)
class StoreLineEntry:
    """One line-program state transition."""

    state: StoreLineState
    command: int | None = None
    is_extended: bool = False
    args: Any = ()


@dataclass(frozen=True, slots=True)
class StoreLineProgram:
    """Small pyelftools-compatible line-program facade."""

    header: StoreLineHeader
    entries: tuple[StoreLineEntry, ...]
    program_start_offset: int | None = None

    def get_entries(self) -> tuple[StoreLineEntry, ...]:
        """Return stable traversal-order line entries."""
        return self.entries


def build_line_program(rows: Iterable[dict[str, Any]]) -> StoreLineProgram | None:
    """Reconstruct a line program from normalized rows.

    The producer records explicit file/directory header rows alongside state
    rows.  Older stores without header rows remain readable through the
    state-row fallback.  Repeated file indexes are folded deterministically
    while line state remains one-to-one with the input rows.
    """
    ordered_rows = tuple(rows)
    if not ordered_rows:
        return None
    file_rows = tuple(row for row in ordered_rows if row.get("entry_kind") == "file")
    directory_rows = tuple(row for row in ordered_rows if row.get("entry_kind") == "directory")
    state_rows = tuple(
        row for row in ordered_rows if row.get("entry_kind") not in {"file", "directory"}
    )
    files, directories, program_offset = _header_rows(directory_rows, file_rows)
    entries, program_offset = _state_rows(state_rows, files, directories, program_offset)
    max_index = max(files, default=0)
    file_entries = tuple(files.get(index, StoreLineFile("")) for index in range(1, max_index + 1))
    max_directory = max(directories, default=0)
    return StoreLineProgram(
        header=StoreLineHeader(
            file_entries,
            tuple(directories.get(index, "") for index in range(1, max_directory + 1)),
        ),
        entries=tuple(entries),
        program_start_offset=program_offset,
    )


def _header_rows(
    directory_rows: tuple[dict[str, Any], ...],
    file_rows: tuple[dict[str, Any], ...],
) -> tuple[dict[int, StoreLineFile], dict[int, str], int | None]:
    directories, program_offset = _directory_rows(directory_rows)
    files: dict[int, StoreLineFile] = {}
    for row in file_rows:
        _add_file_row(files, directories, row)
        program_offset = _first_int(program_offset, row.get("program_offset"))
    return files, directories, program_offset


def _directory_rows(rows: tuple[dict[str, Any], ...]) -> tuple[dict[int, str], int | None]:
    directories: dict[int, str] = {}
    program_offset: int | None = None
    for row in rows:
        directory_index = _int(row.get("directory_index"))
        directory = _string(row.get("directory"))
        if directory_index is not None and directory is not None:
            directories[directory_index] = directory
        program_offset = _first_int(program_offset, row.get("program_offset"))
    return directories, program_offset


def _add_file_row(
    files: dict[int, StoreLineFile],
    directories: dict[int, str],
    row: dict[str, Any],
) -> None:
    file_index = _int(row.get("file_index"))
    if file_index is None or file_index <= 0:
        return
    directory_index = _int(row.get("directory_index")) or 0
    directory = _string(row.get("directory"))
    if directory_index > 0 and directory is not None:
        directories[directory_index] = directory
    files[file_index] = StoreLineFile(
        name=_string(row.get("source_file")) or "",
        dir_index=directory_index,
    )


def _state_rows(
    state_rows: tuple[dict[str, Any], ...],
    files: dict[int, StoreLineFile],
    directories: dict[int, str],
    program_offset: int | None,
) -> tuple[list[StoreLineEntry], int | None]:
    entries: list[StoreLineEntry] = []
    for row in state_rows:
        program_offset = _first_int(program_offset, row.get("program_offset"))
        file_index = _int(row.get("file_index"))
        directory = _string(row.get("directory"))
        if directory and file_index is not None and file_index not in files:
            directory_index = len(directories) + 1
            directories[directory_index] = directory
        if file_index is not None and file_index > 0:
            files.setdefault(
                file_index,
                StoreLineFile(
                    name=_string(row.get("source_file")) or "",
                    dir_index=_directory_index(directories, directory),
                ),
            )
        entries.append(_entry(row))
    return entries, program_offset


def _entry(row: dict[str, Any]) -> StoreLineEntry:
    details = row.get("details")
    if not isinstance(details, dict):
        details = {}
    return StoreLineEntry(
        state=StoreLineState(
            address=_int(row.get("address")),
            file=_int(row.get("file_index")),
            line=_int(row.get("line")),
            column=_int(row.get("column")),
            op_index=_int(row.get("op_index")),
            is_stmt=_bool(row.get("is_stmt")),
            basic_block=_bool(row.get("basic_block")),
            end_sequence=_bool(row.get("end_sequence")),
            prologue_end=_bool(row.get("prologue_end")),
            epilogue_begin=_bool(row.get("epilogue_begin")),
            isa=_int(row.get("isa")),
            discriminator=_int(row.get("discriminator")),
        ),
        command=_int(row.get("command")),
        is_extended=bool(details.get("is_extended", False)),
        args=details.get("args", ()),
    )


def _first_int(current: int | None, candidate: Any) -> int | None:
    return current if current is not None else _int(candidate)


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _directory_index(directories: dict[int, str], directory: str | None) -> int:
    if not directory:
        return 0
    for index, value in directories.items():
        if value == directory:
            return index
    index = max(directories, default=0) + 1
    directories[index] = directory
    return index
