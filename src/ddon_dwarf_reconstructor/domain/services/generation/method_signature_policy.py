"""Shared low-level method-name and type-expression policy."""

from __future__ import annotations

import re

from ...models.dwarf import MethodInfo


def unqualify_type_expression(type_name: str) -> str:
    """Flatten unavailable enclosing scopes in generated expressions."""
    return re.sub(r"\b[A-Za-z_]\w*::(?=[A-Za-z_]\w*)", "", type_name)


def rendered_method_name(method_name: str) -> str:
    """Remove unavailable explicit template scopes from a method name."""
    if method_name.startswith("operator "):
        return "operator " + unqualify_type_expression(method_name[len("operator ") :])
    if method_name.startswith("operator"):
        return method_name
    return method_name.split("<", 1)[0].strip()


def is_conversion_operator(method_name: str) -> bool:
    """Return whether an operator name is a C++ conversion operator."""
    if not method_name.startswith("operator "):
        return False
    return method_name[len("operator ") :].strip() not in {
        "new",
        "new[]",
        "delete",
        "delete[]",
    }


def method_cv_ref_noexcept(method: MethodInfo) -> str:
    """Render the cv/ref/noexcept suffix shared by declarations and definitions."""
    suffix = ""
    if method.is_const:
        suffix += " const"
    if method.is_volatile:
        suffix += " volatile"
    if method.ref_qualifier:
        suffix += f" {method.ref_qualifier}"
    if method.is_noexcept:
        suffix += " noexcept"
    return suffix


def method_declaration_suffix(method: MethodInfo) -> str:
    """Render a complete declaration suffix, including special-member markers."""
    suffix = method_cv_ref_noexcept(method)
    if method.is_pure_virtual:
        return f"{suffix} = 0"
    if method.is_deleted:
        return f"{suffix} = delete"
    if method.is_defaulted:
        return f"{suffix} = default"
    return suffix


def operator_return_type(method: MethodInfo) -> str:
    """Render the return type used for non-conversion operator overloads."""
    return_type = unqualify_type_expression(method.return_type)
    return return_type if return_type and return_type != "void" else "void"


__all__ = [
    "is_conversion_operator",
    "method_cv_ref_noexcept",
    "method_declaration_suffix",
    "operator_return_type",
    "rendered_method_name",
    "unqualify_type_expression",
]
