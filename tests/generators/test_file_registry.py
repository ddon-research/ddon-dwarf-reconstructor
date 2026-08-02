#!/usr/bin/env python3

"""Unit tests for FileRegistry service."""

from unittest.mock import Mock

import pytest

from src.ddon_dwarf_reconstructor.domain.services.generation.file_registry import (
    FileRegistry,
)


@pytest.mark.unit
class TestFileRegistry:
    """Tests for FileRegistry class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.mock_dwarf_info = Mock()
        self.registry = FileRegistry(self.mock_dwarf_info)

    def test_register_class_with_file_index(self) -> None:
        """Test registering a class with valid file index."""
        # Mock the file list extraction
        self.registry._file_lists[0x1000] = ["main.h", "base.h", "util.h"]

        self.registry.register_class("MyClass", 0x1000, 1)

        assert self.registry.get_class_file("MyClass") == "base.h"

    def test_register_class_with_no_file_info(self) -> None:
        """Test registering a class without file information."""
        self.registry.register_class("UnknownClass", 0x1000, None)

        assert self.registry.get_class_file("UnknownClass") is None
        assert "UnknownClass" in self.registry.get_uncategorized_classes()

    def test_register_class_with_invalid_file_index(self) -> None:
        """Test registering a class with out-of-bounds file index."""
        self.registry._file_lists[0x1000] = ["main.h", "base.h"]

        self.registry.register_class("BadClass", 0x1000, 99)

        assert self.registry.get_class_file("BadClass") is None
        assert "BadClass" in self.registry.get_uncategorized_classes()

    def test_register_multiple_classes_same_file(self) -> None:
        """Test registering multiple classes in the same file."""
        self.registry._file_lists[0x1000] = ["types.h"]

        self.registry.register_class("Class1", 0x1000, 0)
        self.registry.register_class("Class2", 0x1000, 0)
        self.registry.register_class("Class3", 0x1000, 0)

        classes_by_file = self.registry.get_classes_by_file()
        assert "types.h" in classes_by_file
        assert len(classes_by_file["types.h"]) == 3

    def test_register_classes_across_multiple_files(self) -> None:
        """Test registering classes across different files."""
        self.registry._file_lists[0x1000] = ["file1.h", "file2.h"]
        self.registry._file_lists[0x2000] = ["file3.h", "file4.h"]

        self.registry.register_class("ClassA", 0x1000, 0)
        self.registry.register_class("ClassB", 0x1000, 1)
        self.registry.register_class("ClassC", 0x2000, 0)
        self.registry.register_class("ClassD", 0x2000, 1)

        classes_by_file = self.registry.get_classes_by_file()
        assert len(classes_by_file) == 4
        assert classes_by_file["file1.h"] == ["ClassA"]
        assert classes_by_file["file2.h"] == ["ClassB"]
        assert classes_by_file["file3.h"] == ["ClassC"]
        assert classes_by_file["file4.h"] == ["ClassD"]

    def test_get_classes_by_file_includes_uncategorized(self) -> None:
        """Test that uncategorized classes appear in get_classes_by_file."""
        self.registry._file_lists[0x1000] = ["known.h"]

        self.registry.register_class("KnownClass", 0x1000, 0)
        self.registry.register_class("UnknownClass1", 0x1000, None)
        self.registry.register_class("UnknownClass2", 0x2000, None)

        classes_by_file = self.registry.get_classes_by_file()

        assert "known.h" in classes_by_file
        assert "UncategorizedDefinitions" in classes_by_file
        assert len(classes_by_file["UncategorizedDefinitions"]) == 2

    def test_get_uncategorized_classes(self) -> None:
        """Test retrieving list of uncategorized classes."""
        self.registry.register_class("Unknown1", 0x1000, None)
        self.registry.register_class("Unknown2", 0x1000, None)
        self.registry.register_class("Unknown3", 0x1000, None)

        uncategorized = self.registry.get_uncategorized_classes()
        assert len(uncategorized) == 3
        assert "Unknown1" in uncategorized
        assert "Unknown2" in uncategorized
        assert "Unknown3" in uncategorized

    def test_has_uncategorized_with_uncategorized_classes(self) -> None:
        """Test has_uncategorized when classes lack file info."""
        self.registry.register_class("MissingFile", 0x1000, None)

        assert self.registry.has_uncategorized() is True

    def test_has_uncategorized_without_uncategorized_classes(self) -> None:
        """Test has_uncategorized when all classes have files."""
        self.registry._file_lists[0x1000] = ["all_known.h"]
        self.registry.register_class("KnownClass", 0x1000, 0)

        assert self.registry.has_uncategorized() is False

    def test_summarize_output(self) -> None:
        """Test the summarize method generates proper output."""
        self.registry._file_lists[0x1000] = ["types.h", "utils.h"]

        self.registry.register_class("Type1", 0x1000, 0)
        self.registry.register_class("Type2", 0x1000, 0)
        self.registry.register_class("Util1", 0x1000, 1)
        self.registry.register_class("Unknown1", 0x1000, None)

        summary = self.registry.summarize()

        assert "File Registry Summary" in summary
        assert "4 classes" in summary
        assert "types.h" in summary
        assert "utils.h" in summary
        assert "UncategorizedDefinitions" in summary

    def test_get_class_file_nonexistent_class(self) -> None:
        """Test getting file for non-existent class."""
        result = self.registry.get_class_file("NonExistentClass")

        assert result is None

    def test_register_class_caches_file_list(self) -> None:
        """Test that file list is cached after first access."""
        # Mock _extract_file_list to track calls
        self.registry._extract_file_list = Mock(return_value=["file1.h", "file2.h"])

        # Register two classes from same CU
        self.registry.register_class("Class1", 0x1000, 0)
        self.registry.register_class("Class2", 0x1000, 1)

        # _extract_file_list should only be called once
        assert self.registry._extract_file_list.call_count == 1

    def test_extract_file_list_with_valid_cu(self) -> None:
        """Test extracting file list from valid compilation unit."""
        # Mock the DWARF structure
        mock_cu = Mock()
        mock_cu.cu_offset = 0x1000

        mock_file_entry1 = Mock()
        mock_file_entry1.name = b"main.h"

        mock_file_entry2 = Mock()
        mock_file_entry2.name = b"base.h"

        mock_line_program = Mock()
        mock_line_program.header.file_entry = [mock_file_entry1, mock_file_entry2]

        self.mock_dwarf_info.iter_CUs.return_value = [mock_cu]
        self.mock_dwarf_info.line_program_for_CU.return_value = mock_line_program

        files = self.registry._extract_file_list(0x1000)

        assert files == ["main.h", "base.h"]

    def test_extract_file_list_with_invalid_cu(self) -> None:
        """Test extracting file list from invalid compilation unit."""
        self.mock_dwarf_info.iter_CUs.return_value = []

        files = self.registry._extract_file_list(0x9999)

        assert files == []

    def test_extract_file_list_with_no_line_program(self) -> None:
        """Test extracting file list when line program is unavailable."""
        mock_cu = Mock()
        mock_cu.cu_offset = 0x1000

        self.mock_dwarf_info.iter_CUs.return_value = [mock_cu]
        self.mock_dwarf_info.line_program_for_CU.return_value = None

        files = self.registry._extract_file_list(0x1000)

        assert files == []

    def test_mixed_scenario_complex_hierarchy(self) -> None:
        """Test complex scenario with mixed files and uncategorized classes."""
        # Set up file lists for two CUs
        self.registry._file_lists[0x1000] = ["base.h", "types.h", "utils.h"]
        self.registry._file_lists[0x2000] = ["derived.h", "extra.h"]

        # Register a mixed hierarchy
        self.registry.register_class("cResource", 0x1000, 0)  # base.h
        self.registry.register_class("MtObject", 0x1000, 0)  # base.h
        self.registry.register_class("MtVector4", 0x1000, 1)  # types.h
        self.registry.register_class("SetInfo", 0x2000, 0)  # derived.h
        self.registry.register_class("SystemType", 0x1000, None)  # uncategorized
        self.registry.register_class("UnknownDep", 0x2000, None)  # uncategorized

        classes_by_file = self.registry.get_classes_by_file()

        assert "base.h" in classes_by_file
        assert len(classes_by_file["base.h"]) == 2
        assert "types.h" in classes_by_file
        assert len(classes_by_file["types.h"]) == 1
        assert "derived.h" in classes_by_file
        assert len(classes_by_file["derived.h"]) == 1
        assert "UncategorizedDefinitions" in classes_by_file
        assert len(classes_by_file["UncategorizedDefinitions"]) == 2
