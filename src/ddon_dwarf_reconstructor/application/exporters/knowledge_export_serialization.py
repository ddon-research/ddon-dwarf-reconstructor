"""Serialization helpers for knowledge export."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ...domain.models.dwarf import ClassInfo
from .knowledge_export_context import KnowledgeExportContext


class KnowledgeExportSerializationMixin:
    def _type_id(self: KnowledgeExportContext, class_info: ClassInfo, fallback_name: str) -> str:
        """Return a source-scoped type identifier stable across repeated exports."""
        identifier = (
            str(class_info.die_offset) if class_info.die_offset is not None else fallback_name
        )
        return f"type:{self.build_id}:{identifier}"

    @staticmethod
    def _ordered_names(class_infos: dict[str, ClassInfo], hierarchy_order: list[str]) -> list[str]:
        """Return hierarchy names first, followed by remaining names deterministically."""
        known = [name for name in hierarchy_order if name in class_infos]
        remaining = sorted(name for name in class_infos if name not in known)
        return known + remaining

    @staticmethod
    def _node(node_id: str, kind: str, properties: dict[str, Any]) -> dict[str, Any]:
        """Build a JSON-serializable graph node record."""
        return {"id": node_id, "kind": kind, "properties": properties}

    @staticmethod
    def _relationship(
        source_id: str,
        relationship_type: str,
        target_id: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a JSON-serializable graph relationship record."""
        return {
            "source_id": source_id,
            "type": relationship_type,
            "target_id": target_id,
            "properties": properties or {},
        }

    @staticmethod
    def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
        """Write graph records in a stable JSONL representation."""
        content = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
        path.write_text(content, encoding="utf-8")

    @staticmethod
    def _deduplicate_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate deterministic nodes and reject conflicting identities."""
        unique: dict[str, dict[str, Any]] = {}
        for node in nodes:
            existing = unique.get(node["id"])
            if existing is not None and existing != node:
                raise ValueError(f"Conflicting graph node: {node['id']}")
            unique[node["id"]] = node
        return [unique[node_id] for node_id in sorted(unique)]

    @staticmethod
    def _deduplicate_relationships(
        relationships: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return relationships sorted and deduplicated by complete content."""
        unique = {
            json.dumps(relationship, sort_keys=True, separators=(",", ":")): relationship
            for relationship in relationships
        }
        return [unique[key] for key in sorted(unique)]

    @staticmethod
    def _sha256_file(path: Path) -> str:
        """Return the SHA-256 digest of a file without loading it into memory."""
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _file_descriptor(self: KnowledgeExportContext, path: Path) -> dict[str, Any]:
        """Describe a generated graph artifact for the manifest."""
        return {"path": path.name, "sha256": self._sha256_file(path)}
