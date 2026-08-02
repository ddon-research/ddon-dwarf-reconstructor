#!/usr/bin/env python3

"""Tests for multi-definition cache support."""

import json
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.repositories.cache import PersistentSymbolCache


@pytest.mark.unit
def test_add_multiple_definitions_for_symbol(tmp_path: Path):
    """Test adding multiple definitions of the same symbol across different CUs."""
    cache_file = tmp_path / "multi_def_cache.json"
    cache = PersistentSymbolCache(cache_file)

    # Add rLayout from three different CUs with different scores
    cache.add_symbol_cu_mapping("rLayout", 293519243, 293519450, score=15528, complete=True)
    cache.add_symbol_cu_mapping("rLayout", 110737552, 110738100, score=5200, complete=True)
    cache.add_symbol_cu_mapping("rLayout", 3229, 5000, score=100, complete=False)

    # Check that all definitions are stored
    definitions = cache.get_all_definitions("rLayout")
    assert len(definitions) == 3

    # Verify definitions are sorted by score (descending)
    assert definitions[0]["score"] == 15528
    assert definitions[1]["score"] == 5200
    assert definitions[2]["score"] == 100

    # Verify best definition (highest score complete definition) is used as primary
    assert cache.get_symbol_offset("rLayout") == 293519450
    assert cache.get_symbol_cu_offset("rLayout") == 293519243
    assert cache.get_symbol_completeness("rLayout") is True


@pytest.mark.unit
def test_update_existing_definition_with_higher_score(tmp_path: Path):
    """Test that existing definition is updated when a higher score is found."""
    cache_file = tmp_path / "update_def_cache.json"
    cache = PersistentSymbolCache(cache_file)

    # Add definition with low score
    cache.add_symbol_cu_mapping("MtObject", 3229, 34029, score=100, complete=True)
    assert cache.get_all_definitions("MtObject")[0]["score"] == 100

    # Update with higher score (same CU and DIE)
    cache.add_symbol_cu_mapping("MtObject", 3229, 34029, score=10000, complete=True)

    # Should have only one definition with updated score
    definitions = cache.get_all_definitions("MtObject")
    assert len(definitions) == 1
    assert definitions[0]["score"] == 10000


@pytest.mark.unit
def test_prefer_complete_definition_over_incomplete(tmp_path: Path):
    """Test that complete definitions are preferred over incomplete ones."""
    cache_file = tmp_path / "complete_def_cache.json"
    cache = PersistentSymbolCache(cache_file)

    # Add incomplete definition with high score
    cache.add_symbol_cu_mapping("cSetInfo", 1000, 2000, score=5000, complete=False)

    # Add complete definition with lower score
    cache.add_symbol_cu_mapping("cSetInfo", 3229, 4000, score=100, complete=True)

    # Best definition should be the complete one despite lower score
    best = cache._get_best_definition("cSetInfo")
    assert best["complete"] is True
    assert best["score"] == 100
    assert best["cu_offset"] == 3229
    assert cache.get_symbol_completeness("cSetInfo") is True


@pytest.mark.unit
def test_incomplete_definition_is_visible_without_being_complete(tmp_path: Path):
    cache = PersistentSymbolCache(tmp_path / "partial.json")
    cache.add_symbol_cu_mapping("Pending", 100, 200, score=20, complete=False)

    assert cache.get_symbol_completeness("Pending") is False


@pytest.mark.unit
def test_cache_with_old_schema_requires_rebuild(tmp_path: Path):
    """Old schema records are rejected instead of guessing missing evidence."""
    cache_file = tmp_path / "migration_cache.json"

    # Create v2.0 cache file
    v2_data = {
        "version": "2.0",
        "symbol_to_offset": {
            "MtObject": 34029,
            "u32": 16675,
        },
        "offset_to_symbol": {
            "34029": "MtObject",
            "16675": "u32",
        },
        "symbol_to_cu_offset": {
            "MtObject": 3229,
            "u32": 3229,
        },
        "cu_offset_to_symbols": {
            "3229": ["MtObject", "u32"],
        },
        "created": 1760200259.0,
        "last_updated": 1760200804.0,
    }

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(v2_data, f)

    # Load cache - the caller must rebuild it from the current source.
    cache = PersistentSymbolCache(cache_file)

    assert cache.data["version"] == "5.0"
    assert cache.get_all_definitions("MtObject") == []


@pytest.mark.unit
def test_cache_with_missing_fields_requires_rebuild(tmp_path: Path):
    """An incomplete current record is not reconstructed from partial fields."""
    cache_file = tmp_path / "missing_fields_cache.json"

    # Create cache missing symbol_definitions field
    incomplete_data = {
        "version": "5.0",
        "symbol_to_offset": {"MtObject": 34029},
        "offset_to_symbol": {"34029": "MtObject"},
        "symbol_to_cu_offset": {"MtObject": 3229},
        "cu_offset_to_symbols": {"3229": ["MtObject"]},
    }

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(incomplete_data, f)

    cache = PersistentSymbolCache(cache_file)

    assert cache.get_all_definitions("MtObject") == []
    assert cache.data["version"] == "5.0"


@pytest.mark.unit
def test_validate_and_repair_duplicate_definitions(tmp_path: Path):
    """Test that validation removes duplicate definitions."""
    cache_file = tmp_path / "dup_defs_cache.json"
    cache = PersistentSymbolCache(cache_file)

    # Manually add duplicate definitions (bypass the check)
    cache.data["symbol_definitions"]["test_symbol"] = [
        {"cu_offset": 1000, "die_offset": 2000, "score": 100, "complete": True},
        {"cu_offset": 1000, "die_offset": 2000, "score": 200, "complete": True},  # Duplicate!
        {"cu_offset": 3000, "die_offset": 4000, "score": 50, "complete": True},
    ]

    report = cache.validate_and_repair()

    # Should have removed one duplicate
    assert len(report["repairs"]) > 0
    definitions = cache.get_all_definitions("test_symbol")
    assert len(definitions) == 2  # Only 2 unique definitions remain


@pytest.mark.unit
def test_get_statistics_includes_multi_def_metrics(tmp_path: Path):
    """Test that statistics include multi-definition metrics."""
    cache_file = tmp_path / "stats_cache.json"
    cache = PersistentSymbolCache(cache_file)

    # Add some symbols with multiple definitions
    cache.add_symbol_cu_mapping("rLayout", 293519243, 293519450, score=15528, complete=True)
    cache.add_symbol_cu_mapping("rLayout", 110737552, 110738100, score=5200, complete=True)
    cache.add_symbol_cu_mapping("MtObject", 3229, 34029, score=10000, complete=True)

    stats = cache.get_statistics()

    # Verify multi-definition metrics
    assert stats["symbols"] == 2  # 2 unique symbols
    assert stats["multi_definition_symbols"] == 1  # Only rLayout has multiple defs
    assert stats["total_definitions"] == 3  # 3 total definitions
    assert stats["version"] == "5.0"


@pytest.mark.unit
def test_empty_cache_initializes_with_current_structure(tmp_path: Path):
    """Test that new empty cache uses the current source-aware format."""
    cache_file = tmp_path / "new_cache.json"
    cache = PersistentSymbolCache(cache_file)

    assert cache.data["version"] == "5.0"
    assert "symbol_definitions" in cache.data
    assert isinstance(cache.data["symbol_definitions"], dict)
