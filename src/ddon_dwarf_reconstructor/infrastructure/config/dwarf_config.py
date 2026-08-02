#!/usr/bin/env python3

"""Validated configuration for DWARF-specific runtime services."""

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from ..artifacts import get_artifact_cache_dir


@dataclass(frozen=True, slots=True)
class DwarfRuntimeConfig:
    """Runtime values required by the lazy DWARF use case."""

    die_cache_size: int = 10_000
    type_cache_size: int = 5_000
    search_timeout_seconds: float = 1.0

    @classmethod
    def from_environment(cls) -> DwarfRuntimeConfig:
        """Load and validate the supported ``DWARF_*`` settings."""
        return cls(
            die_cache_size=_positive_int("DWARF_DIE_CACHE_SIZE", 10_000),
            type_cache_size=_positive_int("DWARF_TYPE_CACHE_SIZE", 5_000),
            search_timeout_seconds=_positive_float("DWARF_MAX_SEARCH_TIME_MS", 1_000) / 1000,
        )


def _positive_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive integer, got {value!r}") from error
    if parsed <= 0:
        raise ValueError(f"{name} must be positive, got {parsed}")
    return parsed


def _positive_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive number, got {value!r}") from error
    if parsed <= 0:
        raise ValueError(f"{name} must be positive, got {parsed}")
    return parsed


def get_cache_file_path(elf_file_path: str) -> Path:
    """Get cache file path for a specific ELF file.

    Args:
        elf_file_path: Path to ELF file

    Returns:
        Path to cache file
    """
    elf_path = Path(elf_file_path)

    cache_dir = get_artifact_cache_dir()

    path_digest = hashlib.sha256(str(elf_path.resolve()).encode()).hexdigest()[:12]
    cache_file = cache_dir / f"{elf_path.stem}-{path_digest}-dwarf-cache.json"

    return cache_file
