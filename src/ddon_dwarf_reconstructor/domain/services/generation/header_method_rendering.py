"""Method rendering operations."""

from __future__ import annotations

import re
from dataclasses import replace

from ....core.observability import get_logger
from ...models.dwarf import MethodInfo, ParameterInfo, TemplateTypeParam, real_parameters
from ...models.dwarf.type_reference import TypeReference
from .method_signature_policy import (
    canonical_parameter_type,
    is_conversion_operator,
    method_declaration_suffix,
    method_overload_key,
    operator_return_type,
    rendered_method_name,
    unique_method_declarations,
)
from .rendering.operations import HeaderRenderingHost
from .template_families import template_primary

logger = get_logger(__name__)


def _method_return_type(
    renderer: HeaderRenderingHost, method: MethodInfo, preserve_qualified: bool
) -> str:
    return (
        method.return_type
        if preserve_qualified
        else renderer._unqualify_type_expression(method.return_type)
    )


def _method_template_projection(method: MethodInfo) -> tuple[MethodInfo, str | None]:
    """Recover a type-parametric declaration only from matching DIE identities."""
    if len(method.template_parameters) != 1 or method.is_virtual:
        return method, None
    template = method.template_parameters[0]
    if not isinstance(template, TemplateTypeParam) or not re.fullmatch(
        r"[A-Za-z_]\w*", template.name
    ):
        return method, None
    if template.cu_offset is None or template.argument_offset is None:
        return method, None
    projected = []
    matched = False
    for parameter in method.parameters or ():
        replacement = _project_template_argument(parameter, template)
        projected.append(replacement or parameter)
        matched |= replacement is not None
    if not matched:
        return method, None
    return replace(method, parameters=projected), f"template <typename {template.name}>"


def _project_template_argument(
    parameter: ParameterInfo, template: TemplateTypeParam
) -> ParameterInfo | None:
    reference = parameter.type_reference
    if (
        parameter.is_artificial
        or parameter.cu_offset != template.cu_offset
        or parameter.type_offset != template.argument_offset
        or not isinstance(reference, TypeReference)
        or reference.alias_target is not None
        or reference.template_arguments
        or reference.declarator.base_name != template.argument_type
    ):
        return None
    new_reference = replace(
        reference, declarator=replace(reference.declarator, base_name=template.name)
    )
    return replace(parameter, type_name=new_reference.name, type_reference=new_reference)


class HeaderMethodRenderingService:
    def _generate_methods(
        self: HeaderRenderingHost,
        methods: list[MethodInfo],
        class_name: str,
        *,
        preserve_qualified: bool = False,
    ) -> list[str]:
        """Generate method declarations."""
        methods = self._deduplicate_rendered_methods(self._deduplicate_methods(methods))
        primary = template_primary(class_name) or class_name
        primary_name = self._unqualify_type_expression(primary)
        constructors, destructors, operators, other_methods = self._partition_methods(
            methods, class_name, primary_name
        )
        return [
            *self._render_constructors(constructors, primary_name, preserve_qualified),
            *self._render_destructors(destructors),
            *self._render_regular_methods(other_methods, preserve_qualified),
            *self._render_operators(operators, preserve_qualified),
        ]

    def _deduplicate_rendered_methods(
        self: HeaderRenderingHost, methods: list[MethodInfo]
    ) -> list[MethodInfo]:
        """Collapse aliases that render to one C++ signature despite DIE differences."""
        return unique_method_declarations(methods, self._rendered_method_key)

    @staticmethod
    def _is_constructor(method: MethodInfo, class_name: str, primary_name: str) -> bool:
        return method.is_constructor or method.name in {class_name, primary_name}

    def _partition_methods(
        self: HeaderRenderingHost,
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
        self: HeaderRenderingHost,
        methods: list[MethodInfo],
        class_name: str,
        preserve_qualified: bool = False,
    ) -> list[str]:
        return [
            f"    {class_name}({self._format_parameters(method, preserve_qualified)}){self._method_suffix(method)};"
            for method in methods
        ]

    def _render_destructors(self: HeaderRenderingHost, methods: list[MethodInfo]) -> list[str]:
        return [
            f"    {'virtual ' if method.is_virtual else ''}{self._rendered_method_name(method.name)}()"
            f"{self._method_suffix(method)};"
            for method in methods
        ]

    def _render_regular_methods(
        self: HeaderRenderingHost, methods: list[MethodInfo], preserve_qualified: bool = False
    ) -> list[str]:
        return [self._render_typed_method(method, preserve_qualified) for method in methods]

    def _render_typed_method(
        self: HeaderRenderingHost, method: MethodInfo, preserve_qualified: bool = False
    ) -> str:
        method, template_declaration = _method_template_projection(method)
        suffix, separator, initializer = self._method_suffix(method).partition(" = ")
        identifier = (
            f"{self._rendered_method_name(method.name)}"
            f"({self._format_parameters(method, preserve_qualified)}){suffix}"
        )
        reference = method.return_type_reference
        declaration = (
            reference.declarator.render(identifier)
            if isinstance(reference, TypeReference)
            else f"{_method_return_type(self, method, preserve_qualified)} {identifier}"
        )
        rendered = f"    {self._method_prefix(method)}{declaration}{separator}{initializer};"
        return f"    {template_declaration}\n{rendered}" if template_declaration else rendered

    def _render_operators(
        self: HeaderRenderingHost, methods: list[MethodInfo], preserve_qualified: bool = False
    ) -> list[str]:
        lines = []
        for method in methods:
            prefix = self._method_prefix(method)
            params = self._format_parameters(method, preserve_qualified)
            suffix = self._method_suffix(method)
            if self._is_conversion_operator(method.name):
                lines.append(
                    f"    {prefix}{self._rendered_method_name(method.name)}({params}){suffix};"
                )
            else:
                if isinstance(method.return_type_reference, TypeReference):
                    lines.append(self._render_typed_method(method, preserve_qualified))
                    continue
                return_type = (
                    method.return_type if preserve_qualified else operator_return_type(method)
                )
                lines.append(
                    f"    {prefix}{return_type} {self._rendered_method_name(method.name)}"
                    f"({params}){suffix};"
                )
        return lines

    @staticmethod
    def _rendered_method_name(method_name: str) -> str:
        """Remove recovered explicit template ids and unavailable enclosing scopes."""
        return rendered_method_name(method_name)

    @staticmethod
    def _deduplicate_methods(methods: list[MethodInfo]) -> list[MethodInfo]:
        """Remove duplicate DWARF method entries with identical C++ signatures."""
        return unique_method_declarations(methods, HeaderMethodRenderingService._source_method_key)

    @staticmethod
    def _source_method_key(method: MethodInfo) -> tuple[object, ...]:
        parameter_types = tuple(
            HeaderMethodRenderingService._canonical_parameter_type(parameter)
            for parameter in real_parameters(method.parameters)
        )
        return method_overload_key(
            method,
            rendered_name=HeaderMethodRenderingService._canonical_method_name(method.name),
            parameter_types=parameter_types,
        )

    def _rendered_method_key(self: HeaderRenderingHost, method: MethodInfo) -> tuple[object, ...]:
        """Keep all overload qualifiers while tolerating alias-only duplicates."""
        method, _template_declaration = _method_template_projection(method)
        parameter_types = tuple(
            self._canonical_parameter_type(parameter)
            for parameter in real_parameters(method.parameters)
        )
        return method_overload_key(
            method,
            rendered_name=self._canonical_method_name(self._rendered_method_name(method.name)),
            parameter_types=parameter_types,
        )

    @staticmethod
    def _canonical_parameter_type(parameter: ParameterInfo) -> tuple[object, ...]:
        return canonical_parameter_type(parameter)

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
        return is_conversion_operator(method_name)

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
        return method_declaration_suffix(method)

    def _format_parameters(
        self: HeaderRenderingHost, method: MethodInfo, preserve_qualified: bool = False
    ) -> str:
        """Format method parameters, filtering artificial ones."""
        if not method.parameters:
            return ""

        param_list = []
        for param in real_parameters(method.parameters):
            param_type = (
                param.type_name
                if preserve_qualified
                else self._unqualify_type_expression(param.type_name)
            )
            reference = param.type_reference
            param_str = (
                reference.declarator.render(param.name)
                if isinstance(reference, TypeReference)
                else self._parameter_declaration(param_type, param.name)
            )
            if param.default_value:
                param_str += f" = {param.default_value}"
            param_list.append(param_str)

        return ", ".join(param_list)

    @staticmethod
    def _parameter_declaration(type_name: str, name: str) -> str:
        """Insert a parameter name into ordinary and function-pointer declarators.

        A resolved pointer-to-member function is rendered as
        ``R (Owner::*)(Args...)``.  Appending the name (``... ) name``) is not
        valid C++; the declarator name belongs inside the ``(*...)`` portion.
        Keep this adjustment local to parameter rendering so the resolver can
        continue returning a reusable type expression for aliases and fields.
        """
        member_pointer = re.search(
            r"\(\s*([A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)\s*::\s*\*\s*\)",
            type_name,
        )
        if member_pointer is not None:
            replacement = f"({member_pointer.group(1)}::*{name})"
            rendered = (
                type_name[: member_pointer.start()]
                + replacement
                + type_name[member_pointer.end() :]
            )
            return rendered
        free_pointer = re.search(r"\(\s*\*\s*\)", type_name)
        if free_pointer is not None:
            replacement = f"(*{name})"
            return type_name[: free_pointer.start()] + replacement + type_name[free_pointer.end() :]
        return f"{type_name} {name}"
