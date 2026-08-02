"""Focused lazy-index search, discovery, lookup, and source-binding tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from ddon_dwarf_reconstructor.domain.services.definition_selection import DefinitionCandidate
from ddon_dwarf_reconstructor.domain.services.lazy_dwarf_index_service import (
    LazyDwarfIndexService,
)
from ddon_dwarf_reconstructor.domain.services.lazy_index_search import _SearchState


def _service(tmp_path: Path) -> LazyDwarfIndexService:
    service = LazyDwarfIndexService(Mock(), str(tmp_path / "symbols.json"))
    service.dwarf_info = Mock()
    return service


def _candidate(score: int, *, complete: bool = True) -> DefinitionCandidate:
    return DefinitionCandidate("Target", 0x10, 0x20, score, complete)


def _die(tag: str = "DW_TAG_class_type", name: bytes = b"Target", offset: int = 0x20) -> Mock:
    die = Mock(tag=tag, offset=offset, has_children=True)
    die.attributes = {"DW_AT_name": Mock(value=name), "DW_AT_byte_size": Mock(value=8)}
    return die


@pytest.mark.unit
def test_targeted_search_accepts_hinted_complete_candidate(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.persistent_cache.get_symbol_cu_offset = Mock(return_value=0x10)
    service._search_hinted_cu = Mock(return_value=_candidate(10_000))
    service._cache_candidate = Mock()

    assert service.targeted_symbol_search("Target") == 0x20
    service._search_hinted_cu.assert_called_once()


@pytest.mark.unit
def test_targeted_search_caches_strong_candidate_from_ordered_cu(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.persistent_cache.get_symbol_cu_offset = Mock(return_value=None)
    service._search_hinted_cu = Mock(return_value=None)
    service._ordered_cus = Mock(return_value=[Mock()])
    service._search_timed_out = Mock(return_value=False)
    service._search_cu_candidate = Mock(return_value=_candidate(5_000))
    service._cache_candidate = Mock()

    assert service.targeted_symbol_search("Target") == 0x20
    service._cache_candidate.assert_called_once()


@pytest.mark.unit
def test_targeted_search_returns_partial_or_none_results() -> None:
    service = object.__new__(LazyDwarfIndexService)
    service.persistent_cache = Mock()
    service.persistent_cache.get_symbol_cu_offset.return_value = None
    service._search_hinted_cu = Mock(return_value=None)
    service._ordered_cus = Mock(return_value=[])
    service._finish_targeted_search = Mock(return_value=0x30)
    assert service.targeted_symbol_search("Target") == 0x30

    service._finish_targeted_search.side_effect = RuntimeError("search failed")
    assert service.targeted_symbol_search("Target") is None


@pytest.mark.unit
def test_search_state_keeps_first_fallback_and_best_score() -> None:
    state = _SearchState()
    state.record(_candidate(-1, complete=False))
    state.record(_candidate(10))
    state.record(_candidate(5))

    assert state.fallback is not None and state.fallback.score == -1
    assert state.best is not None and state.best.score == 10


@pytest.mark.unit
def test_candidate_and_cu_search_cover_nonmatches_and_early_exit(tmp_path: Path) -> None:
    service = _service(tmp_path)
    cu = MagicMock(cu_offset=0x10)
    die = _die()
    cu.iter_DIEs.return_value = [Mock(tag="DW_TAG_subprogram", attributes={}), die]
    tags = {"DW_TAG_class_type"}

    assert service._candidate_for_die(die, cu, "Target", tags, b"Other") is None
    candidate = service._candidate_for_die(die, cu, "Target", tags, b"Target")
    assert candidate is not None and candidate.score > 10_000

    service._cache_candidate = Mock()
    assert service._search_cu_for_symbol_with_score(cu, "Target", tags, b"Target") == (
        0x20,
        candidate.score,
    )
    service._cache_candidate.assert_called()


@pytest.mark.unit
def test_cu_search_returns_fallback_and_handles_iteration_errors(tmp_path: Path) -> None:
    service = _service(tmp_path)
    cu = MagicMock(cu_offset=0x10)
    declaration = _die()
    declaration.attributes["DW_AT_declaration"] = Mock(value=True)
    cu.iter_DIEs.return_value = [declaration]
    tags = {"DW_TAG_class_type"}
    service._cache_candidate = Mock()

    offset, score = service._search_cu_for_symbol_with_score(cu, "Target", tags, b"Target")
    assert offset == declaration.offset
    assert score < 0

    cu.iter_DIEs.side_effect = RuntimeError("broken CU")
    assert service._search_cu_for_symbol_with_score(cu, "Target", tags, b"Target") == (None, -1)


@pytest.mark.unit
def test_discovery_records_names_and_skips_missing_names(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.persistent_cache = Mock()
    service._discovered_symbols = set()
    cu = Mock(cu_offset=0x10)
    cu.iter_DIEs.return_value = [_die(), Mock(tag="DW_TAG_class_type", attributes={})]

    assert service.discover_symbols_in_cu(cu, {"DW_TAG_class_type"}) == 1
    assert service._discovered_symbols == {"Target"}
    service.persistent_cache.add_symbol_cu_mapping.assert_called_once_with("Target", 0x10, 0x20)

    cu.iter_DIEs.side_effect = ValueError("broken")
    assert service.discover_symbols_in_cu(cu, {"DW_TAG_class_type"}) == 0


@pytest.mark.unit
def test_lookup_handles_cache_miss_mismatch_and_bounded_scan(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.die_cache.clear()
    die = _die(offset=0x21)
    service.dwarf_info.get_DIE_from_refaddr.return_value = die
    service._scan_die_at_offset = Mock(return_value=_die(offset=0x20))
    assert service.get_die_by_offset(0x20).offset == 0x20

    service.dwarf_info.get_DIE_from_refaddr.return_value = None
    assert service._find_die_at_offset(0x99) is None
    service.dwarf_info = None
    assert service._find_die_at_offset(0x99) is None


@pytest.mark.unit
def test_lookup_scans_only_matching_cu_and_handles_errors(tmp_path: Path) -> None:
    service = _service(tmp_path)
    target = _die(offset=0x15)
    cu = MagicMock(cu_offset=0x10)
    cu.__getitem__.side_effect = lambda key: 0x20 if key == "unit_length" else None
    cu.iter_DIEs.return_value = [target]
    service.dwarf_info.iter_CUs.return_value = [cu]

    assert service._scan_die_at_offset(0x15) is target
    assert service._scan_die_at_offset(0x99) is None
    service.dwarf_info.iter_CUs.side_effect = TypeError("bad index")
    assert service._get_cu_by_offset(0x10) is None


@pytest.mark.unit
def test_source_fingerprint_and_legacy_validation_cover_boundaries(tmp_path: Path) -> None:
    source = tmp_path / "source.elf"
    source.write_bytes(b"a" * 70_000)
    service = _service(tmp_path)

    fingerprint = service._source_fingerprint(source)
    assert fingerprint is not None and fingerprint["size"] == 70_000
    assert service._source_fingerprint(tmp_path / "missing") is None
    assert service.get_elf_hash(str(source))
    assert service.get_elf_hash(str(tmp_path / "missing")) == ""

    die = _die(name=b"Target")
    service.dwarf_info.get_DIE_from_refaddr.return_value = die
    assert service._validate_unbound_cache({"symbol_to_offset": {"ns::Target": 0x20}})
    assert not service._validate_unbound_cache({})
    assert not service._validate_unbound_cache({"symbol_to_offset": {"Other": 0x20}})
