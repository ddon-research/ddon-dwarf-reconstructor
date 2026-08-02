"""
Comprehensive unit tests for ClassParser module.
Tests the core DWARF class parsing functionality with proper mocks.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ddon_dwarf_reconstructor.domain.services.parsing import ClassParser, LazyTypeResolver
from ddon_dwarf_reconstructor.domain.services.search_result import SearchResult, SearchStatus


class TestClassParser:
    """Test suite for ClassParser functionality."""

    @pytest.fixture
    def type_resolver(self):
        """Mock the production lazy resolver."""
        return Mock(spec=LazyTypeResolver)

    @pytest.fixture
    def dwarf_info(self):
        """Mock DWARF info fixture."""
        return Mock()

    @pytest.fixture
    def class_parser(self, type_resolver, dwarf_info):
        """ClassParser instance with mocked dependencies."""
        return ClassParser(type_resolver, dwarf_info)

    @pytest.mark.unit
    def test_find_class_lazy_cache_validation(self, class_parser):
        """Test that lazy loading validates cached entries are not forward declarations."""
        # Setup lazy index mock
        mock_lazy_index = Mock()
        class_parser.lazy_index = mock_lazy_index
        mock_lazy_index.persistent_cache.get_symbol_completeness.return_value = False

        # Mock cache returns an offset
        mock_lazy_index.find_symbol_offset.return_value = 0x1000

        # Mock DIE at cached offset - forward declaration
        mock_forward_die = Mock()
        mock_forward_die.tag = "DW_TAG_class_type"
        mock_forward_die.attributes = {
            "DW_AT_name": Mock(value=b"TestClass"),
            "DW_AT_declaration": Mock(value=True),  # Forward declaration!
        }
        mock_forward_die.offset = 0x1000
        mock_forward_die.has_children = False

        mock_cu = Mock()
        mock_cu.cu_offset = 0x100
        mock_cu.__getitem__ = Mock(return_value=0x500)  # Mock unit_length

        # Mock finding the DIE - should return the forward declaration
        with patch.object(class_parser, "_find_die_and_cu_by_offset") as mock_find:
            mock_find.return_value = (mock_cu, mock_forward_die)

            # Mock dwarf_info to return empty for full scan fallback
            class_parser.dwarf_info.iter_CUs.return_value = []

            result = class_parser.find_class("TestClass")

            # Should reject cached forward declaration and return None (no full scan match)
            assert result is None

    @pytest.mark.unit
    def test_offset_lookup_uses_direct_reference_api_without_lazy_index(self, class_parser):
        """Direct parser lookup delegates to pyelftools instead of scanning CUs."""
        class_parser.lazy_index = None
        die = Mock()
        die.offset = 0x1234
        die.cu = Mock()
        class_parser.dwarf_info.get_DIE_from_refaddr.return_value = die

        result = class_parser._find_die_and_cu_by_offset(0x1234)

        assert result == (die.cu, die)
        class_parser.dwarf_info.get_DIE_from_refaddr.assert_called_once_with(0x1234)
        class_parser.dwarf_info.iter_CUs.assert_not_called()

    @pytest.mark.unit
    def test_find_class_lazy_uses_dump_before_targeted_search(self, class_parser):
        """Dump-assisted lookup should win over targeted CU scans on cache miss."""
        mock_lazy_index = Mock()
        class_parser.lazy_index = mock_lazy_index
        class_parser.dwarf_dump_path = Path("dump.zst")
        mock_lazy_index.find_symbol_offset.return_value = None

        dump_cu = Mock()
        dump_die = Mock()

        with patch.object(
            class_parser,
            "_find_class_with_dump_status",
            return_value=(True, (dump_cu, dump_die)),
        ) as dump_lookup:
            result = class_parser.find_class("stLayoutID")

        assert result == (dump_cu, dump_die)
        dump_lookup.assert_called_once_with("stLayoutID")
        mock_lazy_index.targeted_symbol_search.assert_not_called()

    @pytest.mark.unit
    def test_find_class_lazy_treats_successful_dump_miss_as_authoritative(self, class_parser):
        """An indexed miss must not trigger a scan of every compile unit."""
        mock_lazy_index = Mock()
        class_parser.lazy_index = mock_lazy_index
        class_parser.dwarf_dump_path = Path("dump.zst")
        mock_lazy_index.find_symbol_offset.return_value = None

        with patch.object(class_parser, "_find_class_with_dump_status", return_value=(True, None)):
            result = class_parser.find_class("CMD")

        assert result is None
        mock_lazy_index.targeted_symbol_search.assert_not_called()

    @pytest.mark.unit
    def test_find_class_lazy_falls_back_when_dump_lookup_fails(self, class_parser):
        """An unavailable or failed dump index retains the targeted fallback."""
        mock_lazy_index = Mock()
        class_parser.lazy_index = mock_lazy_index
        class_parser.dwarf_dump_path = Path("dump.zst")
        mock_lazy_index.find_symbol_offset.return_value = None
        mock_lazy_index.targeted_symbol_search.return_value = SearchResult(
            SearchStatus.NOT_FOUND, None, 0.01, 1
        )

        with patch.object(class_parser, "_find_class_with_dump_status", return_value=(False, None)):
            class_parser._find_class_lazy("CMD")

        mock_lazy_index.targeted_symbol_search.assert_called_once_with("CMD")

    @pytest.mark.unit
    def test_find_class_scoring_declaration_penalty(self, class_parser):
        """Test that forward declarations receive heavy penalty in scoring."""
        # Mock forward declaration with size (shouldn't happen but test scoring)
        mock_forward_die = Mock()
        mock_forward_die.tag = "DW_TAG_class_type"
        mock_forward_die.attributes = {
            "DW_AT_name": Mock(value=b"TestClass"),
            "DW_AT_byte_size": Mock(value=100),
            "DW_AT_declaration": Mock(value=True),  # Declaration penalty: -1000
        }
        mock_forward_die.offset = 0x1000
        mock_forward_die.has_children = False
        mock_forward_die.is_null.return_value = False

        mock_cu1 = Mock()
        mock_cu1.cu_offset = 0x100
        mock_cu1.iter_DIEs.return_value = [mock_forward_die]

        # Mock complete definition with smaller size
        mock_complete_die = Mock()
        mock_complete_die.tag = "DW_TAG_class_type"
        mock_complete_die.attributes = {
            "DW_AT_name": Mock(value=b"TestClass"),
            "DW_AT_byte_size": Mock(value=8),  # Much smaller
        }
        mock_complete_die.offset = 0x2000
        mock_complete_die.has_children = True  # Score: 10008
        mock_complete_die.is_null.return_value = False

        mock_cu2 = Mock()
        mock_cu2.cu_offset = 0x200
        mock_cu2.iter_DIEs.return_value = [mock_complete_die]

        class_parser.dwarf_info.iter_CUs.return_value = [mock_cu1, mock_cu2]

        result = class_parser.find_class("TestClass")

        # Should prefer small complete definition (score: 10008) over
        # large forward declaration (score: -1000+100=-900)
        assert result is not None
        cu, die = result
        assert cu == mock_cu2
        assert die.offset == 0x2000
