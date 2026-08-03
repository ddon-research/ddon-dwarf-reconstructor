"""Optional-artifact and bundle-writing stages for knowledge export."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ...domain.models.disassembly import OrbisDisassemblyReport
from ...domain.models.dwarf import ClassInfo
from ...domain.models.tool_evidence import ToolExport
from .knowledge_export_context import KnowledgeExportContext
from .knowledge_export_core import _OptionalRecords


class KnowledgeExportOutputMixin:
    def _optional_records(
        self: KnowledgeExportContext,
        root_symbol: str,
        class_infos: dict[str, ClassInfo],
        source_id: str,
        output_dir: Path,
        reconstructed_cpp: str | None,
        disassembly_report: OrbisDisassemblyReport | None,
        tool_exports: Sequence[ToolExport],
    ) -> _OptionalRecords:
        records = _OptionalRecords([], [], {}, None)
        if reconstructed_cpp is not None:
            self._append_cpp_records(
                records, root_symbol, class_infos, source_id, output_dir, reconstructed_cpp
            )
        if disassembly_report is not None:
            self._append_disassembly_records(
                records, root_symbol, source_id, output_dir, disassembly_report
            )
        if tool_exports:
            self._append_tool_export_records(records, root_symbol, source_id, tool_exports)
        return records

    def _append_cpp_records(
        self: KnowledgeExportContext,
        records: _OptionalRecords,
        root_symbol: str,
        class_infos: dict[str, ClassInfo],
        source_id: str,
        output_dir: Path,
        content: str,
    ) -> None:
        cpp_path = output_dir / "reconstructed.hpp"
        cpp_path.write_text(content, encoding="utf-8", newline="\n")
        nodes, relationships = self._reconstructed_cpp_records(
            root_symbol, class_infos, source_id, cpp_path
        )
        records.nodes.extend(nodes)
        records.relationships.extend(relationships)
        records.extra_files["reconstructed_cpp"] = self._file_descriptor(cpp_path)

    def _append_disassembly_records(
        self: KnowledgeExportContext,
        records: _OptionalRecords,
        root_symbol: str,
        source_id: str,
        output_dir: Path,
        report: OrbisDisassemblyReport,
    ) -> None:
        nodes, relationships, instructions, tool_source = self._disassembly_records(
            root_symbol, report, source_id
        )
        records.nodes.extend(nodes)
        records.relationships.extend(relationships)
        instructions_path = output_dir / "instructions.jsonl"
        self._write_jsonl(instructions_path, instructions)
        records.extra_files["instructions"] = self._file_descriptor(instructions_path)
        records.tool_source = tool_source
        records.disassembly_report = report

    def _write_bundle(
        self: KnowledgeExportContext,
        root_symbol: str,
        root_authority: dict[str, Any] | None,
        output_dir: Path,
        nodes: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
        diagnostics: list[str],
        source_id: str,
        elf_sha256: str,
        optional: _OptionalRecords,
    ) -> Path:
        nodes_path = output_dir / "nodes.jsonl"
        relationships_path = output_dir / "relationships.jsonl"
        self._write_jsonl(nodes_path, self._deduplicate_nodes(nodes))
        self._write_jsonl(relationships_path, self._deduplicate_relationships(relationships))
        source_artifacts = [
            {
                "id": source_id,
                "path": self.elf_path.name,
                "sha256": elf_sha256,
                "format": "ELF/DWARF",
            }
        ]
        if optional.tool_source is not None:
            source_artifacts.append(optional.tool_source)
        source_artifacts.extend(optional.tool_exports)
        manifest = self._manifest(
            root_symbol,
            root_authority,
            diagnostics,
            source_artifacts,
            nodes_path,
            relationships_path,
            optional,
        )
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return manifest_path

    def _manifest(
        self: KnowledgeExportContext,
        root_symbol: str,
        root_authority: dict[str, Any] | None,
        diagnostics: list[str],
        source_artifacts: list[dict[str, Any]],
        nodes_path: Path,
        relationships_path: Path,
        optional: _OptionalRecords,
    ) -> dict[str, Any]:
        manifest: dict[str, Any] = {
            "schema_version": self.SCHEMA_VERSION,
            "producer": self.PRODUCER,
            "build_id": self.build_id,
            "root_symbol": root_symbol,
            "source_revision": self.build_id,
            "completeness": "complete" if not diagnostics else "partial",
            "diagnostics": diagnostics,
            "source_artifacts": source_artifacts,
            "tool_exports": optional.tool_exports,
            "files": {
                "nodes": self._file_descriptor(nodes_path),
                "relationships": self._file_descriptor(relationships_path),
                **optional.extra_files,
            },
        }
        if optional.disassembly_report is not None:
            report = optional.disassembly_report
            manifest["disassembly"] = {
                "artifact_key": report.artifact_key,
                "flags": list(report.flags),
                "parser_version": report.parser_version,
                "tool": asdict(report.tool),
            }
        if root_authority is not None:
            manifest["root_authority"] = root_authority
        return manifest
