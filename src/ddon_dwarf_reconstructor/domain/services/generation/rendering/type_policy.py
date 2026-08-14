"""Repository-specific C++ type-expression policy."""

from __future__ import annotations

import re
from typing import ClassVar


class TypeExpressionPolicy:
    """Centralize the small, deterministic type vocabulary used by rendering."""

    _AMBIGUOUS_UNQUALIFIED_CLASS_NAMES: ClassVar[frozenset[str]] = frozenset({"Texture"})

    _BUILTIN_WORDS: ClassVar[frozenset[str]] = frozenset(
        {
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
            "uint8_t",
            "uint16_t",
            "uint32_t",
            "uint64_t",
            "int8_t",
            "int16_t",
            "int32_t",
            "int64_t",
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
    )
    _PRIMITIVE_NAMES: ClassVar[frozenset[str]] = frozenset(
        _BUILTIN_WORDS
        | {
            "unknown_type",
            "base_type",
            "subroutine_type",
            "pointer_type",
            "ptr_to_member_type",
            "class_type",
            "structure_type",
            "union_type",
            "enumeration_type",
        }
    )
    _INTEGRAL_WORDS: ClassVar[frozenset[str]] = frozenset(
        {
            "bool",
            "char",
            "short",
            "int",
            "long",
            "signed",
            "unsigned",
            "wchar_t",
            "u8",
            "u16",
            "u32",
            "u64",
            "s8",
            "s16",
            "s32",
            "s64",
            "int8_t",
            "int16_t",
            "int32_t",
            "int64_t",
            "uint8_t",
            "uint16_t",
            "uint32_t",
            "uint64_t",
        }
    )

    @classmethod
    def primitive_names(cls) -> set[str]:
        """Return a mutable copy for callers that build exclusion sets."""
        return set(cls._PRIMITIVE_NAMES)

    @classmethod
    def is_builtin(cls, type_name: str) -> bool:
        """Return whether an expression contains only known built-in words."""
        words = set(re.findall(r"[A-Za-z_]\w*", type_name))
        return bool(words) and words <= cls._BUILTIN_WORDS

    @classmethod
    def is_integral(cls, type_name: str) -> bool:
        """Return whether a type expression is integral for initializer policy."""
        clean_name = re.sub(r"\b(?:const|volatile|restrict)\b", "", type_name)
        words = set(re.findall(r"[A-Za-z_]\w*", clean_name))
        return bool(words) and words <= cls._INTEGRAL_WORDS

    @classmethod
    def preferred_forward_kind(cls, type_name: str) -> str | None:
        """Return the policy for a flattened ambiguous aggregate name.

        The PS4 source contains both ``nPrim::Texture`` (a structure) and
        ``nDraw::Texture``/``sce::Gnm::Texture`` (classes).  The renderer
        intentionally flattens qualified names, so the established byte
        contract chooses the class key for this collision.
        """
        return "class" if type_name in cls._AMBIGUOUS_UNQUALIFIED_CLASS_NAMES else None
