"""Integration tests for DwarfGenerator with real ELF files.

These tests run only if the test ELF file is available and are marked as integration tests.
They verify end-to-end functionality but don't write files to disk.
"""

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.generators.dwarf_generator import DwarfGenerator


class TestDwarfGeneratorIntegration:
    """Integration tests for DwarfGenerator with real DWARF data."""

    @pytest.fixture
    def test_elf_path(self) -> Path:
        """Get path to test ELF file if it exists."""
        return Path("resources/DDOORBIS.elf")

    @pytest.mark.integration
    @pytest.mark.skipif(
        not Path("resources/DDOORBIS.elf").exists(), reason="Test ELF file not available"
    )
    def test_real_elf_processing(self, test_elf_path: Path):
        """Test processing real ELF file without writing output."""
        with DwarfGenerator(test_elf_path) as generator:
            # Test that we can find a known class
            result = generator.find_class("MtObject")
            assert result is not None, "Should find MtObject class in test data"

            _, die = result
            assert die.tag == "DW_TAG_class_type"

            # Test header generation produces valid content
            header_content = generator.generate_header("MtObject")

            # Verify header structure without file I/O
            assert len(header_content) > 100, "Header should have substantial content"
            assert "#ifndef MTOBJECT_H" in header_content, "Should have include guard"
            assert "class MtObject" in header_content, "Should define the class"
            assert "Generated from DWARF debug information" in header_content

            # Verify C++ syntax basics
            lines = header_content.split("\n")
            class_lines = [line for line in lines if "class MtObject" in line]
            assert len(class_lines) > 0, "Should have class declaration"

    # NOTE: We don't test "class not found" scenarios in integration tests
    # because they would require scanning through 2000+ compilation units
    # with millions of DIEs, making the test extremely slow.

    @pytest.mark.integration
    @pytest.mark.skipif(
        not Path("resources/DDOORBIS.elf").exists(), reason="Test ELF file not available"
    )
    def test_dwarf_info_access(self, test_elf_path: Path):
        """Test that DWARF information is properly accessible."""
        with DwarfGenerator(test_elf_path) as generator:
            # Verify we have DWARF info
            assert generator.dwarf_info is not None

            # Verify we can iterate compilation units
            cus = list(generator.dwarf_info.iter_CUs())
            assert len(cus) > 0, "Should have compilation units"

            # Verify compilation units have DIEs
            for cu in cus[:3]:  # Test first few CUs
                dies = list(cu.iter_DIEs())
                assert len(dies) > 0, f"CU at offset {cu.cu_offset} should have DIEs"
