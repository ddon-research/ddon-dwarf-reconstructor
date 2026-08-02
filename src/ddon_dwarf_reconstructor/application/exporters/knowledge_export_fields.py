"""Focused knowledge-export operations for the compatibility façade."""

from __future__ import annotations

import re
from typing import Any

from ...domain.models.dwarf import ClassInfo
from .knowledge_export_context import KnowledgeExportContext


class KnowledgeExportFieldsMixin:
    def _field_records(
        self: KnowledgeExportContext,
        type_id: str,
        class_info: ClassInfo,
        type_ids: dict[str, str],
        type_ids_by_offset: dict[int, str],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Build field and type-reference graph records for a class."""
        nodes: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        for index, member in enumerate(class_info.members):
            field_suffix = str(member.offset) if member.offset is not None else f"index-{index}"
            field_id = f"field:{type_id}:{field_suffix}:{member.name}"
            nodes.append(
                self._node(
                    field_id,
                    "Field",
                    {
                        "name": member.name,
                        "type_name": member.type_name,
                        "type_offset": member.type_offset,
                        "offset": member.offset,
                        "is_static": member.is_static,
                        "is_const": member.is_const,
                        "const_value": member.const_value,
                        "source_revision": self.build_id,
                        "deterministic": True,
                    },
                )
            )
            relationships.append(
                self._relationship(
                    type_id,
                    "HAS_FIELD",
                    field_id,
                )
            )
            reference_id = self._resolve_reference_id(
                member.type_name,
                member.type_offset,
                type_ids,
                type_ids_by_offset,
            )
            if reference_id:
                relationships.append(self._relationship(field_id, "REFERENCES_TYPE", reference_id))
            elif self._should_require_reference(member.type_name):
                logical_name = self._normalize_type_name(member.type_name)
                logical_id = f"logical-type:{logical_name}"
                nodes.append(self._node(logical_id, "LogicalType", {"name": logical_name}))
                relationships.append(
                    self._relationship(
                        field_id,
                        "REFERENCES_TYPE",
                        logical_id,
                        {
                            "resolution": "logical_only",
                            "type_offset": member.type_offset,
                        },
                    )
                )
        return nodes, relationships

    def _validate_closure_references(
        self: KnowledgeExportContext,
        class_infos: dict[str, ClassInfo],
        type_ids: dict[str, str],
        type_ids_by_offset: dict[int, str],
    ) -> list[str]:
        """Describe layout references lacking a concrete exported definition."""
        missing_references: list[str] = []
        for class_name, class_info in class_infos.items():
            missing_references.extend(
                self._missing_field_references(
                    class_name,
                    class_info,
                    type_ids,
                    type_ids_by_offset,
                )
            )
        return sorted(missing_references)

    def _missing_field_references(
        self: KnowledgeExportContext,
        class_name: str,
        class_info: ClassInfo,
        type_ids: dict[str, str],
        type_ids_by_offset: dict[int, str],
    ) -> list[str]:
        """Return resolved member references that are absent from the closure."""
        missing: list[str] = []
        for member in class_info.members:
            if member.type_offset is None:
                continue
            if (
                self._resolve_reference_id(
                    member.type_name,
                    member.type_offset,
                    type_ids,
                    type_ids_by_offset,
                )
                is not None
            ):
                continue
            if not self._offset_requires_resolution(member.type_offset):
                continue
            if not self._should_require_reference(member.type_name):
                continue
            missing.append(
                f"field {class_name}::{member.name} references unresolved type "
                f"{member.type_name} (offset {member.type_offset})"
            )
        return missing

    @staticmethod
    def _resolve_reference_id(
        type_name: str,
        type_offset: int | None,
        type_ids: dict[str, str],
        type_ids_by_offset: dict[int, str],
    ) -> str | None:
        """Resolve an exported type reference by offset first, then by normalized name."""
        if type_offset is not None:
            offset_match = type_ids_by_offset.get(type_offset)
            if offset_match is not None:
                return offset_match

        if type_name in type_ids:
            return type_ids[type_name]

        normalized_name = KnowledgeExportFieldsMixin._normalize_type_name(type_name)
        if normalized_name in type_ids:
            return type_ids[normalized_name]

        suffix_matches = [
            type_id
            for exported_name, type_id in type_ids.items()
            if exported_name.endswith(f"::{normalized_name}")
        ]
        if len(suffix_matches) == 1:
            return suffix_matches[0]

        return None

    @staticmethod
    def _normalize_type_name(type_name: str) -> str:
        """Strip common C++ qualifiers and indirection from a type display string."""
        normalized = re.sub(r"\b(const|volatile)\b", "", type_name)
        normalized = normalized.replace("*", " ").replace("&", " ")
        normalized = re.sub(r"\[[^\]]*\]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    @staticmethod
    def _should_require_reference(type_name: str) -> bool:
        """Return whether an unresolved display type should be treated as a missing closure reference."""
        normalized = KnowledgeExportFieldsMixin._normalize_type_name(type_name)
        if not normalized:
            return False

        builtin_tokens = {
            "bool",
            "char",
            "double",
            "f32",
            "f64",
            "float",
            "int",
            "long",
            "s16",
            "s32",
            "s64",
            "s8",
            "short",
            "signed",
            "size_t",
            "u16",
            "u32",
            "u64",
            "u8",
            "unsigned",
            "void",
        }
        tokens = {token for token in normalized.replace("::", " ").split(" ") if token}
        return not (tokens and tokens.issubset(builtin_tokens))

    def _offset_requires_resolution(self: KnowledgeExportContext, type_offset: int | None) -> bool:
        """Return whether a referenced DWARF offset must exist in the exported closure."""
        if type_offset is None:
            return False
        if self.requires_resolution is None:
            return True
        return self.requires_resolution(type_offset)

    def _inheritance_relationships(
        self: KnowledgeExportContext,
        type_id: str,
        class_info: ClassInfo,
        type_ids: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Build direct inheritance edges when the base is in the closure."""
        return [
            self._relationship(type_id, "INHERITS", type_ids[base_class])
            for base_class in class_info.base_classes
            if base_class in type_ids
        ]
