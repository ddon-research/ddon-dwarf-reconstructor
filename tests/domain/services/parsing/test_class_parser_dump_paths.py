"""Indexed compressed-DWARF discovery and fallback behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.services.parsing import ClassParser


def _parser() -> ClassParser:
    parser = object.__new__(ClassParser)
    parser.dwarf_dump_path = Path("dump.zst")
    parser.dwarf_index_path = Path("dump.sqlite3")
    parser.dwarf_info = Mock()
    parser.lazy_index = Mock()
    parser._dump_parser = Mock()
    parser._dump_lookup_unavailable = False
    parser._dump_lookup_authoritative_miss = False
    return parser


def _location(cu_offset: str = "0x10", die_offset: str = "0x20") -> Mock:
    return Mock(cu_offset=cu_offset, die_offset=die_offset, completeness_score=123)


@pytest.mark.unit
def test_dump_discovery_loads_selected_cu_and_die() -> None:
    parser = _parser()
    cu = Mock(cu_offset=0x10)
    die = Mock(offset=0x20)
    parser.dwarf_info.iter_CUs.return_value = [cu]
    cu.iter_DIEs.return_value = [die]
    parser._dump_parser.find_class_definitions.return_value = [_location()]

    result = parser._find_class_with_dump("Target")

    assert result == (cu, die)
    parser.lazy_index.persistent_cache.add_symbol_cu_mapping.assert_called_once_with(
        "Target", 0x10, 0x20, score=123, complete=True
    )


@pytest.mark.unit
def test_dump_discovery_handles_empty_results_and_unavailable_parser() -> None:
    parser = _parser()
    parser._dump_parser.find_class_definitions.return_value = []

    assert parser._find_class_with_dump("Missing") is None

    parser._dump_parser = None
    assert parser._find_class_with_dump("Missing") is None
    parser.dwarf_dump_path = None
    assert parser._find_class_with_dump_status("Missing") == (False, None)


@pytest.mark.unit
def test_dump_discovery_handles_missing_cu_or_die_without_caching() -> None:
    parser = _parser()
    parser._dump_parser.find_class_definitions.return_value = [_location()]
    parser.dwarf_info.iter_CUs.return_value = []

    assert parser._find_class_with_dump("Target") is None
    parser.lazy_index.persistent_cache.add_symbol_cu_mapping.assert_not_called()

    cu = Mock(cu_offset=0x10)
    cu.iter_DIEs.return_value = []
    parser.dwarf_info.iter_CUs.return_value = [cu]
    assert parser._find_class_with_dump("Target") is None


@pytest.mark.unit
def test_dump_status_distinguishes_unavailable_from_authoritative_miss() -> None:
    parser = _parser()
    parser._dump_parser.find_class_definitions.return_value = []

    assert parser._find_class_with_dump_status("Missing") == (True, None)

    parser._dump_parser.find_class_definitions.side_effect = OSError("sidecar unavailable")
    assert parser._find_class_with_dump_status("Missing") == (False, None)


@pytest.mark.unit
def test_dump_parser_errors_fall_back_to_full_scan() -> None:
    parser = _parser()
    parser._dump_parser.find_class_definitions.side_effect = ValueError("malformed index")

    assert parser._find_class_with_dump("Target") is None
