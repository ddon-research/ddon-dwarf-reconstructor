"""Unit tests for HeaderCache service."""

import json
import tempfile
from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.domain.repositories.cache.header_cache import (
    HeaderCache,
)


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def cache_instance(temp_cache_dir):
    """Create a HeaderCache instance for testing."""
    return HeaderCache("test.elf", cache_dir=temp_cache_dir)


@pytest.mark.unit
def test_init_creates_cache_dir_path(temp_cache_dir):
    """Test that __init__ sets up correct cache file path."""
    cache = HeaderCache("DDOORBIS.elf", cache_dir=temp_cache_dir)

    expected_file = Path(temp_cache_dir) / "DDOORBIS_headers.json"
    assert cache.cache_file == expected_file


@pytest.mark.unit
def test_set_and_get_header_metadata(cache_instance):
    """Test storing and retrieving header metadata."""
    content = "class MtObject { /* ... */ };"
    cache_instance.set_header("MtObject", content, file_path="MtObject.h")

    metadata = cache_instance.get_header_metadata("MtObject")
    assert metadata is not None
    assert metadata["file"] == "MtObject.h"
    assert isinstance(metadata["hash"], str)
    assert len(metadata["hash"]) == 64  # SHA256 hex length


@pytest.mark.unit
def test_set_header_marks_dirty(cache_instance):
    """Test that set_header marks cache as dirty (needs save)."""
    assert cache_instance._dirty is False

    cache_instance.set_header("TestClass", "content")
    assert cache_instance._dirty is True


@pytest.mark.unit
def test_is_valid_with_matching_content(cache_instance):
    """Test is_valid returns True when content hash matches."""
    content = "class MtObject { int value; };"
    cache_instance.set_header("MtObject", content)

    # Same content should be valid
    assert cache_instance.is_valid("MtObject", content) is True


@pytest.mark.unit
def test_is_valid_with_different_content(cache_instance):
    """Test is_valid returns False when content differs."""
    content1 = "class MtObject { int value; };"
    content2 = "class MtObject { int value; int extra; };"

    cache_instance.set_header("MtObject", content1)

    assert cache_instance.is_valid("MtObject", content2) is False


@pytest.mark.unit
def test_is_valid_with_uncached_class(cache_instance):
    """Test is_valid returns False for uncached classes."""
    assert cache_instance.is_valid("NonexistentClass", "content") is False


@pytest.mark.unit
def test_get_header_metadata_nonexistent(cache_instance):
    """Test get_header_metadata returns None for missing class."""
    assert cache_instance.get_header_metadata("NonexistentClass") is None


@pytest.mark.unit
def test_remove_existing_header(cache_instance):
    """Test removing an existing header from cache."""
    cache_instance.set_header("MtObject", "content")
    assert "MtObject" in cache_instance._cache

    removed = cache_instance.remove("MtObject")
    assert removed is True
    assert "MtObject" not in cache_instance._cache


@pytest.mark.unit
def test_remove_nonexistent_header(cache_instance):
    """Test removing a nonexistent header returns False."""
    removed = cache_instance.remove("NonexistentClass")
    assert removed is False


@pytest.mark.unit
def test_remove_marks_dirty(cache_instance):
    """Test that remove marks cache as dirty."""
    cache_instance.set_header("MtObject", "content")
    cache_instance._dirty = False

    cache_instance.remove("MtObject")
    assert cache_instance._dirty is True


@pytest.mark.unit
def test_clear_removes_all_entries(cache_instance):
    """Test clear removes all cached headers."""
    cache_instance.set_header("MtObject", "content1")
    cache_instance.set_header("MtVector4", "content2")

    cache_instance.clear()

    assert len(cache_instance._cache) == 0
    assert cache_instance._dirty is True


@pytest.mark.unit
def test_get_all_cached(cache_instance):
    """Test get_all_cached returns dict of all headers."""
    cache_instance.set_header("MtObject", "content1")
    cache_instance.set_header("MtVector4", "content2")

    all_cached = cache_instance.get_all_cached()

    assert len(all_cached) == 2
    assert "MtObject" in all_cached
    assert "MtVector4" in all_cached


@pytest.mark.unit
def test_save_creates_cache_file(cache_instance):
    """Test save creates cache JSON file with correct format."""
    cache_instance.set_header("MtObject", "class content", file_path="MtObject.h")
    cache_instance.save()

    assert cache_instance.cache_file.exists()

    # Verify JSON format
    with open(cache_instance.cache_file) as f:
        data = json.load(f)

    assert "MtObject" in data
    assert "hash" in data["MtObject"]
    assert "file" in data["MtObject"]
    assert "generated_at" in data["MtObject"]
    assert data["MtObject"]["file"] == "MtObject.h"


@pytest.mark.unit
def test_save_does_not_write_if_not_dirty(temp_cache_dir):
    """Test save skips writing if cache not modified."""
    cache = HeaderCache("test.elf", cache_dir=temp_cache_dir)

    # Initially not dirty
    assert cache._dirty is False

    # Create cache file manually
    cache.cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache.cache_file.write_text("{}")

    original_mtime = cache.cache_file.stat().st_mtime

    # Call save when not dirty - should not modify file
    import time

    time.sleep(0.01)  # Ensure time difference if file is written
    cache.save()

    new_mtime = cache.cache_file.stat().st_mtime
    assert original_mtime == new_mtime


@pytest.mark.unit
def test_load_cache_from_disk(temp_cache_dir):
    """Test loading existing cache from disk."""
    # Create cache file
    cache_file = Path(temp_cache_dir) / "existing_headers.json"
    cache_data = {
        "MtObject": {
            "hash": "abc123def456",
            "file": "MtObject.h",
            "generated_at": 1234567890.0,
        },
        "MtVector4": {
            "hash": "xyz789uvw012",
            "file": "MtVector4.h",
            "generated_at": 1234567891.0,
        },
    }

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w") as f:
        json.dump(cache_data, f)

    # Create cache instance - should load from disk
    cache = HeaderCache("existing.elf", cache_dir=temp_cache_dir)

    # Mock the ELF filename lookup
    cache.cache_file = cache_file

    cache._load_cache()

    assert len(cache._cache) == 2
    assert cache._cache["MtObject"]["hash"] == "abc123def456"
    assert cache._cache["MtVector4"]["file"] == "MtVector4.h"


@pytest.mark.unit
def test_load_cache_handles_corrupted_file(temp_cache_dir):
    """Test load_cache recovers from corrupted JSON."""
    cache_file = Path(temp_cache_dir) / "corrupted_headers.json"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text("{ invalid json }")

    cache = HeaderCache("test.elf", cache_dir=temp_cache_dir)
    cache.cache_file = cache_file

    cache._load_cache()

    # Should start with empty cache after error
    assert len(cache._cache) == 0


@pytest.mark.unit
def test_load_cache_handles_missing_file(temp_cache_dir):
    """Test load_cache when file does not exist."""
    cache = HeaderCache("nonexistent.elf", cache_dir=temp_cache_dir)

    # Should not raise, just start with empty cache
    assert len(cache._cache) == 0


@pytest.mark.unit
def test_compute_hash_consistent(cache_instance):
    """Test that _compute_hash produces consistent results."""
    content = "class MtObject { int x; };"

    hash1 = HeaderCache._compute_hash(content)
    hash2 = HeaderCache._compute_hash(content)

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hex


@pytest.mark.unit
def test_compute_hash_different_content(cache_instance):
    """Test that different content produces different hashes."""
    hash1 = HeaderCache._compute_hash("content1")
    hash2 = HeaderCache._compute_hash("content2")

    assert hash1 != hash2


@pytest.mark.unit
def test_set_header_with_empty_file_path(cache_instance):
    """Test set_header derives filename from class name if not provided."""
    cache_instance.set_header("MtObject", "content")

    metadata = cache_instance.get_header_metadata("MtObject")
    assert metadata["file"] == "MtObject.h"


@pytest.mark.unit
def test_set_header_with_custom_file_path(cache_instance):
    """Test set_header uses provided file path."""
    cache_instance.set_header("MtObject", "content", file_path="custom/path/MtObject.h")

    metadata = cache_instance.get_header_metadata("MtObject")
    assert metadata["file"] == "custom/path/MtObject.h"


@pytest.mark.unit
def test_summarize_empty_cache(cache_instance):
    """Test summarize with empty cache."""
    summary = cache_instance.summarize()
    assert "Cache empty" in summary


@pytest.mark.unit
def test_summarize_with_entries(cache_instance):
    """Test summarize with multiple cached entries."""
    cache_instance.set_header("MtObject", "content1", file_path="MtObject.h")
    cache_instance.set_header("MtVector4", "content2", file_path="MtVector4.h")

    summary = cache_instance.summarize()

    assert "Total headers: 2" in summary
    assert "MtObject" in summary
    assert "MtVector4" in summary
    assert "MtObject.h" in summary


@pytest.mark.unit
def test_summarize_generated_at_timestamp(cache_instance):
    """Test summarize includes generated timestamp."""
    cache_instance.set_header("MtObject", "content")

    summary = cache_instance.summarize()

    # Should contain a timestamp in the output
    assert any(char.isdigit() for char in summary)


@pytest.mark.unit
def test_multiple_classes_independent(cache_instance):
    """Test that multiple classes have independent cache entries."""
    content1 = "class MtObject { int x; };"
    content2 = "class MtVector4 { float x; };"

    cache_instance.set_header("MtObject", content1)
    cache_instance.set_header("MtVector4", content2)

    assert cache_instance.is_valid("MtObject", content1) is True
    assert cache_instance.is_valid("MtObject", content2) is False
    assert cache_instance.is_valid("MtVector4", content2) is True
    assert cache_instance.is_valid("MtVector4", content1) is False


@pytest.mark.unit
def test_save_and_reload_preserves_data(temp_cache_dir):
    """Test that saved cache can be reloaded correctly."""
    # Create and save cache
    cache1 = HeaderCache("test.elf", cache_dir=temp_cache_dir)
    cache1.set_header("MtObject", "class content", file_path="MtObject.h")
    cache1.save()

    # Create new cache instance with same ELF name
    cache2 = HeaderCache("test.elf", cache_dir=temp_cache_dir)

    # Should load the same data
    metadata = cache2.get_header_metadata("MtObject")
    assert metadata is not None
    assert metadata["file"] == "MtObject.h"


@pytest.mark.unit
def test_cache_persistence_across_instances(temp_cache_dir):
    """Test cache persists when creating multiple instances for same ELF."""
    cache1 = HeaderCache("persistent.elf", cache_dir=temp_cache_dir)
    cache1.set_header("Class1", "content1")
    cache1.set_header("Class2", "content2")
    cache1.save()

    # New instance should load from disk
    cache2 = HeaderCache("persistent.elf", cache_dir=temp_cache_dir)

    all_cached = cache2.get_all_cached()
    assert len(all_cached) == 2
    assert "Class1" in all_cached
    assert "Class2" in all_cached
