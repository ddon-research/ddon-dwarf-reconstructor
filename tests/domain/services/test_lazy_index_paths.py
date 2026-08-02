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
from ddon_dwarf_reconstructor.domain.services.search_result import SearchResult, SearchStatus
from ddon_dwarf_reconstructor.infrastructure.artifacts import SourceIdentityCatalog


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

    result = service.targeted_symbol_search("Target")
    assert result.status is SearchStatus.COMPLETE
    assert result.die_offset == 0x20
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

    result = service.targeted_symbol_search("Target")
    assert result.status is SearchStatus.COMPLETE
    assert result.die_offset == 0x20
    service._cache_candidate.assert_called_once()


@pytest.mark.unit
def test_targeted_search_returns_partial_or_none_results(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.persistent_cache = Mock()
    service.persistent_cache.get_symbol_cu_offset.return_value = None
    service._search_hinted_cu = Mock(return_value=None)
    service._ordered_cus = Mock(return_value=[])
    service._finish_targeted_search = Mock(
        return_value=SearchResult(SearchStatus.PARTIAL, _candidate(-1, complete=False), 0.1, 0)
    )
    result = service.targeted_symbol_search("Target")
    assert result.status is SearchStatus.PARTIAL
    assert result.die_offset == 0x20

    service._finish_targeted_search.side_effect = RuntimeError("search failed")
    assert service.targeted_symbol_search("Target").status is SearchStatus.UNAVAILABLE


@pytest.mark.unit
def test_search_state_keeps_first_fallback_and_best_score() -> None:
    state = _SearchState()
    state.record(_candidate(-1, complete=False))
    state.record(_candidate(10))
    state.record(_candidate(5))

    assert state.fallback is not None and state.fallback.score == -1
    assert state.best is not None and state.best.score == 10


@pytest.mark.unit
def test_targeted_timeout_downgrades_best_candidate(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.persistent_cache.get_symbol_cu_offset = Mock(return_value=0x10)
    service._search_hinted_cu = Mock(return_value=_candidate(100))
    service._ordered_cus = Mock(return_value=[Mock()])

    def mark_timeout(
        symbol_name: str, started_at: float, timeout: float, state: _SearchState
    ) -> bool:
        del symbol_name, started_at, timeout
        state.timed_out = True
        return True

    service._search_timed_out = mark_timeout
    service._cache_candidate = Mock()

    result = service.targeted_symbol_search("Target")

    assert result.status is SearchStatus.PARTIAL
    assert result.candidate is not None and result.candidate.complete is False
    service._cache_candidate.assert_called_once()
    assert service._cache_candidate.call_args.args[0].complete is False


@pytest.mark.unit
def test_targeted_fallback_keeps_candidate_cu_and_die_provenance(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.persistent_cache.get_symbol_cu_offset = Mock(return_value=0x10)
    fallback = DefinitionCandidate("Target", 0x300, 0x400, -1, False)
    best = DefinitionCandidate("Target", 0x100, 0x200, 0, False)
    service._search_hinted_cu = Mock(return_value=fallback)
    service._ordered_cus = Mock(return_value=[Mock()])
    service._search_timed_out = Mock(return_value=False)
    service._search_cu_candidate = Mock(return_value=best)
    service._cache_candidate = Mock()

    result = service.targeted_symbol_search("Target")

    assert result.status is SearchStatus.PARTIAL
    assert result.die_offset == 0x400
    cached = service._cache_candidate.call_args.args[0]
    assert (cached.cu_offset, cached.die_offset) == (0x300, 0x400)


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
    cu.header = {"unit_length": 0x20}
    cu.iter_DIEs.return_value = [target]
    service.dwarf_info.iter_CUs.return_value = [cu]

    assert service._scan_die_at_offset(0x15) is target
    assert service._scan_die_at_offset(0x99) is None
    service.dwarf_info.iter_CUs.side_effect = TypeError("bad index")
    assert service._get_cu_by_offset(0x10) is None


@pytest.mark.unit
def test_source_identity_provider_binds_cache_to_strong_identity(tmp_path: Path) -> None:
    source = tmp_path / "source.elf"
    source.write_bytes(b"a" * 70_000)
    identity = SourceIdentityCatalog(tmp_path / "identities.json")
    service = LazyDwarfIndexService(
        Mock(),
        str(tmp_path / "symbols.json"),
        source_file_path=source,
        source_identity=identity,
    )

    fingerprint = service.persistent_cache.source_fingerprint
    assert fingerprint is not None
    assert fingerprint["size"] == 70_000
    assert len(str(fingerprint["sha256"])) == 64
