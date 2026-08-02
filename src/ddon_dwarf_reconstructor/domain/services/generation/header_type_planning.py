"""Focused operations extracted from the public compatibility façade."""

from __future__ import annotations

import re

from ....infrastructure.logging import get_logger
from ...models.dwarf import ClassInfo

logger = get_logger(__name__)


class HeaderTypePlanningMixin:
    @staticmethod
    def _forward_declaration_name(declaration: str) -> str:
        """Extract the declared type name from a C++ forward declaration."""
        match = re.search(
            r"(?:class|struct|union)\s+([A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)\s*;",
            declaration,
        )
        return match.group(1) if match else declaration

    @staticmethod
    def _normalize_type_name(type_name: str) -> str:
        """Remove qualifiers and indirection from a referenced type name."""
        clean_name = type_name.strip()
        clean_name = re.sub(r"\b(?:const|volatile|restrict)\b\s*", "", clean_name)
        clean_name = re.sub(r"\b(?:class|struct|union|enum)\b\s*", "", clean_name)
        clean_name = re.sub(r"\s*[*&]+\s*$", "", clean_name)
        clean_name = re.sub(r"\s*\[[^\]]*\]\s*$", "", clean_name)
        return clean_name.strip()

    @classmethod
    def _collect_typedef_forward_declarations(
        cls,
        typedefs: dict[str, str],
    ) -> set[str]:
        """Collect opaque declarations required before typedef aliases."""
        declarations: set[str] = set()
        typedef_names = set(typedefs)

        for underlying_type in typedefs.values():
            clean_name = cls._normalize_type_name(underlying_type)
            if not clean_name or clean_name in typedef_names:
                continue

            candidate_match = re.match(r"([A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)", clean_name)
            if not candidate_match:
                continue

            candidate = candidate_match.group(1)
            if cls._is_builtin_type(clean_name) or candidate.startswith("std::"):
                continue

            if "<" in clean_name:
                declarations.add(f"template <typename T> class {candidate};")
            else:
                declarations.add(f"class {candidate};")

        return declarations

    @staticmethod
    def _is_builtin_type(type_name: str) -> bool:
        """Return whether a type expression contains only built-in type words."""
        builtin_words = {
            "bool",
            "char",
            "double",
            "float",
            "int",
            "long",
            "short",
            "signed",
            "unsigned",
            "void",
            "wchar_t",
            "size_t",
            "u8",
            "u16",
            "u32",
            "u64",
            "s8",
            "s16",
            "s32",
            "s64",
            "f32",
            "f64",
        }
        words = set(re.findall(r"[A-Za-z_]\w*", type_name))
        return bool(words) and words <= builtin_words

    @staticmethod
    def _referenced_class_name(type_name: str, class_names: set[str]) -> str | None:
        """Match a member's value type to a resolved class or template name."""
        clean_name = HeaderTypePlanningMixin._normalize_type_name(type_name)
        if clean_name in class_names:
            return clean_name
        template_match = re.match(r"([A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)\s*<", clean_name)
        candidate = (
            template_match.group(1) if template_match else re.split(r"[\s\[]", clean_name)[0]
        )
        if candidate in class_names:
            return candidate
        matching_specializations = sorted(
            class_name for class_name in class_names if class_name.startswith(f"{candidate}<")
        )
        return matching_specializations[0] if len(matching_specializations) == 1 else None

    @staticmethod
    def _iter_nested_classes(class_info: ClassInfo) -> list[ClassInfo]:
        """Return nested classes recursively in declaration order."""
        nested_classes: list[ClassInfo] = []
        for nested_class in class_info.nested_classes:
            nested_classes.append(nested_class)
            nested_classes.extend(HeaderTypePlanningMixin._iter_nested_classes(nested_class))
        return nested_classes
