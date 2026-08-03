"""Typed collaboration contract for knowledge-export stages."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from ...domain.models.disassembly import (
    OrbisDisassemblyReport,
    OrbisFunctionDisassembly,
)
from ...domain.models.dwarf import ClassInfo, MethodInfo
from ...domain.models.tool_evidence import ToolExport
from ...domain.ports.source_identity import SourceHashPort

if TYPE_CHECKING:
    from .knowledge_export_core import _OptionalRecords


class KnowledgeExportContext(Protocol):
    """State and operations shared by deterministic export stages."""

    elf_path: Path
    build_id: str
    requires_resolution: Callable[[int], bool] | None
    SCHEMA_VERSION: str
    PRODUCER: str
    source_hash: SourceHashPort

    def _ordered_names(
        self, class_infos: dict[str, ClassInfo], hierarchy_order: list[str]
    ) -> list[str]: ...

    def _base_records(
        self, class_infos: dict[str, ClassInfo]
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
        str,
        str,
        dict[str, str],
        dict[int, str],
    ]: ...

    def _validate_closure_references(
        self,
        class_infos: dict[str, ClassInfo],
        type_ids: dict[str, str],
        type_ids_by_offset: dict[int, str],
    ) -> list[str]: ...

    def _missing_field_references(
        self,
        class_name: str,
        class_info: ClassInfo,
        type_ids: dict[str, str],
        type_ids_by_offset: dict[int, str],
    ) -> list[str]: ...

    def _type_records(
        self,
        ordered_names: list[str],
        class_infos: dict[str, ClassInfo],
        type_ids: dict[str, str],
        type_ids_by_offset: dict[int, str],
        source_id: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]: ...

    def _type_record(
        self,
        name: str,
        class_info: ClassInfo,
        type_ids: dict[str, str],
        type_ids_by_offset: dict[int, str],
        source_id: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]: ...

    def _optional_records(
        self,
        root_symbol: str,
        class_infos: dict[str, ClassInfo],
        source_id: str,
        output_dir: Path,
        reconstructed_cpp: str | None,
        disassembly_report: OrbisDisassemblyReport | None,
        tool_exports: Sequence[ToolExport],
    ) -> _OptionalRecords: ...

    def _append_cpp_records(
        self,
        records: _OptionalRecords,
        root_symbol: str,
        class_infos: dict[str, ClassInfo],
        source_id: str,
        output_dir: Path,
        content: str,
    ) -> None: ...

    def _append_disassembly_records(
        self,
        records: _OptionalRecords,
        root_symbol: str,
        source_id: str,
        output_dir: Path,
        report: OrbisDisassemblyReport,
    ) -> None: ...

    def _append_tool_export_records(
        self,
        records: _OptionalRecords,
        root_symbol: str,
        source_id: str,
        exports: Sequence[ToolExport],
    ) -> None: ...

    def _write_bundle(
        self,
        root_symbol: str,
        root_authority: dict[str, Any] | None,
        output_dir: Path,
        nodes: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
        diagnostics: list[str],
        source_id: str,
        elf_sha256: str,
        optional: _OptionalRecords,
    ) -> Path: ...

    def _node(self, node_id: str, kind: str, properties: dict[str, Any]) -> dict[str, Any]: ...

    def _relationship(
        self,
        source_id: str,
        relationship_type: str,
        target_id: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def _type_id(self, class_info: ClassInfo, fallback_name: str) -> str: ...

    def _field_records(
        self,
        type_id: str,
        class_info: ClassInfo,
        type_ids: dict[str, str],
        type_ids_by_offset: dict[int, str],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]: ...

    def _method_records(
        self, type_id: str, class_info: ClassInfo
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]: ...

    def _inheritance_relationships(
        self, type_id: str, class_info: ClassInfo, type_ids: dict[str, str]
    ) -> list[dict[str, Any]]: ...

    def _resolve_reference_id(
        self,
        type_name: str,
        type_offset: int | None,
        type_ids: dict[str, str],
        type_ids_by_offset: dict[int, str],
    ) -> str | None: ...

    def _should_require_reference(self, type_name: str) -> bool: ...

    def _normalize_type_name(self, type_name: str) -> str: ...

    def _offset_requires_resolution(self, type_offset: int | None) -> bool: ...

    def _reconstructed_cpp_records(
        self,
        root_symbol: str,
        class_infos: dict[str, ClassInfo],
        source_node_id: str,
        cpp_path: Path,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]: ...

    def _sha256_file(self, path: Path) -> str: ...

    def _method_identity(
        self, class_info: ClassInfo, method: MethodInfo
    ) -> tuple[str, str, str]: ...

    def _disassembly_records(
        self,
        root_symbol: str,
        report: OrbisDisassemblyReport,
        elf_source_id: str,
    ) -> tuple[
        list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]
    ]: ...

    def _tool_node(self, tool_id: str, report: OrbisDisassemblyReport) -> dict[str, Any]: ...

    def _function_records(
        self,
        root_symbol: str,
        report: OrbisDisassemblyReport,
        function: OrbisFunctionDisassembly,
        tool_id: str,
        elf_source_id: str,
        selected_addresses: set[int],
        emitted_targets: set[int],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]: ...

    def _function_nodes(
        self,
        root_symbol: str,
        report: OrbisDisassemblyReport,
        function: OrbisFunctionDisassembly,
        evidence_id: str,
        unit_id: str,
    ) -> list[dict[str, Any]]: ...

    def _function_metrics(
        self, function: OrbisFunctionDisassembly
    ) -> tuple[int, int, list[str]]: ...

    def _function_relationships(
        self,
        root_symbol: str,
        function_id: str,
        unit_id: str,
        evidence_id: str,
        elf_source_id: str,
        tool_id: str,
    ) -> list[dict[str, Any]]: ...

    def _instruction_records(
        self,
        function: OrbisFunctionDisassembly,
        function_id: str,
        evidence_id: str,
        selected_addresses: set[int],
        emitted_targets: set[int],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]: ...

    def _orbis_function_id(self, address: int) -> str: ...

    def _orbis_function_node(self, address: int, name: str, size: int | None) -> dict[str, Any]: ...

    def _file_descriptor(self, path: Path) -> dict[str, Any]: ...

    def _write_jsonl(self, path: Path, records: list[dict[str, Any]]) -> None: ...

    def _deduplicate_nodes(self, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]: ...

    def _deduplicate_relationships(
        self, relationships: list[dict[str, Any]]
    ) -> list[dict[str, Any]]: ...

    def _manifest(
        self,
        root_symbol: str,
        root_authority: dict[str, Any] | None,
        diagnostics: list[str],
        source_artifacts: list[dict[str, Any]],
        nodes_path: Path,
        relationships_path: Path,
        optional: _OptionalRecords,
    ) -> dict[str, Any]: ...
