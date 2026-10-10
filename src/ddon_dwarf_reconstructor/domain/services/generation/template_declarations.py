"""Template substitutions restricted to type expressions, never rendered source lines."""

from __future__ import annotations

import re
from dataclasses import replace

from ...models.dwarf import ClassInfo, MemberInfo, ParameterInfo
from .scoped_declarations import scoped_declaration

_TYPE_TOKEN = re.compile(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*")
_ELABORATED = re.compile(r"\b(?:class|struct|union|enum)\s+")


def primary_declaration(info: ClassInfo) -> str | None:
    """Declare the planned primary in its proven scope with its evidenced signature."""
    plan = info.template_rendering
    if plan is None or plan.mode == "blocked" or not plan.declaration:
        return None
    declaration = scoped_declaration(plan.primary, info.kind, info.scope)
    if declaration is None:
        return None
    return declaration.replace(f"{info.kind} ", f"{plan.declaration} {info.kind} ", 1)


def nested_primary_declaration(info: ClassInfo, owner: ClassInfo) -> str | None:
    """Declare an evidenced member-template primary inside its actual owner.

    This publishes only a name and parameter signature. It does not turn an
    unsupported nested specialization into a definition.
    """
    plan = info.template_rendering
    if plan is None or not plan.declaration or plan.mode != "blocked":
        return None
    if not _scope_only_blockage(plan.diagnostic, plan.primary):
        return None
    local_name = _nested_primary_name(info, owner, plan.primary)
    if local_name is None or info.kind not in {"class", "struct", "union"}:
        return None
    return f"{plan.declaration} {info.kind} {local_name};"


def _scope_only_blockage(diagnostic: str | None, primary: str) -> bool:
    permitted = {
        f"unresolved enclosing-scope template emission: {primary}",
        f"unresolved template primary scope: {primary}",
    }
    return bool(diagnostic) and set(diagnostic.split("; ")) <= permitted


def _nested_primary_name(info: ClassInfo, owner: ClassInfo, primary: str) -> str | None:
    scope = info.scope
    owner_name = owner.qualified_name or owner.name
    if (
        scope is None
        or not scope.complete
        or scope.containing_aggregate != owner_name
        or info.containing_type != owner_name
        or not primary.startswith(owner_name + "::")
    ):
        return None
    local_name = primary.removeprefix(owner_name + "::")
    return local_name if re.fullmatch(r"[A-Za-z_]\w*", local_name) else None


def substitute_type(expression: str, substitutions: tuple[tuple[str, str], ...]) -> str:
    """Replace observed template arguments while preserving declarator syntax.

    Template arguments are recovered as complete type expressions, so a simple
    identifier-token replacement is insufficient for arguments such as
    ``ns::Value*`` or ``class ns::Value const``.  Replace the longest complete
    argument expression first, then fall back to token replacement for a bare
    qualified name.  The replacement is deliberately textual only within the
    type expression; rendered declarations and parameter names are never fed
    through this helper.
    """
    result = expression
    for source, target in sorted(substitutions, key=lambda item: len(item[0]), reverse=True):
        for variant in _source_variants(source):
            if not variant:
                continue
            pattern = _type_expression_pattern(variant)
            result = pattern.sub(target, result)
    return result


def _source_variants(source: str) -> tuple[str, ...]:
    compact = " ".join(source.strip().split())
    without_elaborated = _ELABORATED.sub("", compact).strip()
    values = [compact]
    if without_elaborated != compact:
        values.append(without_elaborated)
    return tuple(dict.fromkeys(values))


def _type_expression_pattern(source: str) -> re.Pattern[str]:
    """Build a boundary-aware pattern for one complete type atom."""
    escaped = re.escape(source)
    escaped = escaped.replace(r"\ ", r"\s+")
    escaped = escaped.replace(r"\*", r"\s*\*\s*")
    escaped = escaped.replace(r"\&", r"\s*&\s*")
    return re.compile(rf"(?<![A-Za-z0-9_:]){escaped}(?![A-Za-z0-9_])")


def project_template(info: ClassInfo) -> ClassInfo:
    """Make a rendering-only copy; retain all original concrete evidence separately."""
    plan = info.template_rendering
    if plan is None or plan.mode != "generic":
        return info
    substitutions = plan.substitutions
    methods = [
        replace(
            method,
            return_type=substitute_type(method.return_type, substitutions),
            return_type_offset=(
                method.return_type_offset
                if substitute_type(method.return_type, substitutions) == method.return_type
                else None
            ),
            parameters=[
                _project_typed_value(parameter, substitutions)
                for parameter in method.parameters or ()
            ],
        )
        for method in info.methods
    ]
    return replace(
        info,
        members=[
            replace(_project_typed_value(member, substitutions), offset=None)
            for member in info.members
        ],
        methods=methods,
        base_classes=[substitute_type(base, substitutions) for base in info.base_classes],
    )


def _project_typed_value[T: (MemberInfo, ParameterInfo)](
    value: T, substitutions: tuple[tuple[str, str], ...]
) -> T:
    type_name = substitute_type(value.type_name, substitutions)
    if type_name == value.type_name:
        return value
    return replace(value, type_name=type_name, type_offset=None, declared_type_offset=None)
