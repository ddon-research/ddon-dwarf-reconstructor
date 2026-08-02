"""Unit tests for ZstdDumpParser module.

Tests parsing of compressed llvm-dwarfdump files for class definition locations.
"""

import os
from contextlib import closing
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from ddon_dwarf_reconstructor.infrastructure.zstd_dump_parser import (
    DefinitionLocation,
    ZstdDumpParser,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def isolated_artifact_cache(tmp_path, monkeypatch):
    """Keep durable source-catalog writes inside each test sandbox."""
    monkeypatch.setenv("DWARF_CACHE_DIR", str(tmp_path / "artifact-cache"))


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

SAMPLE_DUMP_EARLY_STOP = [
    "0x0001: Compile Unit:\n",
    "0x1000:   DW_TAG_class_type [8]  (0x0001)\n",
    '            DW_AT_name [DW_FORM_strp]     ("rLayout")\n',
    "            DW_AT_byte_size [DW_FORM_data1]       (0x00000210)\n",
    "          0x1010: DW_TAG_enumeration_type [17] * (0x1000)\n",
    "0x0002: Compile Unit:\n",
    "0x2000:   DW_TAG_class_type [8]  (0x0002)\n",
    '            DW_AT_name [DW_FORM_strp]     ("rLayout")\n',
    "            DW_AT_byte_size [DW_FORM_data1]       (0x00000210)\n",
    "          0x2010: DW_TAG_enumeration_type [17] * (0x2000)\n",
    "0x0003: Compile Unit:\n",
    "0x3000:   DW_TAG_class_type [8]  (0x0003)\n",
    '            DW_AT_name [DW_FORM_strp]     ("rLayout")\n',
    "            DW_AT_byte_size [DW_FORM_data1]       (0x00000210)\n",
    "          0x3010: DW_TAG_enumeration_type [17] * (0x3000)\n",
    "0x0004: Compile Unit:\n",
    "0x4000:   DW_TAG_class_type [8]  (0x0004)\n",
    '            DW_AT_name [DW_FORM_strp]     ("rLayout")\n',
    "            DW_AT_byte_size [DW_FORM_data1]       (0x00000210)\n",
    "          0x4010: DW_TAG_enumeration_type [17] * (0x4000)\n",
    "0x0005: Compile Unit:\n",
    "0x5000:   DW_TAG_class_type [8]  (0x0005)\n",
    '            DW_AT_name [DW_FORM_strp]     ("rLayout")\n',
    "            DW_AT_byte_size [DW_FORM_data1]       (0x00000210)\n",
    "          0x5010: DW_TAG_enumeration_type [17] * (0x5000)\n",
    "0x0006: Compile Unit:\n",
    "__STOP__\n",
]

SAMPLE_DUMP_WITH_METHOD = """
0x0001: Compile Unit:
0x1000: DW_TAG_class_type [1] (0x0001)
          DW_AT_name [DW_FORM_strp] ("rLayout")
          DW_AT_byte_size [DW_FORM_data1] (0x00000210)
0x1100: DW_TAG_subprogram [2] (0x0001)
          DW_AT_specification [DW_FORM_ref_addr] (0x00001080)
0x1200: DW_TAG_subprogram [2] (0x0001)
          DW_AT_specification [DW_FORM_ref4] (cu + 0x0090 => {0x00001090} "load")
"""


class GuardedDump:
    """File-like guard that detects reads beyond an expected parser boundary."""

    def __init__(self, lines: list[str]):
        self._lines = iter(lines)

    def __iter__(self):
        return self

    def __next__(self) -> str:
        line = next(self._lines)
        if line == "__STOP__\n":
            raise AssertionError("Parser read past the expected early-stop point")
        return line

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class TestZstdDumpParser:
    """Test ZstdDumpParser functionality."""

    def test_init_file_not_found(self):
        """Test error when dump file doesn't exist."""
        with pytest.raises(FileNotFoundError, match="DWARF dump not found"):
            ZstdDumpParser(Path("nonexistent.zst"))

    @pytest.mark.unit
    @patch("compression.zstd.open")
    def test_find_single_definition(self, mock_zstd_open, tmp_path, mocker):
        """Test finding a single class definition."""
        # Setup
        dump_file = tmp_path / "test.zst"
        dump_file.touch()

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

    @pytest.mark.unit
    @patch("compression.zstd.open")
    def test_index_build_streams_complete_dump_once(self, mock_zstd_open, tmp_path, mocker):
        """Cold indexing makes one complete pass so every later lookup is indexed."""
        dump_file = tmp_path / "test.zst"
        dump_file.touch()

        lines = [line for line in SAMPLE_DUMP_EARLY_STOP if line != "__STOP__\n"]
        mock_zstd_open.return_value = GuardedDump(lines)

        parser = ZstdDumpParser(dump_file)
        locations = parser.find_class_definitions("rLayout")

        assert len(locations) == 5
        parser.find_class_definitions("rLayout")
        assert mock_zstd_open.call_count == 1

    @pytest.mark.unit
    def test_real_sidecar_supports_warm_class_and_method_lookups(self, tmp_path):
        """One real compressed pass serves both lookup kinds without reopening the dump."""
        import compression.zstd as zstd

        dump_file = tmp_path / "test.zst"
        with zstd.open(dump_file, "wt", encoding="utf-8") as output:
            output.write(SAMPLE_DUMP_WITH_METHOD)

        parser = ZstdDumpParser(dump_file)
        definitions = parser.find_class_definitions("rLayout")
        implementation = parser.find_method_implementation(0x1080)
        llvm_implementation = parser.find_method_implementation(0x1090)

        assert definitions[0].die_offset == "0x1000"
        assert definitions[0].cu_offset == "1"
        assert implementation == 0x1100
        assert llvm_implementation == 0x1200
        assert parser.index_path.exists()
        assert not hasattr(parser, "_dump_content")

        with patch("compression.zstd.open", side_effect=AssertionError("warm lookup decompressed")):
            assert parser.find_class_definitions("rLayout") == definitions
            assert parser.find_method_implementation(0x1080) == 0x1100

    @pytest.mark.unit
    def test_sidecar_rebuilds_after_source_change(self, tmp_path):
        """A changed compressed source invalidates method and class index data."""
        import compression.zstd as zstd

        dump_file = tmp_path / "test.zst"
        with zstd.open(dump_file, "wt", encoding="utf-8") as output:
            output.write(SAMPLE_DUMP_WITH_METHOD)
        parser = ZstdDumpParser(dump_file)
        assert parser.find_method_implementation(0x1080) == 0x1100
        previous_mtime = dump_file.stat().st_mtime_ns

        changed_dump = SAMPLE_DUMP_WITH_METHOD.replace("0x1100:", "0x2200:")
        with zstd.open(dump_file, "wt", encoding="utf-8") as output:
            output.write(changed_dump)
        os.utime(dump_file, ns=(previous_mtime + 1_000_000, previous_mtime + 1_000_000))

        assert parser.find_method_implementation(0x1080) == 0x2200

    @pytest.mark.unit
    def test_sidecar_survives_metadata_only_timestamp_change(self, tmp_path):
        """Immutable content is matched by boundaries rather than source mtime."""
        import compression.zstd as zstd

        dump_file = tmp_path / "test.zst"
        with zstd.open(dump_file, "wt", encoding="utf-8") as output:
            output.write(SAMPLE_DUMP_WITH_METHOD)
        parser = ZstdDumpParser(dump_file)
        assert parser.find_method_implementation(0x1080) == 0x1100
        stat = dump_file.stat()
        os.utime(dump_file, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

        with patch("compression.zstd.open", side_effect=AssertionError("index rebuilt")):
            assert parser.find_method_implementation(0x1080) == 0x1100

    @pytest.mark.unit
    def test_v11_sidecar_is_atomically_enriched_without_dump_scan(self, tmp_path):
        """Existing expensive indexes migrate to the durable identity contract."""
        import compression.zstd as zstd
        import sqlite3

        dump_file = tmp_path / "test.zst"
        with zstd.open(dump_file, "wt", encoding="utf-8") as output:
            output.write(SAMPLE_DUMP_WITH_METHOD)
        parser = ZstdDumpParser(dump_file)
        assert parser.find_method_implementation(0x1080) == 0x1100
        with closing(sqlite3.connect(parser.index_path)) as connection:
            connection.execute("UPDATE metadata SET value = '1.1' WHERE key = 'schema_version'")
            connection.execute(
                "DELETE FROM metadata WHERE key IN "
                "('producer', 'producer_version', 'config_sha256', "
                "'source_boundary_sha256')"
            )
            connection.commit()

        with patch("compression.zstd.open", side_effect=AssertionError("dump rescanned")):
            assert parser.find_method_implementation(0x1080) == 0x1100

        with closing(sqlite3.connect(parser.index_path)) as connection:
            metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        assert metadata["schema_version"] == "1.2"
        assert metadata["producer"] == parser.INDEX_PRODUCER
        assert metadata["config_sha256"] == parser.INDEX_CONFIG_SHA256
