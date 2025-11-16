"""Unit tests for ZstdDumpParser module.

Tests parsing of compressed llvm-dwarfdump files for class definition locations.
"""

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from ddon_dwarf_reconstructor.infrastructure.zstd_dump_parser import (
    DefinitionLocation,
    ZstdDumpParser,
)


# Sample llvm-dwarfdump output for testing
SAMPLE_DUMP_SINGLE = """
0x117ec452:   DW_TAG_class_type [8]  (0x117ebf8b)
                DW_AT_name [DW_FORM_strp]     ("rLayout")
                DW_AT_byte_size [DW_FORM_data1]       (0x00000210)
                DW_AT_decl_file [DW_FORM_data1]       (0x01)
              0x117ecd22: DW_TAG_enumeration_type [17] * (0x117ec452)
                            DW_AT_name [DW_FORM_strp]   ("SET_INFO_ALLOC")
              0x117ecd30: DW_TAG_enumeration_type [17] * (0x117ec452)
                            DW_AT_name [DW_FORM_strp]   ("TYPE")
"""

SAMPLE_DUMP_MULTIPLE = """
0x76133:   DW_TAG_class_type [8]  (0xc9d)
             DW_AT_name [DW_FORM_strp]     ("rLayout")
             DW_AT_byte_size [DW_FORM_data1]       (0x00000210)
             DW_AT_decl_file [DW_FORM_data1]       (0x01)
           0x7614a: DW_TAG_enumeration_type [17] * (0x76133)
                      DW_AT_name [DW_FORM_strp]   ("TYPE")

0x117ec452:   DW_TAG_class_type [8]  (0x117ebf8b)
                DW_AT_name [DW_FORM_strp]     ("rLayout")
                DW_AT_byte_size [DW_FORM_data1]       (0x00000210)
                DW_AT_decl_file [DW_FORM_data1]       (0x01)
              0x117ecd22: DW_TAG_enumeration_type [17] * (0x117ec452)
                            DW_AT_name [DW_FORM_strp]   ("SET_INFO_ALLOC")
              0x117ecd30: DW_TAG_enumeration_type [17] * (0x117ec452)
                            DW_AT_name [DW_FORM_strp]   ("TYPE")
"""

SAMPLE_DUMP_NESTED_TYPES = """
0x1000:   DW_TAG_class_type [8]  (0x500)
            DW_AT_name [DW_FORM_strp]     ("TestClass")
            DW_AT_byte_size [DW_FORM_data1]       (0x00000100)
          0x1010: DW_TAG_enumeration_type [17] * (0x1000)
                    DW_AT_name [DW_FORM_strp]   ("Enum1")
          0x1020: DW_TAG_enumeration_type [17] * (0x1000)
                    DW_AT_name [DW_FORM_strp]   ("Enum2")
          0x1030: DW_TAG_structure_type [18] * (0x1000)
                    DW_AT_name [DW_FORM_strp]   ("NestedStruct")
          0x1040: DW_TAG_union_type [19] * (0x1000)
                    DW_AT_name [DW_FORM_strp]   ("NestedUnion")
"""


class TestZstdDumpParser:
    """Test ZstdDumpParser functionality."""

    def test_init_python_version_check(self, mocker):
        """Test Python version validation."""
        # Mock sys.version_info to simulate Python 3.13
        mocker.patch("sys.version_info", (3, 13, 0))
        
        with pytest.raises(ImportError, match="Python 3.14\\+ required"):
            ZstdDumpParser(Path("dummy.zst"))

    def test_init_file_not_found(self, mocker):
        """Test error when dump file doesn't exist."""
        # Mock Python version check
        mocker.patch("sys.version_info", (3, 14, 0))
        mocker.patch("ddon_dwarf_reconstructor.infrastructure.zstd_dump_parser.sys.version_info", (3, 14, 0))
        
        with pytest.raises(FileNotFoundError, match="DWARF dump not found"):
            ZstdDumpParser(Path("nonexistent.zst"))

    @pytest.mark.unit
    @patch("compression.zstd.open")
    def test_find_single_definition(self, mock_zstd_open, tmp_path, mocker):
        """Test finding a single class definition."""
        # Setup
        dump_file = tmp_path / "test.zst"
        dump_file.touch()
        
        # Mock Python version
        mocker.patch("sys.version_info", (3, 14, 0))
        mocker.patch("ddon_dwarf_reconstructor.infrastructure.zstd_dump_parser.sys.version_info", (3, 14, 0))
        
        # Mock zstd.open to return our sample data
        mock_zstd_open.return_value.__enter__.return_value = StringIO(SAMPLE_DUMP_SINGLE)
        
        # Execute
        parser = ZstdDumpParser(dump_file)
        locations = parser.find_class_definitions("rLayout")
        
        # Assert
        assert len(locations) == 1
        loc = locations[0]
        assert loc.cu_offset == "117ebf8b"  # Regex captures without 0x prefix
        assert loc.die_offset == "0x117ec452"  # Full offset with 0x
        assert loc.byte_size == 0x210  # 528 bytes
        assert loc.nested_enum_count == 2  # SET_INFO_ALLOC, TYPE
        assert loc.completeness_score == 0x210 + (2 * 1000)  # size + enums

    @pytest.mark.unit
    @patch("compression.zstd.open")
    def test_find_multiple_definitions_best_first(self, mock_zstd_open, tmp_path, mocker):
        """Test finding multiple definitions, best scored first."""
        # Setup
        dump_file = tmp_path / "test.zst"
        dump_file.touch()
        
        # Mock Python version
        mocker.patch("sys.version_info", (3, 14, 0))
        mocker.patch("ddon_dwarf_reconstructor.infrastructure.zstd_dump_parser.sys.version_info", (3, 14, 0))
        
        # Mock zstd.open
        mock_zstd_open.return_value.__enter__.return_value = StringIO(SAMPLE_DUMP_MULTIPLE)
        
        # Execute
        parser = ZstdDumpParser(dump_file)
        locations = parser.find_class_definitions("rLayout")
        
        # Assert
        assert len(locations) == 2
        
        # Best definition should be first (2 enums)
        best = locations[0]
        assert best.cu_offset == "117ebf8b"  # Regex captures without 0x
        assert best.die_offset == "0x117ec452"
        assert best.nested_enum_count == 2
        assert best.completeness_score == 0x210 + (2 * 1000)
        
        # Incomplete definition should be second (1 enum)
        incomplete = locations[1]
        assert incomplete.cu_offset == "c9d"  # Regex captures without 0x
        assert incomplete.die_offset == "0x76133"
        assert incomplete.nested_enum_count == 1
        assert incomplete.completeness_score == 0x210 + (1 * 1000)

    @pytest.mark.unit
    @patch("compression.zstd.open")
    def test_nested_type_scoring(self, mock_zstd_open, tmp_path, mocker):
        """Test scoring algorithm with various nested types."""
        # Setup
        dump_file = tmp_path / "test.zst"
        dump_file.touch()
        
        # Mock Python version
        mocker.patch("sys.version_info", (3, 14, 0))
        mocker.patch("ddon_dwarf_reconstructor.infrastructure.zstd_dump_parser.sys.version_info", (3, 14, 0))
        
        # Mock zstd.open
        mock_zstd_open.return_value.__enter__.return_value = StringIO(SAMPLE_DUMP_NESTED_TYPES)
        
        # Execute
        parser = ZstdDumpParser(dump_file)
        locations = parser.find_class_definitions("TestClass")
        
        # Assert
        assert len(locations) == 1
        loc = locations[0]
        assert loc.nested_enum_count == 2
        assert loc.nested_struct_count == 1
        assert loc.nested_union_count == 1
        
        # Score: size(256) + enums(2*1000) + struct(1*500) + union(1*300)
        expected_score = 0x100 + (2 * 1000) + (1 * 500) + (1 * 300)
        assert loc.completeness_score == expected_score

    @pytest.mark.unit
    @patch("compression.zstd.open")
    def test_no_matches_found(self, mock_zstd_open, tmp_path, mocker):
        """Test behavior when class not found in dump."""
        # Setup
        dump_file = tmp_path / "test.zst"
        dump_file.touch()
        
        # Mock Python version
        mocker.patch("sys.version_info", (3, 14, 0))
        mocker.patch("ddon_dwarf_reconstructor.infrastructure.zstd_dump_parser.sys.version_info", (3, 14, 0))
        
        # Mock zstd.open with data that doesn't match
        mock_zstd_open.return_value.__enter__.return_value = StringIO(SAMPLE_DUMP_SINGLE)
        
        # Execute
        parser = ZstdDumpParser(dump_file)
        locations = parser.find_class_definitions("NonExistentClass")
        
        # Assert
        assert len(locations) == 0

    @pytest.mark.unit
    def test_definition_location_dataclass(self):
        """Test DefinitionLocation dataclass creation."""
        loc = DefinitionLocation(
            cu_offset="0x1234",
            die_offset="0x5678",
            nested_enum_count=2,
            nested_struct_count=1,
            nested_union_count=0,
            byte_size=256,
            completeness_score=2756,
        )
        
        assert loc.cu_offset == "0x1234"
        assert loc.die_offset == "0x5678"
        assert loc.nested_enum_count == 2
        assert loc.nested_struct_count == 1
        assert loc.nested_union_count == 0
        assert loc.byte_size == 256
        assert loc.completeness_score == 2756
