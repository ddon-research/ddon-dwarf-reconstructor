"""Canonical out-of-class method-definition signatures for reconstruction."""

from __future__ import annotations

from ...models.dwarf import MethodInfo, ParameterInfo, real_parameters
from .method_signature_policy import (
    is_conversion_operator,
    method_cv_ref_noexcept,
    operator_return_type,
    rendered_method_name,
    unqualify_type_expression,
)


class MethodDefinitionRenderingService:
    """Render definitions from the same method metadata used by headers."""

    @classmethod
    def render_signature(cls, method: MethodInfo) -> str:
        """Render the name/signature view used in implementation evidence."""
        parameters = cls._format_parameter_types(method)
        return f"{cls._method_name(method.name)}({parameters}){cls._cv_ref_noexcept(method)}"

    @classmethod
    def render(cls, owner: str, method: MethodInfo) -> str:
        """Return a declaration-compatible qualified definition signature."""
        name = cls._method_name(method.name)
        parameters = cls._format_parameters(method)
        suffix = cls._cv_ref_noexcept(method)
        class_name = owner.rsplit("::", 1)[-1].split("<", 1)[0]
        is_constructor = method.is_constructor or name in {class_name, owner}
        is_destructor = method.is_destructor or name.startswith("~")
        qualified_name = f"{owner}::{name}"
        if is_constructor or is_destructor or is_conversion_operator(name):
            return f"{qualified_name}({parameters}){suffix}"
        return_type = (
            operator_return_type(method)
            if name.startswith("operator")
            else unqualify_type_expression(method.return_type)
        )
        return f"{return_type} {qualified_name}({parameters}){suffix}"

    @staticmethod
    def _method_name(name: str) -> str:
        return rendered_method_name(name)

    @staticmethod
    def _format_parameters(method: MethodInfo) -> str:
        parameters = []
        for index, parameter in enumerate(
            MethodDefinitionRenderingService._real_parameters(method)
        ):
            type_name = unqualify_type_expression(parameter.type_name)
            name = parameter.name or f"param{index}"
            parameters.append(f"{type_name} {name}")
        return ", ".join(parameters)

    @staticmethod
    def _format_parameter_types(method: MethodInfo) -> str:
        return ", ".join(
            unqualify_type_expression(parameter.type_name)
            for parameter in MethodDefinitionRenderingService._real_parameters(method)
        )

    @staticmethod
    def _real_parameters(method: MethodInfo) -> tuple[ParameterInfo, ...]:
        return real_parameters(method.parameters)

    @staticmethod
    def _cv_ref_noexcept(method: MethodInfo) -> str:
        return method_cv_ref_noexcept(method)


__all__ = ["MethodDefinitionRenderingService"]
