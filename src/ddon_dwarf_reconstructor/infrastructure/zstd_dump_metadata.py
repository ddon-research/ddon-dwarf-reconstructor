"""Source metadata validation for the compressed DWARF sidecar."""

from __future__ import annotations


class ZstdDumpMetadataMixin:
    """Validate the source identity fields stored in an index."""

    @staticmethod
    def _metadata_matches_source(metadata: dict[str, str], source_metadata: dict[str, str]) -> bool:
        for key in ("source_size", "source_sha256"):
            stored = metadata.get(key)
            if stored is not None and stored != source_metadata[key]:
                return False
        return True
