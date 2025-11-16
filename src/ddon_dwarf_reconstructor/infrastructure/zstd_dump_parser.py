#!/usr/bin/env python3

"""Parser for compressed llvm-dwarfdump .zst files.

This module provides fast lookup of DWARF definition locations using
pre-generated llvm-dwarfdump output. Requires Python 3.14+ for native
compression.zstd support.

Example llvm-dwarfdump output format:
    0x117ec452:   DW_TAG_class_type [8]  (0x117ebf8b)
                    DW_AT_name [DW_FORM_strp]     ("rLayout")
                    DW_AT_byte_size [DW_FORM_data1]       (0x00000210)
                    ...
                  0x117ecd22: DW_TAG_enumeration_type [17] * (0x117ec452)
                                DW_AT_name [DW_FORM_strp]   ("SET_INFO_ALLOC")

The "* (0xOFFSET)" marker indicates parent DIE relationship.
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from ..infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DefinitionLocation:
    """DWARF definition location with completeness metrics.
    
    Attributes:
        cu_offset: Compilation unit offset (hex string)
        die_offset: DIE offset within the dump (hex string)
        nested_enum_count: Number of nested enums found
        nested_struct_count: Number of nested structs found
        nested_union_count: Number of nested unions found
        byte_size: Class size in bytes (0 if unknown)
        completeness_score: Calculated score for ranking definitions
    """
    cu_offset: str
    die_offset: str
    nested_enum_count: int
    nested_struct_count: int
    nested_union_count: int
    byte_size: int
    completeness_score: int


class ZstdDumpParser:
    """Parser for compressed llvm-dwarfdump files.
    
    Uses Python 3.14+ native compression.zstd module for streaming
    decompression and regex-based extraction of DWARF structures.
    """

    def __init__(self, dump_path: Path):
        """Initialize parser with path to .zst dump file.
        
        Args:
            dump_path: Path to compressed llvm-dwarfdump .zst file
            
        Raises:
            ImportError: If Python 3.14+ compression.zstd not available
            FileNotFoundError: If dump file doesn't exist
        """
        self.dump_path = dump_path
        self._check_python_version()
        
        if not dump_path.exists():
            raise FileNotFoundError(f"DWARF dump not found: {dump_path}")
    
    def _check_python_version(self) -> None:
        """Verify Python 3.14+ and compression.zstd availability."""
        if sys.version_info < (3, 14):
            raise ImportError(
                f"Python 3.14+ required for compression.zstd (current: {sys.version_info})"
            )
        
        try:
            import compression.zstd  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "compression.zstd module not available. Ensure Python 3.14+ is installed."
            ) from e
    
    def find_class_definitions(self, class_name: str) -> list[DefinitionLocation]:
        """Find all DWARF definitions for a class across all CUs.
        
        Searches compressed dump for DW_TAG_class_type with matching name,
        extracts CU/DIE offsets, counts nested types, and calculates scores.
        
        Args:
            class_name: Exact class name to search for
            
        Returns:
            List of DefinitionLocation sorted by completeness_score (descending)
            
        Example:
            >>> parser = ZstdDumpParser(Path("dump.zst"))
            >>> locations = parser.find_class_definitions("rLayout")
            >>> best = locations[0]
            >>> print(f"Best at {best.die_offset}: {best.nested_enum_count} enums")
        """
        import compression.zstd as zstd
        
        logger.info(f"Searching compressed dump for class: {class_name}")
        
        # Regex patterns
        cu_pattern = re.compile(r"^(0x[0-9a-f]+):\s+Compile Unit:", re.IGNORECASE)
        class_pattern = re.compile(
            r"^(0x[0-9a-f]+):\s+DW_TAG_class_type.*\*?\s*\(0x([0-9a-f]+)\)",
            re.IGNORECASE
        )
        name_pattern = re.compile(
            rf'DW_AT_name.*["\']({re.escape(class_name)})["\']',
            re.IGNORECASE
        )
        size_pattern = re.compile(r"DW_AT_byte_size.*\(0x([0-9a-f]+)\)", re.IGNORECASE)
        enum_pattern = re.compile(r"DW_TAG_enumeration_type.*\*\s*\(0x([0-9a-f]+)\)")
        struct_pattern = re.compile(r"DW_TAG_structure_type.*\*\s*\(0x([0-9a-f]+)\)")
        union_pattern = re.compile(r"DW_TAG_union_type.*\*\s*\(0x([0-9a-f]+)\)")
        
        # Track ALL matching classes by their DIE offset for parent matching
        class_definitions: dict[str, dict] = {}  # DIE offset (without 0x) -> class data
        current_cu_offset: str | None = None
        current_class_die: str | None = None

        # Parse dump file once
        with zstd.open(self.dump_path, 'rt', encoding='utf-8', errors='replace') as f:
            for _, line in enumerate(f, 1):
                line = line.rstrip()
                
                # Track CU headers
                cu_match = cu_pattern.match(line)
                if cu_match:
                    current_cu_offset = cu_match.group(1)
                    continue
                
                # Check for class_type tag
                class_match = class_pattern.match(line)
                if class_match:
                    die_offset = class_match.group(1)  # With 0x prefix
                    die_offset_raw = die_offset[2:] if die_offset.startswith('0x') else die_offset
                    parent_marker = class_match.group(2)  # Parent DIE from * (0xOFFSET)
                    
                    # Use tracked CU offset if available, otherwise extract from parent marker
                    cu_offset = current_cu_offset
                    if not cu_offset and parent_marker:
                        cu_offset = parent_marker  # Already captured with 0x prefix
                    
                    # Create entry for this class
                    class_definitions[die_offset_raw] = {
                        "die_offset": die_offset,
                        "die_offset_raw": die_offset_raw,
                        "cu_offset": cu_offset,
                        "byte_size": 0,
                        "nested_enums": 0,
                        "nested_structs": 0,
                        "nested_unions": 0,
                        "matches_name": False,
                    }
                    current_class_die = die_offset_raw
                    continue
                
                # Check for name match (track which class this belongs to)
                if current_class_die and current_class_die in class_definitions:
                    name_match = name_pattern.search(line)
                    if name_match:
                        class_definitions[current_class_die]["matches_name"] = True

                    # Extract byte size
                    size_match = size_pattern.search(line)
                    if size_match:
                        class_definitions[current_class_die]["byte_size"] = int(size_match.group(1), 16)
                
                # Count nested enums/structs/unions by checking parent against ALL classes
                enum_match = enum_pattern.search(line)
                if enum_match:
                    parent_raw = enum_match.group(1)
                    parent_raw = parent_raw[2:] if parent_raw.startswith('0x') else parent_raw
                    if parent_raw in class_definitions:
                        class_definitions[parent_raw]["nested_enums"] += 1

                struct_match = struct_pattern.search(line)
                if struct_match:
                    parent_raw = struct_match.group(1)
                    parent_raw = parent_raw[2:] if parent_raw.startswith('0x') else parent_raw
                    if parent_raw in class_definitions:
                        class_definitions[parent_raw]["nested_structs"] += 1

                union_match = union_pattern.search(line)
                if union_match:
                    parent_raw = union_match.group(1)
                    parent_raw = parent_raw[2:] if parent_raw.startswith('0x') else parent_raw
                    if parent_raw in class_definitions:
                        class_definitions[parent_raw]["nested_unions"] += 1
        
        # Convert to definitions list (only classes that match name)
        definitions: list[DefinitionLocation] = []
        for class_data in class_definitions.values():
            if class_data.get("matches_name"):
                definitions.append(self._create_location(class_data))
        
        # Sort by completeness score (descending)
        definitions.sort(key=lambda d: d.completeness_score, reverse=True)
        
        logger.info(
            f"Found {len(definitions)} definition(s) for {class_name} "
            f"(best score: {definitions[0].completeness_score if definitions else 0})"
        )
        
        return definitions
    
    def _create_location(self, class_data: dict) -> DefinitionLocation:
        """Create DefinitionLocation from parsed class data.
        
        Scoring algorithm matches class_parser.py:
        - byte_size: +1 per byte
        - nested_enums: +1000 each
        - nested_structs: +500 each
        - nested_unions: +300 each
        """
        byte_size = class_data["byte_size"]
        nested_enums = class_data["nested_enums"]
        nested_structs = class_data["nested_structs"]
        nested_unions = class_data["nested_unions"]
        cu_offset = class_data["cu_offset"]
        
        # Strip 0x prefix from cu_offset if present
        if cu_offset and cu_offset.startswith("0x"):
            cu_offset = cu_offset[2:]
        
        score = (
            byte_size +
            (nested_enums * 1000) +
            (nested_structs * 500) +
            (nested_unions * 300)
        )
        
        return DefinitionLocation(
            cu_offset=cu_offset,
            die_offset=class_data["die_offset"],
            nested_enum_count=nested_enums,
            nested_struct_count=nested_structs,
            nested_union_count=nested_unions,
            byte_size=byte_size,
            completeness_score=score,
        )
