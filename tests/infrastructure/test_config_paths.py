"""Configuration override, validation, and cache-path tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.infrastructure.config import Config
from ddon_dwarf_reconstructor.infrastructure.config.dwarf_config import (
    DwarfRuntimeConfig,
    get_cache_file_path,
)


@pytest.mark.unit
def test_config_from_args_applies_only_explicit_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELF_FILE_PATH", "env.elf")
    monkeypatch.setenv("OUTPUT_DIR", "env-output")
    monkeypatch.setenv("VERBOSE", "false")

    config = Config.from_args(output_dir=Path("explicit"), verbose=True)

    assert config.elf_file_path == Path("env.elf")
    assert config.output_dir == Path("explicit")
    assert config.verbose is True


@pytest.mark.unit
def test_config_validation_and_output_directories(tmp_path: Path) -> None:
    missing = Config(tmp_path / "missing.elf", tmp_path / "out")
    with pytest.raises(ValueError, match="not found"):
        missing.validate()

    directory = tmp_path / "directory"
    directory.mkdir()
    with pytest.raises(ValueError, match="Not a file"):
        Config(directory, tmp_path / "out").validate()

    config = Config(tmp_path / "source.elf", tmp_path / "out", log_dir=tmp_path / "logs")
    config.ensure_output_dir()
    config.ensure_log_dir()
    assert config.output_dir.is_dir()
    assert config.log_dir.is_dir()


@pytest.mark.unit
def test_dwarf_config_reads_validated_environment_types(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DWARF_DIE_CACHE_SIZE", "42")
    monkeypatch.setenv("DWARF_TYPE_CACHE_SIZE", "17")
    monkeypatch.setenv("DWARF_MAX_SEARCH_TIME_MS", "250")

    config = DwarfRuntimeConfig.from_environment()

    assert config.die_cache_size == 42
    assert config.type_cache_size == 17
    assert config.search_timeout_seconds == 0.25


@pytest.mark.unit
@pytest.mark.parametrize("value", ["invalid", "0", "-1"])
def test_dwarf_config_rejects_invalid_cache_size(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("DWARF_DIE_CACHE_SIZE", value)

    with pytest.raises(ValueError, match="DWARF_DIE_CACHE_SIZE"):
        DwarfRuntimeConfig.from_environment()


@pytest.mark.unit
def test_dwarf_config_rejects_invalid_search_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DWARF_MAX_SEARCH_TIME_MS", "invalid")

    with pytest.raises(ValueError, match="DWARF_MAX_SEARCH_TIME_MS"):
        DwarfRuntimeConfig.from_environment()


@pytest.mark.unit
def test_cache_file_path_is_source_specific(tmp_path: Path) -> None:
    source = tmp_path / "DDOORBIS.elf"

    first = get_cache_file_path(str(source))
    second = get_cache_file_path(str(tmp_path / "other" / "DDOORBIS.elf"))

    assert first.name.startswith("DDOORBIS-")
    assert first.suffix == ".json"
    assert first != second
