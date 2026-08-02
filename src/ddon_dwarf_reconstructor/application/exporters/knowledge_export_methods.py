"""Focused knowledge-export operations for the compatibility façade."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ...domain.models.dwarf import ClassInfo, MethodInfo
from .knowledge_export_context import KnowledgeExportContext


class KnowledgeExportMethodsMixin:
    def _method_records(
        self: KnowledgeExportContext, type_id: str, class_info: ClassInfo
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Build declared-method records without assigning executable addresses."""
        nodes: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        for method in class_info.methods:
            parameters = [asdict(parameter) for parameter in method.parameters or []]
            qualified_name, signature, function_id = self._method_identity(class_info, method)
            nodes.append(
                self._node(
                    function_id,
                    "Function",
                    {
                        "qualified_name": qualified_name,
                        "signature": signature,
                        "name": method.name,
                        "return_type": method.return_type,
                        "return_type_offset": method.return_type_offset,
                        "parameters": parameters,
                        "is_virtual": method.is_virtual,
                        "vtable_index": method.vtable_index,
                        "source_revision": self.build_id,
                        "deterministic": True,
                    },
                )
            )
            relationships.append(self._relationship(type_id, "DECLARES_METHOD", function_id))
        return nodes, relationships

    def _reconstructed_cpp_records(
        self: KnowledgeExportContext,
        root_symbol: str,
        class_infos: dict[str, ClassInfo],
        source_node_id: str,
        cpp_path: Path,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Project the generated hierarchy header as explicitly partial C++."""
        content_sha256 = self._sha256_file(cpp_path)
        unit_id = f"reconstructed-cpp:{self.build_id}:{root_symbol}:{content_sha256[:16]}"
        logical_type_id = f"logical-type:{root_symbol}"
        source_files = sorted(
            {
                info.declaration_file
                for info in class_infos.values()
                if info.declaration_file is not None
            }
        )
        die_offsets = sorted(
            info.die_offset for info in class_infos.values() if info.die_offset is not None
        )
        node = self._node(
            unit_id,
            "ReconstructedCppUnit",
            {
                "name": root_symbol,
                "owner_name": root_symbol,
                "path": cpp_path.name,
                "content_sha256": content_sha256,
                "producer": self.PRODUCER,
                "producer_version": self.SCHEMA_VERSION,
                "source_revision": self.build_id,
                "source_files": source_files,
                "die_offsets": die_offsets,
                "completeness": "declarations_only",
                "diagnostics": ["METHOD_BODY_RECONSTRUCTION_NOT_IMPLEMENTED"],
                "deterministic": True,
            },
        )
        relationships = [
            self._relationship(unit_id, "ABOUT", logical_type_id),
            self._relationship(unit_id, "RECONSTRUCTED_FROM", source_node_id),
        ]
        for class_info in class_infos.values():
            for method in class_info.methods:
                _, _, function_id = self._method_identity(class_info, method)
                relationships.append(self._relationship(unit_id, "COVERS_FUNCTION", function_id))
        return [node], relationships

    def _method_identity(
        self: KnowledgeExportContext, class_info: ClassInfo, method: MethodInfo
    ) -> tuple[str, str, str]:
        """Return the qualified name, signature, and source-scoped DWARF function ID."""
        qualified_name = f"{class_info.name}::{method.name}"
        parameter_types = ",".join(parameter.type_name for parameter in method.parameters or [])
        signature = f"{method.return_type} {qualified_name}({parameter_types})"
        signature_hash = hashlib.sha256(signature.encode()).hexdigest()[:16]
        owner_identity = (
            f"{class_info.die_offset:x}"
            if class_info.die_offset is not None
            else hashlib.sha256(class_info.name.encode()).hexdigest()[:16]
        )
        function_id = f"function:{self.build_id}:dwarf:{owner_identity}:{signature_hash}"
        return qualified_name, signature, function_id
