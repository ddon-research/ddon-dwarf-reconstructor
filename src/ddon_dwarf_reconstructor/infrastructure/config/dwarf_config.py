#!/usr/bin/env python3

"""Configuration for DWARF-specific lazy loading components."""

import os
from pathlib import Path

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


def get_config() -> dict:
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
                try:
                    config[key] = int(env_value)
                except ValueError:
                    pass
            elif isinstance(config[key], float):
                try:
                    config[key] = float(env_value)
                except ValueError:
                    pass
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
    config = get_config()
    elf_path = Path(elf_file_path)

    # Create cache directory next to ELF file
    cache_dir = elf_path.parent / config["CACHE_DIR"]
    cache_dir.mkdir(exist_ok=True)

    # Cache file name based on ELF file name
    cache_file = cache_dir / f"{elf_path.stem}_dwarf_cache.json"

    return cache_file
