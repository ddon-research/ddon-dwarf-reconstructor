"""Method rendering operations."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ....core.observability import get_logger
from ...models.dwarf import MethodInfo, ParameterInfo

if TYPE_CHECKING:
    from .header_generator_context import HeaderGeneratorContext

logger = get_logger(__name__)


class HeaderMethodRenderingMixin:
    def _generate_methods(
        self: HeaderGeneratorContext, methods: list[MethodInfo], class_name: str
    ) -> list[str]:
        """Generate method declarations."""
        methods = self._deduplicate_rendered_methods(self._deduplicate_methods(methods))
        template_info = self._template_rendering_info(class_name)
        primary_name = template_info[0] if template_info else class_name
        constructors, destructors, operators, other_methods = self._partition_methods(
            methods, class_name, primary_name
        )
        return [
            *self._render_constructors(constructors, primary_name),
            *self._render_destructors(destructors),
            *self._render_regular_methods(other_methods),
            *self._render_operators(operators),
        ]

    def _deduplicate_rendered_methods(
        self: HeaderGeneratorContext, methods: list[MethodInfo]
    ) -> list[MethodInfo]:
        """Collapse aliases that render to one C++ signature despite DIE differences."""
        unique_methods: list[MethodInfo] = []
        seen_signatures: set[tuple[object, ...]] = set()
        for method in methods:
            signature = (
                self._canonical_method_name(self._rendered_method_name(method.name)),
                tuple(
                    self._canonical_parameter_type(parameter)
                    for parameter in (method.parameters or [])
                    if parameter.name != "__artificial__"
                ),
                method.is_const,
                method.is_volatile,
                method.ref_qualifier,
            )
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            unique_methods.append(method)
        return unique_methods

    @staticmethod
    def _is_constructor(method: MethodInfo, class_name: str, primary_name: str) -> bool:
        return method.is_constructor or method.name in {class_name, primary_name}

    def _partition_methods(
        self: HeaderGeneratorContext,
        methods: list[MethodInfo],
        class_name: str,
        primary_name: str,
    ) -> tuple[list[MethodInfo], list[MethodInfo], list[MethodInfo], list[MethodInfo]]:
        constructors: list[MethodInfo] = []
        destructors: list[MethodInfo] = []
        operators: list[MethodInfo] = []
        other_methods: list[MethodInfo] = []
        for method in methods:
            if self._is_constructor(method, class_name, primary_name):
                constructors.append(method)
            elif method.is_destructor:
                destructors.append(method)
            elif method.name.startswith("operator"):
                operators.append(method)
            else:
                other_methods.append(method)
        return constructors, destructors, operators, other_methods

    def _render_constructors(
        self: HeaderGeneratorContext, methods: list[MethodInfo], class_name: str
    ) -> list[str]:
        return [
            f"    {class_name}({self._format_parameters(method)}){self._method_suffix(method)};"
            for method in methods
        ]

    def _render_destructors(self: HeaderGeneratorContext, methods: list[MethodInfo]) -> list[str]:
        return [
            f"    {'virtual ' if method.is_virtual else ''}{self._rendered_method_name(method.name)}()"
            f"{self._method_suffix(method)};"
            for method in methods
        ]

    def _render_regular_methods(
        self: HeaderGeneratorContext, methods: list[MethodInfo]
    ) -> list[str]:
        return [
            f"    {self._method_prefix(method)}{self._unqualify_type_expression(method.return_type)} "
            f"{self._rendered_method_name(method.name)}({self._format_parameters(method)}){self._method_suffix(method)};"
            for method in methods
        ]

    def _render_operators(self: HeaderGeneratorContext, methods: list[MethodInfo]) -> list[str]:
        lines = []
        for method in methods:
            prefix = self._method_prefix(method)
            params = self._format_parameters(method)
            suffix = self._method_suffix(method)
            if self._is_conversion_operator(method.name):
                lines.append(
                    f"    {prefix}{self._rendered_method_name(method.name)}({params}){suffix};"
                )
            else:
                return_type = (
                    self._unqualify_type_expression(method.return_type)
                    if method.return_type and method.return_type != "void"
                    else "void"
                )
                lines.append(
                    f"    {prefix}{return_type} {self._rendered_method_name(method.name)}"
                    f"({params}){suffix};"
                )
        return lines

    def _rendered_method_name(self: HeaderGeneratorContext, method_name: str) -> str:
        """Remove recovered explicit template ids and unavailable enclosing scopes."""
        if method_name.startswith("operator "):
            return "operator " + self._unqualify_type_expression(method_name[len("operator ") :])
        if method_name.startswith("operator"):
            return method_name
        return method_name.split("<", 1)[0].strip()

    @staticmethod
    def _deduplicate_methods(methods: list[MethodInfo]) -> list[MethodInfo]:
        """Remove duplicate DWARF method entries with identical C++ signatures."""
        unique_methods: list[MethodInfo] = []
        seen_signatures: set[tuple[object, ...]] = set()

        for method in methods:
            parameter_types = tuple(
                HeaderMethodRenderingMixin._canonical_parameter_type(parameter)
                for parameter in (method.parameters or [])
                if parameter.name != "__artificial__"
            )
            signature = (
                HeaderMethodRenderingMixin._canonical_method_name(method.name),
                parameter_types,
                method.is_static,
                method.is_const,
                method.is_volatile,
                method.ref_qualifier,
            )
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            unique_methods.append(method)

        return unique_methods

    @staticmethod
    def _canonical_parameter_type(parameter: ParameterInfo) -> tuple[object, ...]:
        """Normalize alias-only parameter names without losing declarator qualifiers."""
        type_name = re.sub(r"\s+", " ", parameter.type_name.strip())
        if parameter.type_offset is None:
            return ("name", type_name, (), "")

        qualifiers = tuple(re.findall(r"\b(?:const|volatile|restrict)\b", type_name))
        declarator = re.sub(r"\b(?:const|volatile|restrict)\b", "", type_name)
        declarator = re.sub(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", "", declarator)
        declarator = re.sub(r"\s+", "", declarator)
        canonical_simple = HeaderMethodRenderingMixin._canonical_simple_type(type_name)
        if canonical_simple is not None:
            return ("name", canonical_simple, qualifiers, declarator)
        return ("terminal", parameter.type_offset, qualifiers, declarator)

    @staticmethod
    def _canonical_simple_type(type_name: str) -> str | None:
        clean_name = re.sub(r"\b(?:const|volatile|restrict)\b\s*", "", type_name).strip()
        if HeaderMethodRenderingMixin._has_declarator(clean_name):
            return None
        words = clean_name.split()
        if not words or not HeaderMethodRenderingMixin._simple_words_are_identifiers(words):
            return None
        if not HeaderMethodRenderingMixin._simple_words_are_allowed(words):
            return None
        return HeaderMethodRenderingMixin._canonical_alias(words) or " ".join(words)

    @staticmethod
    def _has_declarator(type_name: str) -> bool:
        return any(token in type_name for token in ("*", "&", "[", "]", "(", ")"))

    @staticmethod
    def _simple_words_are_identifiers(words: list[str]) -> bool:
        return all(re.fullmatch(r"[A-Za-z_]\w*", word) for word in words)

    @staticmethod
    def _simple_words_are_allowed(words: list[str]) -> bool:
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
        }
        fixed_width_words = {
            "uint8_t",
            "uint16_t",
            "uint32_t",
            "uint64_t",
            "int8_t",
            "int16_t",
            "int32_t",
            "int64_t",
        }
        return all(
            word in builtin_words
            or re.fullmatch(r"(?:u|s|f)\d+", word) is not None
            or word in fixed_width_words
            for word in words
        )

    @staticmethod
    def _canonical_alias(words: list[str]) -> str | None:
        aliases = {
            "u8": "signed char",
            "s8": "signed char",
            "u16": "unsigned short",
            "s16": "short",
            "u32": "unsigned int",
            "s32": "int",
            "u64": "unsigned long",
            "s64": "long",
            "uint8_t": "signed char",
            "uint16_t": "unsigned short",
            "uint32_t": "unsigned int",
            "uint64_t": "unsigned long",
            "int8_t": "signed char",
            "int16_t": "short",
            "int32_t": "int",
            "int64_t": "long",
        }
        return aliases.get(words[0]) if len(words) == 1 else None

    @staticmethod
    def _canonical_method_name(method_name: str) -> str:
        """Normalize DWARF spacing so equivalent operator names deduplicate."""
        canonical_name = re.sub(r"\s+", " ", method_name.strip())
        if not canonical_name.startswith("operator"):
            canonical_name = canonical_name.split("<", 1)[0].strip()
            canonical_name = canonical_name.rsplit("::", 1)[-1]
        if canonical_name.startswith("operator "):
            target = canonical_name[len("operator ") :]
            target = re.sub(r"\s*([*&])\s*", r"\1", target)
            canonical_name = f"operator {target}"
        return canonical_name

    @staticmethod
    def _is_conversion_operator(method_name: str) -> bool:
        """Identify conversion operators whose declaration has no return type."""
        if not method_name.startswith("operator "):
            return False
        target = method_name[len("operator ") :].strip()
        return target not in {"new", "new[]", "delete", "delete[]"}

    @staticmethod
    def _method_prefix(method: MethodInfo) -> str:
        """Return static/virtual method declaration qualifiers."""
        qualifiers = []
        if method.is_noreturn:
            qualifiers.append("[[noreturn]]")
        if method.is_static:
            qualifiers.append("static")
        if method.is_virtual and not method.is_static:
            qualifiers.append("virtual")
        return " ".join(qualifiers) + (" " if qualifiers else "")

    @staticmethod
    def _method_suffix(method: MethodInfo) -> str:
        """Return cv/ref/noexcept and special method declaration suffixes."""
        suffix = ""
        if method.is_const:
            suffix += " const"
        if method.is_volatile:
            suffix += " volatile"
        if method.ref_qualifier:
            suffix += f" {method.ref_qualifier}"
        if method.is_noexcept:
            suffix += " noexcept"
        if method.is_pure_virtual:
            suffix += " = 0"
        elif method.is_deleted:
            suffix += " = delete"
        elif method.is_defaulted:
            suffix += " = default"
        return suffix

    def _format_parameters(self: HeaderGeneratorContext, method: MethodInfo) -> str:
        """Format method parameters, filtering artificial ones."""
        if not method.parameters:
            return ""

        param_list = []
        for param in method.parameters:
            # Skip artificial parameters (like 'this')
            if param.name == "__artificial__":
                continue

            param_type = self._unqualify_type_expression(param.type_name)
            param_str = f"{param_type} {param.name}"
            if param.default_value:
                param_str += f" = {param.default_value}"
            param_list.append(param_str)

        return ", ".join(param_list)
