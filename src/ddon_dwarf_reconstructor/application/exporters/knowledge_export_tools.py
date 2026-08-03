"""Project source-bound external tool exports into knowledge-bundle records."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...domain.models.tool_evidence import ToolExport
from .knowledge_export_context import KnowledgeExportContext

if TYPE_CHECKING:
    from .knowledge_export_core import _OptionalRecords


class KnowledgeExportToolsMixin:
    """Additive graph projection for raw tool output and its provenance."""

    def _append_tool_export_records(
        self: KnowledgeExportContext,
        records: _OptionalRecords,
        root_symbol: str,
        source_id: str,
        exports: Sequence[ToolExport],
    ) -> None:
        """Attach complete tool exports without changing DWARF-derived facts."""
        build_id = f"build:{self.build_id}"
        for export in sorted(exports, key=lambda item: item.artifact_key):
            export.require_complete()
            assert export.output is not None
            tool_id = f"source:tool:{export.tool_name}:{export.tool_sha256[:16]}"
            artifact_id = f"source:{self.build_id}:tool-export:{export.artifact_key}"
            evidence_id = f"evidence:{self.build_id}:tool-export:{export.artifact_key}"
            records.nodes.extend(
                [
                    self._node(
                        tool_id,
                        "Tool",
                        {
                            "name": export.tool_name,
                            "path": Path(export.tool_path).name,
                            "sha256": export.tool_sha256,
                            "version": export.tool_version,
                            "authority": export.authority,
                            "deterministic": True,
                        },
                    ),
                    self._node(
                        artifact_id,
                        "SourceArtifact",
                        {
                            "path": export.output.path,
                            "manifest": export.manifest_name,
                            "sha256": export.output.sha256,
                            "size": export.output.size,
                            "format": export.output.format,
                            "max_output_bytes": export.max_output_bytes,
                            "profile": export.profile,
                            "authority": export.authority,
                            "source_sha256": export.source_sha256,
                            "status": export.status,
                            "deterministic": True,
                        },
                    ),
                    self._node(
                        evidence_id,
                        "Evidence",
                        {
                            "evidence_kind": "external_tool_export",
                            "profile": export.profile,
                            "authority": export.authority,
                            "source_revision": self.build_id,
                            "root_symbol": root_symbol,
                            "artifact_key": export.artifact_key,
                            "status": export.status,
                            "diagnostics": list(export.diagnostics),
                            "deterministic": True,
                        },
                    ),
                ]
            )
            records.relationships.extend(
                [
                    self._relationship(artifact_id, "BELONGS_TO", build_id),
                    self._relationship(artifact_id, "DERIVED_FROM", source_id),
                    self._relationship(artifact_id, "PRODUCED_BY", tool_id),
                    self._relationship(evidence_id, "DERIVED_FROM", artifact_id),
                    self._relationship(evidence_id, "ABOUT", build_id),
                ]
            )
            records.tool_exports.append(
                KnowledgeExportToolsMixin._tool_export_descriptor(export, artifact_id)
            )

    @staticmethod
    def _tool_export_descriptor(export: ToolExport, artifact_id: str) -> dict[str, Any]:
        """Return the manifest-level descriptor used by downstream graph loaders."""
        assert export.output is not None
        return {
            "id": artifact_id,
            "artifact_key": export.artifact_key,
            "manifest": export.manifest_name,
            "path": export.output.path,
            "sha256": export.output.sha256,
            "size": export.output.size,
            "format": export.output.format,
            "max_output_bytes": export.max_output_bytes,
            "profile": export.profile,
            "authority": export.authority,
            "source_sha256": export.source_sha256,
            "tool": {
                "name": export.tool_name,
                "path": Path(export.tool_path).name,
                "sha256": export.tool_sha256,
                "version": export.tool_version,
            },
            "status": export.status,
        }
