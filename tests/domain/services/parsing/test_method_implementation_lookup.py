"""Tests for dump-assisted method implementation lookup."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.services.parsing import ClassParser


@pytest.mark.unit
def test_dump_offset_uses_direct_die_lookup_without_cu_scan() -> None:
    dwarf_info = Mock()
    parser = ClassParser(Mock(), dwarf_info, dwarf_dump_path=Path("fixture.zst"))
    dump_index = Mock()
    dump_index.find_method_implementation.return_value = 0x200
    parser._dump_parser = dump_index
    cu = Mock(cu_offset=0x100)
    implementation = Mock(offset=0x200, cu=cu)
    dwarf_info.get_DIE_from_refaddr.return_value = implementation

    assert parser._find_implementation_in_dump(0x80, "load") == (cu, implementation)
    dwarf_info.get_DIE_from_refaddr.assert_called_once_with(0x200)
    dwarf_info.iter_CUs.assert_not_called()


@pytest.mark.unit
def test_mismatched_direct_lookup_is_rejected() -> None:
    dwarf_info = Mock()
    parser = ClassParser(Mock(), dwarf_info, dwarf_dump_path=Path("fixture.zst"))
    dump_index = Mock()
    dump_index.find_method_implementation.return_value = 0x200
    parser._dump_parser = dump_index
    dwarf_info.get_DIE_from_refaddr.return_value = Mock(offset=0x201)

    assert parser._find_implementation_in_dump(0x80, "load") is None
