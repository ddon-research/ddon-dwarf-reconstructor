#!/usr/bin/env python3

"""File registry for mapping classes to their declared files.

Maps classes to their source file declarations using DWARF DW_AT_decl_file
attributes. Handles compilation unit file lists and normalizes paths.
"""

from typing import TYPE_CHECKING

from ....core.dwarf import decode_dwarf_string
from ....core.observability import get_logger

if TYPE_CHECKING:
    from ....core.dwarf import DwarfInfo

logger = get_logger(__name__)


class FileRegistry:
    """Maps classes to their declared source files.

    Uses DWARF DW_AT_decl_file attribute to locate class declarations.
    Each compilation unit has a file list (from DW_AT_stmt_list):
    - Index 0: main source file
    - Index 1+: included files

    Attributes:
        _file_lists: Cache of file lists per compilation unit offset
        _class_files: Map of class name -> file path
        _uncategorized: Set of classes with no file info
    """

    def __init__(self, dwarf_info: DwarfInfo):
        """Initialize file registry with DWARF information.

        Args:
            dwarf_info: DWARF information structure from pyelftools
        """
        self.dwarf_info = dwarf_info
        self._file_lists: dict[int, list[str]] = {}  # CU offset -> file list
        self._class_files: dict[str, str | None] = {}  # class name -> file
        self._uncategorized: set[str] = set()  # classes without file info

    def register_class(
        self,
        class_name: str,
        cu_offset: int,
        decl_file_index: int | str | None,
    ) -> None:
        """Register a class with its declared file.

        Args:
            class_name: Name of the class
            cu_offset: Offset of the compilation unit containing this class
            decl_file_index: Either:
                            - Integer index into CU's file list (from DW_AT_decl_file)
                            - String file path (already resolved)
                            - None if file info not available
        """
        if decl_file_index is None:
            self._class_files[class_name] = None
            self._uncategorized.add(class_name)
            logger.debug(f"Class {class_name}: no file info available")
            return

        # If it's already a string path, use it directly
        if isinstance(decl_file_index, str):
            self._class_files[class_name] = decl_file_index
            logger.debug(f"Class {class_name}: file path {decl_file_index}")
            return

        # Otherwise, treat as integer index and look up in file list
        # Get file list for this CU if not cached
        if cu_offset not in self._file_lists:
            self._file_lists[cu_offset] = self._extract_file_list(cu_offset)

        file_list = self._file_lists[cu_offset]

        # Validate file index
        if decl_file_index < 0 or decl_file_index >= len(file_list):
            logger.warning(
                f"Invalid file index {decl_file_index} for class {class_name} "
                f"(CU has {len(file_list)} files)"
            )
            self._class_files[class_name] = None
            self._uncategorized.add(class_name)
            return

        file_path = file_list[decl_file_index]
        self._class_files[class_name] = file_path
        logger.debug(f"Class {class_name} -> {file_path}")

    def get_class_file(self, class_name: str) -> str | None:
        """Get declared file for a class.

        Args:
            class_name: Name of the class

        Returns:
            File path if known, None otherwise
        """
        return self._class_files.get(class_name)

    def get_classes_by_file(self) -> dict[str, list[str]]:
        """Group classes by their declaration files.

        Returns:
            Dictionary mapping file path -> list of class names
            File path may be None for classes without file info
        """
        classes_by_file: dict[str | None, list[str]] = {}

        for class_name, file_path in self._class_files.items():
            if file_path not in classes_by_file:
                classes_by_file[file_path] = []
            classes_by_file[file_path].append(class_name)

        # Convert None key to "UncategorizedDefinitions" string for output
        result: dict[str, list[str]] = {}
        for file_path, classes in classes_by_file.items():
            if file_path is None:
                result["UncategorizedDefinitions"] = classes
            else:
                result[file_path] = classes

        return result

    def get_uncategorized_classes(self) -> list[str]:
        """Get list of classes without file info.

        Returns:
            List of class names without declared files
        """
        return sorted(self._uncategorized)

    def _extract_file_list(self, cu_offset: int) -> list[str]:
        """Extract file list from compilation unit.

        Reads the DW_AT_stmt_list attribute to get the file list for a CU.
        Each CU can have different files (main + includes).

        Args:
            cu_offset: Offset of compilation unit

        Returns:
            List of file paths from the CU's statement list
        """
        try:
            # Find the CU containing this offset
            for cu in self.dwarf_info.iter_CUs():
                if cu.cu_offset == cu_offset:
                    # Get the line program (stmt_list)
                    line_program = self.dwarf_info.line_program_for_CU(cu)
                    if line_program:
                        # line_program.header.file_entry is the file list
                        files = line_program.header.file_entry
                        file_paths = []
                        for file_entry in files:
                            # file_entry has name, dir_index, timestamp, size
                            file_name = decode_dwarf_string(file_entry.name)
                            file_paths.append(file_name)
                        logger.debug(f"Extracted {len(file_paths)} files for CU 0x{cu_offset:x}")
                        return file_paths
        except (AttributeError, IndexError, KeyError, RuntimeError, TypeError, ValueError) as error:
            logger.debug(
                "Failed to extract file list for CU 0x%x: %s", cu_offset, error, exc_info=error
            )

        # Fallback: return empty list
        return []

    def has_uncategorized(self) -> bool:
        """Check if there are uncategorized classes.

        Returns:
            True if any classes lack file info
        """
        return len(self._uncategorized) > 0

    def summarize(self) -> str:
        """Generate summary of registered classes and files.

        Returns:
            Multi-line summary string
        """
        classes_by_file = self.get_classes_by_file()
        total_classes = sum(len(classes) for classes in classes_by_file.values())

        lines = [f"File Registry Summary ({total_classes} classes):"]
        for file_path in sorted(classes_by_file.keys()):
            classes = classes_by_file[file_path]
            display_path = file_path or "UncategorizedDefinitions"
            lines.append(f"  {display_path}: {len(classes)} classes")
            for cls_name in sorted(classes)[:3]:  # Show first 3
                lines.append(f"    - {cls_name}")
            if len(classes) > 3:
                lines.append(f"    ... and {len(classes) - 3} more")

        return "\n".join(lines)
