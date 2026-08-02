"""Orchestration of deterministic knowledge-graph export stages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...domain.models.disassembly import OrbisDisassemblyReport
from ...domain.models.dwarf import ClassInfo
from .knowledge_export_context import KnowledgeExportContext


@dataclass
class _OptionalRecords:
    nodes: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    extra_files: dict[str, dict[str, Any]]
    tool_source: dict[str, Any] | None
    disassembly_report: OrbisDisassemblyReport | None = None


class KnowledgeExportCoreMixin:
    def export(
        self: KnowledgeExportContext,
        root_symbol: str,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        output_dir: Path,
        root_authority: dict[str, Any] | None = None,
        reconstructed_cpp: str | None = None,
        disassembly_report: OrbisDisassemblyReport | None = None,
    ) -> Path:
        """Write nodes, relationships, optional artifacts, and a manifest."""
        if not class_infos:
            raise ValueError("Cannot export an empty DWARF type closure")
        output_dir.mkdir(parents=True, exist_ok=True)
        ordered_names = self._ordered_names(class_infos, hierarchy_order)
        nodes, relationships, source_id, elf_sha256, type_ids, offsets = self._base_records(
            class_infos
        )
        diagnostics = self._validate_closure_references(class_infos, type_ids, offsets)
        type_nodes, type_relationships = self._type_records(
            ordered_names, class_infos, type_ids, offsets, source_id
        )
        nodes.extend(type_nodes)
        relationships.extend(type_relationships)
        optional = self._optional_records(
            root_symbol,
            class_infos,
            source_id,
            output_dir,
            reconstructed_cpp,
            disassembly_report,
        )
        nodes.extend(optional.nodes)
        relationships.extend(optional.relationships)
        return self._write_bundle(
            root_symbol,
            root_authority,
            output_dir,
            nodes,
            relationships,
            diagnostics,
            source_id,
            elf_sha256,
            optional,
        )

    def _base_records(
        self: KnowledgeExportContext, class_infos: dict[str, ClassInfo]
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
        str,
        str,
        dict[str, str],
        dict[int, str],
    ]:
        elf_sha256 = self.source_hash(self.elf_path)
        build_id = f"build:{self.build_id}"
        source_id = f"source:{self.build_id}:elf"
        nodes = [
            self._node(build_id, "Build", {"build_id": self.build_id, "deterministic": True}),
            self._node(
                source_id,
                "SourceArtifact",
                {
                    "path": self.elf_path.name,
                    "sha256": elf_sha256,
                    "format": "ELF/DWARF",
                    "deterministic": True,
                },
            ),
        ]
        relationships = [self._relationship(source_id, "BELONGS_TO", build_id)]
        type_ids = {
            name: self._type_id(class_info, name) for name, class_info in class_infos.items()
        }
        offsets = {
            class_info.die_offset: type_ids[name]
            for name, class_info in class_infos.items()
            if class_info.die_offset is not None
        }
        return nodes, relationships, source_id, elf_sha256, type_ids, offsets

    def _type_records(
        self: KnowledgeExportContext,
        ordered_names: list[str],
        class_infos: dict[str, ClassInfo],
        type_ids: dict[str, str],
        type_ids_by_offset: dict[int, str],
        source_id: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        nodes: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        for name in ordered_names:
            class_nodes, class_relationships = self._type_record(
                name, class_infos[name], type_ids, type_ids_by_offset, source_id
            )
            nodes.extend(class_nodes)
            relationships.extend(class_relationships)
        return nodes, relationships

    def _type_record(
        self: KnowledgeExportContext,
        name: str,
        class_info: ClassInfo,
        type_ids: dict[str, str],
        type_ids_by_offset: dict[int, str],
        source_id: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        type_id = type_ids[name]
        logical_id = f"logical-type:{name}"
        nodes = [
            self._node(
                type_id,
                "Type",
                {
                    "name": name,
                    "byte_size": class_info.byte_size,
                    "alignment": class_info.alignment,
                    "die_offset": class_info.die_offset,
                    "cu_offset": class_info.cu_offset,
                    "declaration_file": class_info.declaration_file,
                    "declaration_line": class_info.declaration_line,
                    "packing_info": class_info.packing_info or {},
                    "source_revision": self.build_id,
                    "deterministic": True,
                },
            ),
            self._node(logical_id, "LogicalType", {"name": name}),
        ]
        relationships = [
            self._relationship(type_id, "REPRESENTS", logical_id),
            self._relationship(type_id, "EVIDENCED_BY", source_id),
        ]
        field_nodes, field_relationships = self._field_records(
            type_id, class_info, type_ids, type_ids_by_offset
        )
        method_nodes, method_relationships = self._method_records(type_id, class_info)
        nodes.extend(field_nodes)
        nodes.extend(method_nodes)
        relationships.extend(field_relationships)
        relationships.extend(self._inheritance_relationships(type_id, class_info, type_ids))
        relationships.extend(method_relationships)
        return nodes, relationships
