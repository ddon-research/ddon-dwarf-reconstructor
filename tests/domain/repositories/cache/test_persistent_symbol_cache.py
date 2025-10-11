#!/usr/bin/env python3

"""Tests for persistent symbol cache."""

import json
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.repositories.cache.persistent_symbol_cache import (
    PersistentSymbolCache,
)


@pytest.mark.unit
def test_add_symbol_cu_mapping_no_duplicates(tmp_path: Path):
    """Test that adding symbols to same CU doesn't create duplicate keys."""
    cache_file = tmp_path / "test_cache.json"
    cache = PersistentSymbolCache(cache_file)

    # Add multiple symbols to the same CU
    cache.add_symbol_cu_mapping("MtObject", 3229, 34029)
    cache.add_symbol_cu_mapping("u32", 3229, 16675)
    cache.add_symbol_cu_mapping("MtPropertyList", 3229, 76092)

    # Save and reload
    cache.save()

    # Check that JSON has no duplicate keys
    with open(cache_file, encoding="utf-8") as f:
        raw_data = f.read()
        # Count occurrences of "3229" as a JSON key (with quotes and colon)
        key_count = raw_data.count('"3229":')
        assert key_count == 1, f"Found {key_count} occurrences of '3229' key, expected 1"

    # Verify symbols are stored correctly
    reloaded_cache = PersistentSymbolCache(cache_file)
    cu_symbols = reloaded_cache.get_cu_symbols(3229)
    assert set(cu_symbols) == {"MtObject", "u32", "MtPropertyList"}


@pytest.mark.unit
def test_add_symbol_cu_mapping_zero_cu_offset(tmp_path: Path):
    """Test that CU offset 0 works correctly and doesn't create duplicates."""
    cache_file = tmp_path / "test_cache.json"
    cache = PersistentSymbolCache(cache_file)

    # Add symbols to CU offset 0
    cache.add_symbol_cu_mapping("size_t", 0, 2360)
    cache.add_symbol_cu_mapping("bool", 0, 1347)

    # Save and reload
    cache.save()

    # Check JSON for duplicate keys
    with open(cache_file, encoding="utf-8") as f:
        raw_data = f.read()
        key_count = raw_data.count('"0":')
        assert key_count == 1, f"Found {key_count} occurrences of '0' key, expected 1"

    # Verify symbols
    reloaded_cache = PersistentSymbolCache(cache_file)
    cu_symbols = reloaded_cache.get_cu_symbols(0)
    assert set(cu_symbols) == {"size_t", "bool"}


@pytest.mark.unit
def test_add_symbol_cu_mapping_multiple_cus(tmp_path: Path):
    """Test adding symbols across multiple CUs."""
    cache_file = tmp_path / "test_cache.json"
    cache = PersistentSymbolCache(cache_file)

    # Add symbols to different CUs
    cache.add_symbol_cu_mapping("MtObject", 3229, 34029)
    cache.add_symbol_cu_mapping("size_t", 0, 2360)
    cache.add_symbol_cu_mapping("rAIFSM", 3229, 498357)
    cache.add_symbol_cu_mapping("bool", 0, 1347)

    # Save and reload
    cache.save()

    # Verify no duplicate keys
    with open(cache_file, encoding="utf-8") as f:
        data = json.load(f)
        # Check that keys are unique
        cu_keys = list(data["cu_offset_to_symbols"].keys())
        assert len(cu_keys) == len(set(cu_keys)), f"Duplicate keys found: {cu_keys}"

    # Verify all symbols are accessible
    reloaded_cache = PersistentSymbolCache(cache_file)
    assert set(reloaded_cache.get_cu_symbols(3229)) == {"MtObject", "rAIFSM"}
    assert set(reloaded_cache.get_cu_symbols(0)) == {"size_t", "bool"}


@pytest.mark.unit
def test_get_or_create_behavior(tmp_path: Path):
    """Test that adding symbol uses get-or-create behavior."""
    cache_file = tmp_path / "test_cache.json"
    cache = PersistentSymbolCache(cache_file)

    # Add first symbol
    cache.add_symbol_cu_mapping("MtObject", 3229, 34029)

    # Get symbols - should return list with MtObject
    symbols = cache.get_cu_symbols(3229)
    assert symbols == ["MtObject"]

    # Add second symbol to same CU
    cache.add_symbol_cu_mapping("u32", 3229, 16675)

    # Should now have both symbols
    symbols = cache.get_cu_symbols(3229)
    assert set(symbols) == {"MtObject", "u32"}


@pytest.mark.unit
def test_string_keys_consistency(tmp_path: Path):
    """Test that cu_offset keys are consistently stored as strings."""
    cache_file = tmp_path / "test_cache.json"
    cache = PersistentSymbolCache(cache_file)

    # Add symbols with integer CU offsets
    cache.add_symbol_cu_mapping("test1", 3229, 1000)
    cache.add_symbol_cu_mapping("test2", 0, 2000)

    cache.save()

    # Load raw JSON and verify keys are strings
    with open(cache_file, encoding="utf-8") as f:
        data = json.load(f)

    # All keys should be strings in the loaded data
    for key in data["cu_offset_to_symbols"]:
        assert isinstance(key, str), f"Key {key} is {type(key)}, expected str"

    # Verify we can retrieve using integer offsets
    symbols_3229 = cache.get_cu_symbols(3229)
    symbols_0 = cache.get_cu_symbols(0)
    assert "test1" in symbols_3229
    assert "test2" in symbols_0


@pytest.mark.unit
def test_corrupted_cache_raises_error(tmp_path: Path):
    """Test that loading a corrupted cache file with duplicate keys raises an error."""
    cache_file = tmp_path / "corrupted_cache.json"

    # Create a corrupted cache file with duplicate keys (simulating the bug)
    corrupted_data = {
        "version": "2.0",
        "symbol_to_offset": {
            "MtObject": 34029,
            "u32": 16675,
            "MtPropertyList": 76092,
            "size_t": 2360,
            "bool": 1347,
        },
        "offset_to_symbol": {
            "34029": "MtObject",
            "16675": "u32",
            "76092": "MtPropertyList",
            "2360": "size_t",
            "1347": "bool",
        },
        "symbol_to_cu_offset": {
            "MtObject": 3229,
            "u32": 3229,
            "MtPropertyList": 3229,
            "size_t": 0,
            "bool": 0,
        },
        # This is what the file looks like with duplicate keys - JSON parser keeps last value
        "cu_offset_to_symbols": {
            "3229": ["MtPropertyList"],  # Lost MtObject and u32!
            "0": ["bool"],  # Lost size_t!
        },
        "created": 1760200259.362108,
        "last_updated": 1760200804.847423,
    }

    # Write corrupted cache
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(corrupted_data, f, indent=2)

    # Load cache - should raise ValueError
    with pytest.raises(ValueError, match="Cache file is corrupted"):
        PersistentSymbolCache(cache_file)

