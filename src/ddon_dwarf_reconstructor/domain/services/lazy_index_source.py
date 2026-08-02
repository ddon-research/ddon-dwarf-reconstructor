"""Source binding for the lazy DWARF index."""

from __future__ import annotations

from pathlib import Path

from ...core.observability import get_logger
from ..ports.source_identity import SourceIdentityPort

logger = get_logger(__name__)


class LazyIndexSourceMixin:
    @staticmethod
    def _source_fingerprint(
        source_identity: SourceIdentityPort | None, path: Path
    ) -> dict[str, int | str] | None:
        """Resolve a source binding through the infrastructure identity port."""
        if source_identity is None:
            logger.warning("No source identity provider configured for %s", path)
            return None
        try:
            return source_identity.identify(path).as_fingerprint()
        except OSError as error:
            logger.warning(
                "Cannot identify DWARF source %s: %s", path.resolve(), error, exc_info=error
            )
            return None
