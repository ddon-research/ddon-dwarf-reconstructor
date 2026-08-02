#!/usr/bin/env python3

"""Configuration for DWARF-specific lazy loading components."""

import contextlib
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from ..artifacts import get_artifact_cache_dir

# Default configuration values
DEFAULT_CONFIG = {
    # Cache sizes
    "DIE_CACHE_SIZE": 10000,
    "TYPE_CACHE_SIZE": 5000,
    # Cache file settings
    "CACHE_FILE": ".dwarf_cache.json",
    "CACHE_DIR": ".cache",
    # Feature flags
    "ENABLE_LAZY_LOADING": True,
    "ENABLE_PERSISTENT_CACHE": True,
    "FALLBACK_TO_FULL_SCAN": True,
    # Performance tuning
    "CACHE_HIT_THRESHOLD": 0.8,  # Minimum cache hit rate
    "MAX_SEARCH_TIME_MS": 1000,  # Max time for targeted search
}


def get_config() -> dict[str, Any]:
    """Get configuration with environment variable overrides.

    Returns:
        Configuration dictionary
    """
    config = DEFAULT_CONFIG.copy()

    # Override with environment variables
    for key in config:
        env_value = os.getenv(f"DWARF_{key}")
        if env_value is not None:
            # Convert to appropriate type
            if isinstance(config[key], bool):
                config[key] = env_value.lower() in ("true", "1", "yes", "on")
            elif isinstance(config[key], int):
                with contextlib.suppress(ValueError):
                    config[key] = int(env_value)
            elif isinstance(config[key], float):
                with contextlib.suppress(ValueError):
                    config[key] = float(env_value)
            else:
                config[key] = env_value

    return config


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

    legacy_cache = elf_path.parent / ".cache" / f"{elf_path.stem}_dwarf_cache.json"
    if not cache_file.exists() and legacy_cache.exists():
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{cache_file.name}.", dir=cache_dir)
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        try:
            shutil.copyfile(legacy_cache, temporary_path)
            temporary_path.replace(cache_file)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    return cache_file
