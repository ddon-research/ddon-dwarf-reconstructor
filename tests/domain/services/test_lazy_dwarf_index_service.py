"""Tests for indexed DWARF reference lookup behavior."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.services.lazy_dwarf_index_service import (
    LazyDwarfIndexService,
)
from ddon_dwarf_reconstructor.infrastructure.artifacts import SourceIdentityCatalog


@pytest.mark.unit
def test_offset_lookup_uses_pyelftools_reference_index_and_lru_cache(tmp_path: Path) -> None:
    """Repeated offsets never fall back to full CU or DIE iteration."""
    dwarf_info = Mock()
    die = Mock()
    die.tag = "DW_TAG_class_type"
    die.offset = 0x1234
    dwarf_info.get_DIE_from_refaddr.return_value = die
    service = LazyDwarfIndexService(dwarf_info, str(tmp_path / "symbols.json"))

    first = service.get_die_by_offset(0x1234)
    second = service.get_die_by_offset(0x1234)

    assert first is die
    assert second is die
    dwarf_info.get_DIE_from_refaddr.assert_called_once_with(0x1234)
    dwarf_info.iter_CUs.assert_not_called()


@pytest.mark.unit
def test_unreadable_source_disables_cache_binding(tmp_path: Path) -> None:
    """An inaccessible source must not prevent use of an already-open DWARF object."""
    service = LazyDwarfIndexService(
        Mock(),
        str(tmp_path / "symbols.json"),
        source_file_path=tmp_path / "missing.elf",
    )

    assert service.persistent_cache.source_fingerprint is None


@pytest.mark.unit
def test_same_path_source_replacement_discards_symbol_cache(tmp_path: Path) -> None:
    """Replacing an ELF at the same path rejects offsets from the old source."""
    source = tmp_path / "DDOORBIS.elf"
    source.write_bytes(b"source-v1" * 20_000)
    cache_file = tmp_path / "symbols.json"

    identity = SourceIdentityCatalog(tmp_path / "identities.json")
    first = LazyDwarfIndexService(
        Mock(), str(cache_file), source_file_path=source, source_identity=identity
    )
    first.persistent_cache.add_symbol("OldType", 0x1234)
    first.save_cache()

    source.write_bytes(b"source-v2" * 20_000)
    second = LazyDwarfIndexService(
        Mock(), str(cache_file), source_file_path=source, source_identity=identity
    )

    assert second.find_symbol_offset("OldType") is None
    assert second.persistent_cache.source_fingerprint != first.persistent_cache.source_fingerprint
