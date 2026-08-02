"""Source identity and legacy-cache binding for the lazy DWARF index."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ...core.observability import get_logger
from .lazy_index_context import LazyIndexContext

logger = get_logger(__name__)


class LazyIndexSourceMixin:
    @staticmethod
    def _source_fingerprint(path: Path) -> dict[str, int | str] | None:
        """Return a bounded source fingerprint for cache binding."""
        resolved = path.resolve()
        try:
            stat = resolved.stat()
            digest = hashlib.sha256()
            with resolved.open("rb") as source:
                digest.update(source.read(64 * 1024))
                if stat.st_size > 64 * 1024:
                    source.seek(max(0, stat.st_size - 64 * 1024))
                    digest.update(source.read(64 * 1024))
        except OSError as error:
            logger.warning("Cannot fingerprint DWARF source %s: %s", resolved, error)
            return None
        return {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "boundary_sha256": digest.hexdigest(),
        }

    def _validate_unbound_cache(self: LazyIndexContext, data: dict[str, Any]) -> bool:
        """Validate a small sample before binding a legacy cache to this source."""
        mappings = list(data.get("symbol_to_offset", {}).items())[:8]
        if not mappings:
            return False
        try:
            for symbol, offset in mappings:
                die = self.dwarf_info.get_DIE_from_refaddr(int(offset))
                if die is None:
                    return False
                name_attribute = die.attributes.get("DW_AT_name")
                if name_attribute is None:
                    return False
                raw_name = name_attribute.value
                die_name = (
                    raw_name.decode("utf-8", errors="replace")
                    if isinstance(raw_name, bytes)
                    else str(raw_name)
                )
                if die_name != str(symbol).rsplit("::", 1)[-1]:
                    return False
        except AttributeError, KeyError, TypeError, ValueError, RuntimeError:
            return False
        logger.info("Validated %s legacy cache offsets against the current ELF", len(mappings))
        return True

    def get_elf_hash(self, elf_file_path: str) -> str:
        """Return the compatibility first-block ELF hash."""
        try:
            with open(elf_file_path, "rb") as source:
                return hashlib.sha256(source.read(65536)).hexdigest()[:16]
        except OSError:
            return ""
