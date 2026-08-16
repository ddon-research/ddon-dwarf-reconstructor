"""Tests for dump-assisted method implementation lookup."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.analytical_dwarf import QueryResult, QueryStatus
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


@pytest.mark.unit
def test_store_offset_uses_direct_die_lookup_without_cu_scan() -> None:
    dwarf_info = Mock()
    query_port = Mock()
    cu = Mock(cu_offset=0x100)
    implementation = Mock(offset=0x200, cu=cu)
    query_port.find_method_implementation.return_value = QueryResult(
        QueryStatus.COMPLETE, (implementation,)
    )
    dwarf_info.get_DIE_from_refaddr.return_value = implementation
    parser = ClassParser(Mock(), dwarf_info, query_port=query_port)

    assert parser._find_method_implementation(0x80, "load") == (cu, implementation)
    query_port.find_method_implementation.assert_called_once_with(0x80)
    dwarf_info.iter_CUs.assert_not_called()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("status", "items"),
    [
        (QueryStatus.NOT_FOUND, ()),
        (QueryStatus.PARTIAL, (Mock(offset=0x200),)),
        (QueryStatus.COMPLETE, ()),
    ],
)
def test_store_lookup_refuses_incomplete_or_empty_results(
    status: QueryStatus, items: tuple[object, ...]
) -> None:
    dwarf_info = Mock()
    query_port = Mock()
    query_port.find_method_implementation.return_value = QueryResult(status, items)
    parser = ClassParser(Mock(), dwarf_info, query_port=query_port)

    assert parser._find_method_implementation(0x80, "load") is None
    dwarf_info.get_DIE_from_refaddr.assert_not_called()


@pytest.mark.unit
def test_store_lookup_rejects_missing_offset_and_direct_resolutions() -> None:
    query_port = Mock()
    query_port.find_method_implementation.return_value = QueryResult(
        QueryStatus.COMPLETE, (Mock(),)
    )
    parser = ClassParser(Mock(), Mock(), query_port=query_port)
    assert parser._find_method_implementation(0x80, "load") is None

    for resolved in (None, Mock(cu=None)):
        dwarf_info = Mock()
        implementation = Mock(offset=0x200)
        query_port = Mock()
        query_port.find_method_implementation.return_value = QueryResult(
            QueryStatus.COMPLETE, (implementation,)
        )
        dwarf_info.get_DIE_from_refaddr.return_value = resolved
        parser = ClassParser(Mock(), dwarf_info, query_port=query_port)
        assert parser._find_method_implementation(0x80, "load") is None


@pytest.mark.unit
def test_live_lookup_finds_perfect_specification_match() -> None:
    dwarf_info = Mock()
    cu = Mock(cu_offset=0x100)
    specification = Mock(value=0x80)
    implementation = Mock(
        offset=0x200,
        cu=cu,
        tag="DW_TAG_subprogram",
        attributes={"DW_AT_specification": specification, "DW_AT_low_pc": 0x1000},
    )
    implementation.get_DIE_from_attribute.return_value = Mock(offset=0x80)
    implementation.iter_children.return_value = []
    cu.iter_DIEs.return_value = [implementation]
    dwarf_info.iter_CUs.return_value = [cu]
    parser = ClassParser(Mock(), dwarf_info)

    assert parser._find_method_implementation(0x80, "load") == (cu, implementation)


@pytest.mark.unit
def test_plural_lookup_scans_abstract_origin_after_an_index_miss() -> None:
    dwarf_info = Mock()
    query_port = Mock()
    query_port.find_method_implementations.return_value = QueryResult(QueryStatus.NOT_FOUND)
    cu = Mock(cu_offset=0x100)
    specification = Mock(value=0x80)
    abstract_origin = Mock(value=0x80)
    first = Mock(
        offset=0x210,
        cu=cu,
        tag="DW_TAG_subprogram",
        attributes={"DW_AT_specification": specification},
    )
    second = Mock(
        offset=0x220,
        cu=cu,
        tag="DW_TAG_subprogram",
        attributes={"DW_AT_abstract_origin": abstract_origin},
    )
    first.get_DIE_from_attribute.return_value = Mock(offset=0x80)
    second.get_DIE_from_attribute.return_value = Mock(offset=0x80)
    cu.iter_DIEs.return_value = [second, first]
    dwarf_info.iter_CUs.return_value = [cu]
    parser = ClassParser(Mock(), dwarf_info, query_port=query_port)

    result = parser.find_method_implementation_candidates(0x80, "load")

    assert result.status is QueryStatus.COMPLETE
    assert [die.offset for _cu, die in result.items] == [0x210, 0x220]
    assert "analytical index miss" in result.diagnostics[0]


@pytest.mark.unit
def test_indexed_lookup_keeps_a_complete_negative_result_without_cu_scan() -> None:
    dwarf_info = Mock()
    query_port = Mock()
    query_port.find_method_implementations.return_value = QueryResult(QueryStatus.NOT_FOUND)
    parser = ClassParser(Mock(), dwarf_info, query_port=query_port)

    result = parser.find_method_implementation_candidates_indexed(0x80, "load")

    assert result.status is QueryStatus.NOT_FOUND
    dwarf_info.iter_CUs.assert_not_called()


@pytest.mark.unit
def test_plural_lookup_preserves_partial_scan_without_candidates() -> None:
    parser = ClassParser(Mock(), Mock(), query_port=Mock())
    parser.query_port.find_method_implementations.return_value = QueryResult(QueryStatus.NOT_FOUND)
    parser._scan_method_implementation_candidates = Mock(
        return_value=QueryResult(
            QueryStatus.PARTIAL,
            diagnostics=("implementation scan timed out",),
            truncated=True,
        )
    )

    result = parser.find_method_implementation_candidates(0x80, "load")

    assert result.status is QueryStatus.PARTIAL
    assert result.truncated is True
    assert "implementation scan timed out" in result.diagnostics
