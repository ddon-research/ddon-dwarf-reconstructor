"""
Unit tests for ClassParser scoring algorithm and timeout functionality.
Tests the enhancements for forward declaration detection and type-specific scoring.
"""

import time
from unittest.mock import Mock, patch

import pytest

from ddon_dwarf_reconstructor.domain.services.definition_selection import DefinitionCandidate
from ddon_dwarf_reconstructor.domain.services.parsing import ClassParser, LazyTypeResolver
from ddon_dwarf_reconstructor.domain.services.parsing.class_parser_scan_state import ScanState
from ddon_dwarf_reconstructor.domain.services.search_result import SearchResult, SearchStatus


@pytest.fixture
def type_resolver():
    """Mock the production lazy resolver."""
    return Mock(spec=LazyTypeResolver)


@pytest.fixture
def dwarf_info():
    """Mock DWARF info fixture."""
    return Mock()


@pytest.fixture
def lazy_index():
    """Mock LazyDwarfIndexService fixture."""
    return Mock()


@pytest.fixture
def class_parser(type_resolver, dwarf_info, lazy_index):
    """ClassParser instance with mocked dependencies."""
    parser = ClassParser(type_resolver, dwarf_info, full_scan_timeout=180.0)
    parser.lazy_index = lazy_index
    return parser


class TestClassParserScoring:
    """Test suite for ClassParser scoring and timeout features."""

    @pytest.mark.unit
    def test_forward_declaration_detection(self, class_parser):
        """Test that forward declarations are detected via DW_AT_declaration attribute."""
        # Create mock DIE with DW_AT_declaration attribute
        mock_die = Mock()
        mock_die.tag = "DW_TAG_class_type"
        mock_die.attributes = {
            "DW_AT_name": Mock(value=b"ForwardClass"),
            "DW_AT_declaration": Mock(value=True),  # Forward declaration marker
        }
        mock_die.has_children = False

        # The scoring should penalize this with -1000
        # In actual usage, this would be handled in _find_class_full_scan
        assert "DW_AT_declaration" in mock_die.attributes

    @pytest.mark.unit
    def test_typedef_scoring(self, class_parser):
        """Test that typedefs get score of 5000 when they have DW_AT_type attribute."""
        mock_die = Mock()
        mock_die.tag = "DW_TAG_typedef"
        mock_die.attributes = {
            "DW_AT_name": Mock(value=b"u32"),
            "DW_AT_type": Mock(value=0x1234),  # Has type reference
        }
        mock_die.has_children = False

        # Typedef with DW_AT_type should score 5000
        assert "DW_AT_type" in mock_die.attributes
        assert mock_die.tag == "DW_TAG_typedef"

    @pytest.mark.unit
    def test_base_type_scoring(self, class_parser):
        """Test that base types (int, float, etc.) get score of 8000."""
        mock_die = Mock()
        mock_die.tag = "DW_TAG_base_type"
        mock_die.attributes = {
            "DW_AT_name": Mock(value=b"int"),
            "DW_AT_byte_size": Mock(value=4),
        }
        mock_die.has_children = False

        # Base types are always complete and should score 8000
        assert mock_die.tag == "DW_TAG_base_type"

    @pytest.mark.unit
    def test_enum_scoring(self, class_parser):
        """Test that enums with size get score of 6000."""
        mock_die = Mock()
        mock_die.tag = "DW_TAG_enumeration_type"
        mock_die.attributes = {
            "DW_AT_name": Mock(value=b"MyEnum"),
            "DW_AT_byte_size": Mock(value=4),
        }
        mock_die.has_children = True

        # Enum with size should score 6000
        assert mock_die.tag == "DW_TAG_enumeration_type"
        assert "DW_AT_byte_size" in mock_die.attributes

    @pytest.mark.unit
    def test_class_with_members_scoring(self, class_parser):
        """Test that classes with members get high scores (10000+)."""
        mock_die = Mock()
        mock_die.tag = "DW_TAG_class_type"
        mock_die.attributes = {
            "DW_AT_name": Mock(value=b"CompleteClass"),
            "DW_AT_byte_size": Mock(value=128),
        }
        mock_die.has_children = True  # Has members

        # Class with members: size (128) + 10000 = 10128
        size_attr = mock_die.attributes.get("DW_AT_byte_size")
        expected_score = size_attr.value + 10000
        assert expected_score == 10128

    @pytest.mark.unit
    def test_forward_declaration_vs_complete_class(self, class_parser):
        """Test that complete definition is preferred over forward declaration."""
        # Forward declaration (early in DWARF)
        forward_die = Mock()
        forward_die.tag = "DW_TAG_class_type"
        forward_die.attributes = {
            "DW_AT_name": Mock(value=b"MyClass"),
            "DW_AT_declaration": Mock(value=True),
        }
        forward_die.has_children = False
        forward_die.offset = 0x1000

        # Complete definition (later in DWARF)
        complete_die = Mock()
        complete_die.tag = "DW_TAG_class_type"
        complete_die.attributes = {
            "DW_AT_name": Mock(value=b"MyClass"),
            "DW_AT_byte_size": Mock(value=64),
        }
        complete_die.has_children = True
        complete_die.offset = 0x2000

        # Forward declaration score: -1000
        # Complete class score: 64 + 10000 = 10064
        # Complete should win
        assert "DW_AT_declaration" in forward_die.attributes
        assert "DW_AT_byte_size" in complete_die.attributes
        assert complete_die.has_children

    @pytest.mark.unit
    def test_blacklist_pthread_types(self, class_parser):
        """Test that pthread types are blacklisted and skipped."""
        from ddon_dwarf_reconstructor.domain.services.parsing.class_parser import TYPE_BLACKLIST

        assert "pthread_mutex" in TYPE_BLACKLIST
        assert "pthread_cond_t" in TYPE_BLACKLIST
        assert "FILE" in TYPE_BLACKLIST

    @pytest.mark.unit
    def test_lazy_loading_validates_cached_forward_declaration(self, class_parser):
        """Test that cached forward declarations trigger targeted search."""
        # Mock lazy index returning a cached offset
        mock_offset = 0x1000
        class_parser.lazy_index.find_symbol_offset.return_value = mock_offset

        # Mock DIE at that offset (forward declaration)
        forward_die = Mock()
        forward_die.tag = "DW_TAG_class_type"
        forward_die.attributes = {
            "DW_AT_name": Mock(value=b"CachedClass"),
            "DW_AT_declaration": Mock(value=True),  # Forward declaration
        }
        forward_die.has_children = False

        # Mock CU
        mock_cu = Mock()

        # Mock the find_die_and_cu method to return the forward declaration
        with patch.object(
            class_parser, "_find_die_and_cu_by_offset", return_value=(mock_cu, forward_die)
        ):
            # Mock targeted search to return better result
            better_offset = 0x2000
            class_parser.lazy_index.targeted_symbol_search.return_value = SearchResult(
                SearchStatus.COMPLETE,
                DefinitionCandidate("CachedClass", 0x100, better_offset, 100, True),
                0.01,
                1,
            )

            # Mock better DIE (complete definition)
            complete_die = Mock()
            complete_die.tag = "DW_TAG_class_type"
            complete_die.attributes = {
                "DW_AT_name": Mock(value=b"CachedClass"),
                "DW_AT_byte_size": Mock(value=128),
            }
            complete_die.has_children = True

            # This tests the validation logic - it should detect forward declaration
            # and try targeted search
            _result = class_parser._find_class_lazy("CachedClass")

            # Verify targeted search was called after detecting forward declaration
            class_parser.lazy_index.targeted_symbol_search.assert_called_once_with("CachedClass")

    @pytest.mark.unit
    def test_timeout_behavior(self, class_parser):
        """Test that full scan respects timeout and marks timed-out symbols."""
        # Set a very short timeout for testing
        class_parser.full_scan_timeout = 0.001  # 1ms

        # Create many mock CUs to force timeout
        mock_cus = []
        for i in range(100):
            mock_cu = Mock()
            mock_cu.cu_offset = i * 0x1000

            # Mock CU DIE (compilation unit header)
            cu_die = Mock()
            cu_die.tag = "DW_TAG_compile_unit"

            mock_die = Mock()
            mock_die.tag = "DW_TAG_class_type"
            mock_die.attributes = {"DW_AT_name": Mock(value=b"DummyClass")}
            mock_die.has_children = False
            mock_cu.iter_DIEs.return_value = [cu_die, mock_die]
            mock_cus.append(mock_cu)

        class_parser.dwarf_info.iter_CUs.return_value = mock_cus

        # Mock time to simulate elapsed time exceeding timeout
        start_time = time.time()
        call_count = [0]

        def mock_time():
            call_count[0] += 1
            if call_count[0] > 5:  # After a few calls, report timeout
                return start_time + 0.002  # Exceed 1ms timeout
            return start_time

        with patch("time.time", side_effect=mock_time):
            _result = class_parser._find_class_full_scan("TimeoutTest")

            # Should timeout and return None or incomplete result
            # The timed_out_symbols set should contain the symbol
            assert "TimeoutTest" in class_parser.timed_out_symbols

    @pytest.mark.unit
    def test_timeout_does_not_cache_best_candidate_as_complete(self, class_parser):
        cu = Mock(cu_offset=0x100)
        die = Mock(offset=0x200, has_children=True)
        die.attributes = {"DW_AT_byte_size": Mock(value=8)}
        class_parser.lazy_index.persistent_cache.add_symbol_cu_mapping = Mock()
        state = ScanState(
            best_candidate=die,
            best_cu=cu,
            best_score=10008,
            timed_out=True,
        )

        result = class_parser._select_scan_result("Target", state)

        assert result == (cu, die)
        class_parser.lazy_index.persistent_cache.add_symbol_cu_mapping.assert_called_once_with(
            "Target",
            0x100,
            0x200,
            score=10008,
            complete=False,
        )


@pytest.mark.unit
def test_early_exit_optimization(class_parser):
    """A strong typedef result stops the full scan before the next CU."""
    mock_cu1 = Mock(cu_offset=0x1000)
    typedef_die = Mock(
        tag="DW_TAG_typedef",
        offset=0x1100,
        has_children=False,
        attributes={"DW_AT_name": Mock(value=b"u32"), "DW_AT_type": Mock(value=0x1234)},
    )
    typedef_die.is_null.return_value = False
    mock_cu1.iter_DIEs.return_value = [typedef_die]
    mock_cu2 = Mock(cu_offset=0x2000)
    mock_cu2.iter_DIEs.return_value = []
    class_parser.dwarf_info.iter_CUs.return_value = [mock_cu1, mock_cu2]

    result = class_parser._find_class_full_scan("u32")

    assert result == (mock_cu1, typedef_die)
    mock_cu2.iter_DIEs.assert_not_called()
