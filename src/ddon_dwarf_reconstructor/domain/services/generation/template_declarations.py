"""Template substitutions restricted to type expressions, never rendered source lines."""

from __future__ import annotations

import re
from dataclasses import replace

from ...models.dwarf import ClassInfo, MemberInfo, ParameterInfo

_TYPE_TOKEN = re.compile(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*")


def substitute_type(expression: str, substitutions: tuple[tuple[str, str], ...]) -> str:
    """Replace complete qualified type tokens simultaneously before unqualification."""
    replacements = dict(substitutions)
    return _TYPE_TOKEN.sub(lambda match: replacements.get(match[0], match[0]), expression)


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
