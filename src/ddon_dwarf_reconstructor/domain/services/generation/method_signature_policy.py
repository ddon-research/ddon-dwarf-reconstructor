"""Shared low-level method-name and type-expression policy."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import replace
from itertools import combinations_with_replacement

from ...models.dwarf import MethodInfo, ParameterInfo, TypeReference, real_parameters
from ...models.dwarf.template_param_info import TemplateTypeParam
from ...models.dwarf.type_reference import DeclaratorLayer, TypeDeclarator


def _parameter_declarator(reference: TypeReference) -> TypeDeclarator:
    """Apply C++ parameter adjustment to source-proven declarator layers."""
    declarator = reference.declarator
    if not declarator.layers:
        return declarator
    outer, *inner = declarator.layers
    if outer.kind == "array" and not outer.qualifiers:
        return replace(declarator, layers=(DeclaratorLayer("pointer"), *inner))
    if outer.kind == "function" and not (outer.qualifiers or outer.ref_qualifier):
        return replace(declarator, layers=(DeclaratorLayer("pointer"), outer, *inner))
    return declarator


def _resolved_alias_reference(reference: TypeReference) -> TypeReference:
    """Follow complete typedef evidence, retaining ambiguous aliases as named types."""
    current = reference
    for _ in range(32):
        target = current.alias_target
        if (
            current.kind != "DW_TAG_typedef"
            or target is None
            or target.diagnostics
            or current.declarator.qualifiers
            or current.declarator.layers
        ):
            return current
        current = target
    return reference


def canonical_parameter_type(parameter: ParameterInfo) -> tuple[object, ...]:
    """Use rendered structural evidence; never guess alias equivalence from names."""
    reference = parameter.type_reference
    if isinstance(reference, TypeReference):
        return ("structured", _parameter_declarator(_resolved_alias_reference(reference)))
    spelling = " ".join(parameter.type_name.strip().split())
    if (
        parameter.cu_offset is not None
        and parameter.type_offset is not None
        and re.fullmatch(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", spelling)
    ):
        return ("terminal", parameter.cu_offset, parameter.type_offset)
    return ("spelling", spelling)


def unqualify_type_expression(type_name: str) -> str:
    """Flatten unavailable enclosing scopes in generated expressions."""
    return re.sub(r"\b[A-Za-z_]\w*::(?=[A-Za-z_]\w*)", "", type_name)


def rendered_method_name(method_name: str) -> str:
    """Remove unavailable explicit template scopes from a method name."""
    if method_name.startswith("operator "):
        return "operator " + unqualify_type_expression(method_name[len("operator ") :])
    if method_name.startswith("operator=") and "<" in method_name:
        # DWARF may spell an explicitly instantiated assignment operator as
        # ``operator=<32>``.  The specialization belongs to its parameter
        # types; it is not valid C++ syntax in the member name.
        return "operator="
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


def canonical_method_signature(
    method: MethodInfo,
    *,
    rendered_name: str | None = None,
    parameter_types: tuple[object, ...] | None = None,
) -> tuple[object, ...]:
    """Return full declaration evidence, distinct from overload identity."""
    parameters = (
        parameter_types
        if parameter_types is not None
        else tuple(
            canonical_parameter_type(parameter) for parameter in real_parameters(method.parameters)
        )
    )
    name = rendered_name if rendered_name is not None else method.name
    signature: tuple[object, ...] = (
        name,
        parameters,
        method.is_const,
        method.is_volatile,
        method.ref_qualifier or "",
        method.is_noexcept,
        method.is_static,
        method.is_virtual,
        method.access,
        method.is_constructor,
        method.is_destructor,
        method.is_pure_virtual,
        method.is_deleted,
        method.is_defaulted,
        method.is_noreturn,
    )
    result = method.return_type_reference
    if isinstance(result, TypeReference):
        result = _resolved_alias_reference(result)
    return_type = (
        ("structured", result.declarator, result.kind)
        if isinstance(result, TypeReference)
        else ("spelling", " ".join(method.return_type.strip().split()))
    )
    template_shape = tuple(
        ("type" if isinstance(parameter, TemplateTypeParam) else "value", parameter.name)
        for parameter in method.template_parameters
    )
    return (*signature, return_type, template_shape)


def method_overload_key(
    method: MethodInfo,
    *,
    rendered_name: str | None = None,
    parameter_types: tuple[object, ...] | None = None,
) -> tuple[object, ...]:
    """Identify name, explicit parameters and implicit-object cv/ref qualifiers.

    Return type, exception specification, staticness, access and virtualness
    cannot create an overload. Static/nonstatic and ref-qualified/unqualified
    clashes additionally require correspondence checks between these keys.
    """
    signature = canonical_method_signature(
        method, rendered_name=rendered_name, parameter_types=parameter_types
    )
    if not method.template_parameters:
        return signature[:5]
    parameters = signature[1]
    assert isinstance(parameters, tuple)
    return (signature[0], (("method_template", signature[-1]), *parameters), *signature[2:5])


class MethodDeclarationError(ValueError):
    """Incompatible observations would otherwise be hidden or emitted twice."""


def method_declaration_conflicts(
    methods: Iterable[MethodInfo],
    key: Callable[[MethodInfo], tuple[object, ...]] = method_overload_key,
) -> tuple[str, ...]:
    """Compare declaration evidence only among corresponding overloads.

    Group first by name and explicit parameters, then by object qualifiers;
    repeated CU observations do not require an all-method pairwise comparison.
    """
    groups: dict[tuple[object, ...], dict[tuple[object, ...], set[tuple[object, ...]]]] = {}
    for method in methods:
        overload = key(method)
        variants = groups.setdefault(overload[:2], {})
        object_key = (*overload[2:], method.is_static)
        variants.setdefault(object_key, set()).add(_declaration_for_key(method, overload))
    return tuple(
        repr(base)
        for base, variants in sorted(groups.items(), key=lambda item: repr(item[0]))
        if _conflicting_object_variants(variants)
    )


def _conflicting_object_variants(
    variants: dict[tuple[object, ...], set[tuple[object, ...]]],
) -> bool:
    for first, second in combinations_with_replacement(variants, 2):
        # C++17 [over.load] forbids mixing ref-qualified/unqualified members
        # with the same explicit parameters, even with different cv qualifiers.
        overlap = (
            first[3] or second[3] or bool(first[2]) != bool(second[2]) or first[:3] == second[:3]
        )
        if overlap and len(variants[first] | variants[second]) > 1:
            return True
    return False


def _declaration_for_key(method: MethodInfo, key: tuple[object, ...]) -> tuple[object, ...]:
    # Keep normalized name/parameter identity but all remaining source evidence.
    return (*key[:2], *canonical_method_signature(method)[2:])


def unique_method_declarations(
    methods: list[MethodInfo], key: Callable[[MethodInfo], tuple[object, ...]]
) -> list[MethodInfo]:
    """Deduplicate compatible observations; never discard conflicting returns."""
    conflicts = method_declaration_conflicts(methods, key)
    if conflicts:
        raise MethodDeclarationError("conflicting method declaration: " + "; ".join(conflicts))
    unique: dict[tuple[object, ...], MethodInfo] = {}
    for method in methods:
        unique.setdefault(_declaration_for_key(method, key(method)), method)
    return list(unique.values())


def operator_return_type(method: MethodInfo) -> str:
    """Render the return type used for non-conversion operator overloads."""
    return_type = unqualify_type_expression(method.return_type)
    return return_type if return_type and return_type != "void" else "void"


__all__ = [
    "canonical_parameter_type",
    "is_conversion_operator",
    "canonical_method_signature",
    "method_overload_key",
    "method_declaration_conflicts",
    "unique_method_declarations",
    "MethodDeclarationError",
    "method_cv_ref_noexcept",
    "method_declaration_suffix",
    "operator_return_type",
    "rendered_method_name",
    "unqualify_type_expression",
]
