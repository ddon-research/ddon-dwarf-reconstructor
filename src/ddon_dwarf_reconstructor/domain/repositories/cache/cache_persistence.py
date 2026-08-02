"""Focused persistent-symbol-cache operations."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from time import monotonic, sleep, time
from typing import Any

from ....infrastructure.logging import get_logger
from .cache_context import CacheContext

logger = get_logger(__name__)


class CachePersistenceMixin:
    def save(self: CacheContext) -> None:
        """Save cache to disk only if content actually changed.

        Compares current cache data against disk content, ignoring timestamps.
        Only writes to disk if symbol mappings have changed, reducing I/O.
        """
        if not self._modified:
            return

        # Load current disk content for comparison
        disk_data = self._load_disk_cache_for_comparison()

        # Compare content (ignore timestamps)
        if self._cache_content_unchanged(disk_data):
            logger.debug(
                f"Cache content unchanged (only timestamps differ), "
                f"skipping save to {self.cache_file}"
            )
            self._modified = False
            return

        # Content changed, proceed with an atomic, process-serialized save.
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with self._exclusive_lock():
                latest_data = self._load_disk_cache_for_comparison()
                self.data = self._merge_with_disk(latest_data)
                self._atomic_write(self.data)
            logger.info(
                f"Saved cache to {self.cache_file} ({len(self.data['symbol_to_offset'])} symbols)"
            )
            self._modified = False
        except OSError as e:
            logger.error(f"Failed to save cache to {self.cache_file}: {e}")

    def restore_from(self: CacheContext, source_cache_file: str | Path) -> dict[str, Any]:
        """Atomically replace this cache from an explicitly selected cache.

        This operator repair intentionally does not merge with current disk
        state. It preserves this cache's source fingerprint while migrating and
        validating the replacement content.
        """
        source_path = Path(source_cache_file).resolve()
        if source_path == self.cache_file.resolve():
            raise ValueError("Source and destination symbol caches are identical")
        replacement = self._new_cache(source_path)
        replacement.data["source_fingerprint"] = self.data.get("source_fingerprint")
        replacement.source_fingerprint = self.source_fingerprint
        replacement._validate_cache_integrity(replacement.data)

        with self._exclusive_lock():
            self.data = deepcopy(replacement.data)
            self.data["last_updated"] = time()
            self._atomic_write(self.data)
        self._modified = False
        return self.get_statistics()

    def _load_disk_cache_for_comparison(self: CacheContext) -> dict[str, Any]:
        """Load cache from disk for content comparison.

        Returns:
            Cache data from disk, or empty dict if file doesn't exist
        """
        try:
            if self.cache_file.exists():
                with open(self.cache_file, encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        return {str(key): value for key, value in loaded.items()}
        except (json.JSONDecodeError, OSError) as e:
            logger.debug(f"Could not load disk cache for comparison: {e}")

        return {}

    def _cache_content_unchanged(self: CacheContext, disk_data: dict[str, Any]) -> bool:
        """Compare cache data, ignoring timestamps.

        Args:
            disk_data: Data loaded from disk

        Returns:
            True if content is identical (except timestamps)
        """
        # If disk is empty, we have changes
        if not disk_data:
            return False

        # Compare all symbol mapping sections (ignore timestamps)
        return (
            self.data.get("version") == disk_data.get("version")
            and self.data.get("source_fingerprint") == disk_data.get("source_fingerprint")
            and self.data.get("symbol_to_offset") == disk_data.get("symbol_to_offset")
            and self.data.get("offset_to_symbol") == disk_data.get("offset_to_symbol")
            and self.data.get("symbol_to_cu_offset") == disk_data.get("symbol_to_cu_offset")
            and self.data.get("symbol_definitions") == disk_data.get("symbol_definitions")
            and self.data.get("cu_offset_to_symbols") == disk_data.get("cu_offset_to_symbols")
        )

    def _atomic_write(self: CacheContext, data: dict[str, Any]) -> None:
        """Flush a complete JSON document before atomically replacing the cache."""
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.cache_file.name}.", dir=self.cache_file.parent
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
                json.dump(data, output, indent=2, sort_keys=True)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            temporary_path.replace(self.cache_file)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def _merge_with_disk(self: CacheContext, disk_data: dict[str, Any]) -> dict[str, Any]:
        """Preserve compatible updates published by another process while waiting."""
        if not self._can_merge_disk_data(disk_data):
            return self.data

        merged = deepcopy(disk_data)
        self._merge_symbol_maps(merged)
        self._merge_definition_records(merged)
        self._select_best_definitions(merged)
        self._rebuild_reverse_maps(merged)
        merged["last_updated"] = max(
            float(disk_data.get("last_updated", 0)), float(self.data.get("last_updated", 0))
        )
        return merged

    def _can_merge_disk_data(self: CacheContext, disk_data: dict[str, Any]) -> bool:
        return bool(
            disk_data
            and disk_data.get("version") == self.CURRENT_VERSION
            and disk_data.get("source_fingerprint") == self.data.get("source_fingerprint")
        )

    def _merge_symbol_maps(self: CacheContext, merged: dict[str, Any]) -> None:
        for symbol, offset in self.data.get("symbol_to_offset", {}).items():
            merged["symbol_to_offset"][symbol] = offset
        for symbol, cu_offset in self.data.get("symbol_to_cu_offset", {}).items():
            merged["symbol_to_cu_offset"][symbol] = cu_offset

    def _merge_definition_records(self: CacheContext, merged: dict[str, Any]) -> None:
        merged_definitions = merged.setdefault("symbol_definitions", {})
        for symbol, definitions in self.data.get("symbol_definitions", {}).items():
            merged_definitions[symbol] = self._merge_definition_list(
                merged_definitions.get(symbol, []), definitions
            )

    @staticmethod
    def _merge_definition_list(
        existing_definitions: list[dict[str, Any]],
        new_definitions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        by_location = {
            (item["cu_offset"], item["die_offset"]): item for item in existing_definitions
        }
        for definition in new_definitions:
            key = (definition["cu_offset"], definition["die_offset"])
            existing = by_location.get(key)
            if existing is None:
                by_location[key] = deepcopy(definition)
                continue
            existing["score"] = max(existing.get("score", 0), definition.get("score", 0))
            existing["complete"] = existing.get("complete", True) or definition.get(
                "complete", True
            )
        return list(by_location.values())

    @staticmethod
    def _select_best_definitions(merged: dict[str, Any]) -> None:
        merged_definitions = merged.get("symbol_definitions", {})
        for symbol, definitions in merged_definitions.items():
            if not definitions:
                continue
            complete = [item for item in definitions if item.get("complete", True)]
            best = max(complete or definitions, key=lambda item: item.get("score", 0))
            merged["symbol_to_offset"][symbol] = best["die_offset"]
            merged["symbol_to_cu_offset"][symbol] = best["cu_offset"]

    @staticmethod
    def _rebuild_reverse_maps(merged: dict[str, Any]) -> None:
        merged["offset_to_symbol"] = {
            str(offset): symbol for symbol, offset in merged["symbol_to_offset"].items()
        }
        cu_symbols: dict[str, list[str]] = {}
        for symbol, cu_offset in merged["symbol_to_cu_offset"].items():
            cu_symbols.setdefault(str(cu_offset), []).append(symbol)
        merged["cu_offset_to_symbols"] = {
            key: sorted(symbols) for key, symbols in sorted(cu_symbols.items())
        }

    @contextmanager
    def _exclusive_lock(self: CacheContext) -> Generator[None]:
        """Serialize cache publication and recover abandoned lock files."""
        lock_path = self.cache_file.with_suffix(f"{self.cache_file.suffix}.lock")
        deadline = monotonic() + self.LOCK_TIMEOUT_SECONDS
        descriptor: int | None = None
        while descriptor is None:
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(descriptor, f"pid={os.getpid()}\ncreated={time()}\n".encode())
            except FileExistsError:
                try:
                    is_stale = time() - lock_path.stat().st_mtime > self.STALE_LOCK_SECONDS
                except FileNotFoundError:
                    continue
                if is_stale:
                    lock_path.unlink(missing_ok=True)
                    continue
                if monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for cache lock: {lock_path}") from None
                sleep(0.05)
        try:
            yield
        finally:
            os.close(descriptor)
            lock_path.unlink(missing_ok=True)
