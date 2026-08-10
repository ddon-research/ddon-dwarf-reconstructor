"""Source-bound historical primary selection for analytical stores."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.store_selection import (
    load_selection_cache,
    prefer_cached_definition,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_cached_primary_definition_is_moved_before_other_candidates() -> None:
    class _Cache:
        def get_symbol_offset(self, name: str) -> int | None:
            assert name == "rLayout"
            return 0x20

    candidates = (SimpleNamespace(offset=0x10), SimpleNamespace(offset=0x20))

    selected = prefer_cached_definition("rLayout", candidates, _Cache())

    assert [item.offset for item in selected] == [0x20, 0x10]
    assert candidates == (SimpleNamespace(offset=0x10), SimpleNamespace(offset=0x20))


def test_cached_offset_not_in_candidates_preserves_store_order() -> None:
    class _Cache:
        def get_symbol_offset(self, name: str) -> int | None:
            del name
            return 0x30

    candidates = (SimpleNamespace(offset=0x10), SimpleNamespace(offset=0x20))

    assert prefer_cached_definition("rLayout", candidates, _Cache()) == candidates


def test_selection_cache_reuses_matching_source_bound_sibling(tmp_path: Path) -> None:
    fingerprint = {"sha256": "source", "size": 42}
    sibling = tmp_path / "original-dwarf-cache.json"
    sibling.write_text(
        json.dumps(
            {
                "version": "5.0",
                "source_fingerprint": fingerprint,
                "symbol_to_offset": {"rLayout": 0x20},
                "offset_to_symbol": {"32": "rLayout"},
                "symbol_to_cu_offset": {"rLayout": 0x10},
                "symbol_definitions": {
                    "rLayout": [{"complete": True, "cu_offset": 0x10, "die_offset": 0x20}]
                },
                "cu_offset_to_symbols": {"16": ["rLayout"]},
                "created": 0,
                "last_updated": 0,
            }
        ),
        encoding="utf-8",
    )
    manifest = SimpleNamespace(source_identity=SimpleNamespace(as_fingerprint=lambda: fingerprint))

    cache = load_selection_cache(manifest, tmp_path / "relocated-dwarf-cache.json")

    assert cache is not None
    assert cache.get_symbol_offset("rLayout") == 0x20


def test_selection_cache_can_use_verified_relocated_source_fingerprint(tmp_path: Path) -> None:
    manifest_fingerprint = {"sha256": "source", "size": 42, "mtime_ns": 1, "ctime_ns": 2}
    requested_fingerprint = {
        "sha256": "source",
        "size": 42,
        "mtime_ns": 3,
        "ctime_ns": 4,
    }
    cache_path = tmp_path / "dwarf-cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "version": "5.0",
                "source_fingerprint": requested_fingerprint,
                "symbol_to_offset": {"rLayout": 0x20},
                "offset_to_symbol": {"32": "rLayout"},
                "symbol_to_cu_offset": {"rLayout": 0x10},
                "symbol_definitions": {
                    "rLayout": [{"complete": True, "cu_offset": 0x10, "die_offset": 0x20}]
                },
                "cu_offset_to_symbols": {"16": ["rLayout"]},
                "created": 0,
                "last_updated": 0,
            }
        ),
        encoding="utf-8",
    )
    manifest = SimpleNamespace(
        source_identity=SimpleNamespace(as_fingerprint=lambda: manifest_fingerprint)
    )

    cache = load_selection_cache(
        manifest,
        cache_path,
        source_fingerprint=requested_fingerprint,
    )

    assert cache is not None
    assert cache.get_symbol_offset("rLayout") == 0x20
