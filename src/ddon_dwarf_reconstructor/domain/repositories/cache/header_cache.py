"""
Cache for tracking generated header metadata and supporting incremental builds.

HeaderCache persists across runs, storing hashes of header content to detect
when regeneration is needed. This enables fast re-runs where unchanged
classes skip regeneration.

Architecture:
- Cache file: .cache/{elf_name}_headers.json
- Format: {class_name: {"hash": str, "file": str, "generated_at": float}}
- Hash: SHA256 of header content (content addressable)
- Invalidation: CU or class DIE offset changes (detected via version)

Usage:
    cache = HeaderCache(elf_path)

    # Check if class header is cached
    if cache.is_valid("MtObject", header_content):
        print("Reuse cached header")
    else:
        print("Regenerate header")
        cache.set_header("MtObject", header_content, file_path="MtObject.h")

    cache.save()
"""

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import TypedDict


class HeaderMetadata(TypedDict):
    """Metadata for a cached header."""

    hash: str
    file: str
    generated_at: float


class HeaderCache:
    """Track generated header content with SHA256 hashes for change detection."""

    def __init__(self, elf_path: str, cache_dir: str = ".cache") -> None:
        """
        Initialize header cache for an ELF file.

        Args:
            elf_path: Path to the ELF file (used to derive cache filename)
            cache_dir: Directory for cache files (default: .cache)

        Caches are stored as:
            {cache_dir}/{elf_name}_headers.json
        """
        self.elf_path = Path(elf_path)
        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / f"{self.elf_path.stem}_headers.json"

        self._cache: dict[str, HeaderMetadata] = {}
        self._dirty = False

        self._load_cache()

    def _load_cache(self) -> None:
        """Load cache from disk if it exists."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    data = json.load(f)
                    self._cache = {
                        name: HeaderMetadata(
                            hash=item["hash"],
                            file=item["file"],
                            generated_at=item["generated_at"],
                        )
                        for name, item in data.items()
                    }
            except json.JSONDecodeError, KeyError:
                # Cache corrupted, start fresh
                self._cache = {}

    def save(self) -> None:
        """Persist cache to disk if modified."""
        if not self._dirty:
            return

        self.cache_dir.mkdir(parents=True, exist_ok=True)

        cache_data = {
            name: {
                "hash": metadata["hash"],
                "file": metadata["file"],
                "generated_at": metadata["generated_at"],
            }
            for name, metadata in self._cache.items()
        }

        with open(self.cache_file, "w") as f:
            json.dump(cache_data, f, indent=2)

        self._dirty = False

    def is_valid(self, class_name: str, header_content: str) -> bool:
        """
        Check if cached header matches current content (same hash).

        Args:
            class_name: Name of the class
            header_content: Current header content

        Returns:
            True if cache exists and hash matches, False otherwise
        """
        if class_name not in self._cache:
            return False

        content_hash = self._compute_hash(header_content)
        cached_hash = self._cache[class_name]["hash"]

        return content_hash == cached_hash

    def set_header(self, class_name: str, header_content: str, file_path: str = "") -> None:
        """
        Store header in cache with SHA256 hash of content.

        Args:
            class_name: Name of the class
            header_content: Header C++ code content
            file_path: Optional file path where header will be written
        """
        content_hash = self._compute_hash(header_content)

        self._cache[class_name] = HeaderMetadata(
            hash=content_hash,
            file=file_path or f"{class_name}.h",
            generated_at=time.time(),
        )

        self._dirty = True

    def get_header_metadata(self, class_name: str) -> HeaderMetadata | None:
        """
        Retrieve cached metadata for a class header.

        Args:
            class_name: Name of the class

        Returns:
            HeaderMetadata dict if cached, None otherwise
        """
        return self._cache.get(class_name)

    def get_all_cached(self) -> dict[str, HeaderMetadata]:
        """
        Get all cached headers.

        Returns:
            Dict mapping class names to metadata
        """
        return dict(self._cache)

    def remove(self, class_name: str) -> bool:
        """
        Remove header from cache (invalidate).

        Args:
            class_name: Name of the class

        Returns:
            True if removed, False if not in cache
        """
        if class_name in self._cache:
            del self._cache[class_name]
            self._dirty = True
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._dirty = True

    def summarize(self) -> str:
        """
        Generate cache summary report.

        Returns:
            Human-readable string with cache stats
        """
        if not self._cache:
            return "Cache empty"

        total = len(self._cache)
        recent = sum(1 for m in self._cache.values() if time.time() - m["generated_at"] < 3600)

        lines = [
            f"Cache: {self.cache_file}",
            f"Total headers: {total}",
            f"Generated in last hour: {recent}",
        ]

        if self._cache:
            lines.append("\nHeaders:")
            for name, metadata in sorted(self._cache.items()):
                dt = datetime.fromtimestamp(metadata["generated_at"]).strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"  {name}: {metadata['file']} ({dt})")

        return "\n".join(lines)

    @staticmethod
    def _compute_hash(content: str) -> str:
        """
        Compute SHA256 hash of content.

        Args:
            content: String content to hash

        Returns:
            Hex string of SHA256 hash
        """
        return hashlib.sha256(content.encode()).hexdigest()
