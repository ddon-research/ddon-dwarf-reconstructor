"""Tests for runtime cache placement."""

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.infrastructure.config.dwarf_config import get_cache_file_path


@pytest.mark.unit
def test_cache_defaults_outside_elf_resource_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Runtime caches use the operating-system cache root, not tracked resources."""
    local_app_data = tmp_path / "local-app-data"
    elf_path = tmp_path / "repository" / "resources" / "DDOORBIS.elf"
    monkeypatch.delenv("DWARF_CACHE_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))

    cache_path = get_cache_file_path(str(elf_path))

    assert cache_path.parent == local_app_data / "ddon-dwarf-reconstructor"
    assert cache_path.parent != elf_path.parent / ".cache"
    assert cache_path.name.startswith("DDOORBIS-")


@pytest.mark.unit
def test_explicit_cache_root_is_respected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Operators can place runtime caches at an explicit untracked location."""
    cache_root = tmp_path / "custom-cache"
    monkeypatch.setenv("DWARF_CACHE_DIR", str(cache_root))

    cache_path = get_cache_file_path(str(tmp_path / "DDOORBIS.elf"))

    assert cache_path.parent == cache_root
