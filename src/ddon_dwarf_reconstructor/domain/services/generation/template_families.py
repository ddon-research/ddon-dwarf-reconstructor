"""Conservative reconstruction of compatible, source-bound template instantiations."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import asdict, replace
from typing import Any, Literal

from ....core.content_hash import sha256_text
from ...models.dwarf import ClassInfo, TemplateTypeParam, TemplateValueParam
from ...models.dwarf.template_rendering import TemplateFamilyPlan, TemplateRendering
from .template_declarations import project_template


def plan_template_families(
    infos: Mapping[str, ClassInfo], origins: Mapping[str, set[str]]
) -> tuple[dict[str, ClassInfo], tuple[TemplateFamilyPlan, ...]]:
    """Plan each qualified family once; input definitions remain untouched."""
    families: dict[str, list[str]] = {}
    for key, info in sorted(infos.items()):
        name = info.qualified_name or info.name
        primary = template_primary(name)
        if primary is not None:
            families.setdefault(primary, []).append(key)
    rendered = dict(infos)
    plans = []
    for primary, keys in sorted(families.items()):
        plan, projections = _plan_family(primary, keys, infos, origins)
        plans.append(plan)
        rendered.update(projections)
    rendered, nested_plans = _plan_nested_families(rendered, origins)
    plans.extend(nested_plans)
    return rendered, tuple(plans)


def template_primary(name: str) -> str | None:
    """Find the template owned by the final scope, respecting nested arguments."""
    depth = 0
    scope_start = 0
    for index, character in enumerate(name):
        if character == "<":
            depth += 1
        elif character == ">":
            depth -= 1
        elif depth == 0 and name[index : index + 2] == "::":
            scope_start = index + 2
    opening = name.find("<", scope_start)
    return name[:opening] if opening > 0 and depth == 0 and name.endswith(">") else None


def _plan_nested_families(
    infos: dict[str, ClassInfo],
    origins: Mapping[str, set[str]],
) -> tuple[dict[str, ClassInfo], list[TemplateFamilyPlan]]:
    plans = []
    result = dict(infos)
    for owner, info in infos.items():
        if not info.nested_classes:
            continue
        children = {
            f"{owner}::nested:{index}": child for index, child in enumerate(info.nested_classes)
        }
        child_origins = {key: origins.get(owner, set()) for key in children}
        projected, nested = plan_template_families(children, child_origins)
        result[owner] = replace(info, nested_classes=list(projected.values()))
        plans.extend(nested)
    return result, plans


def parameter_declaration(info: ClassInfo) -> str | None:
    """Use child-DIE order and actual parameter kinds, without invented defaults."""
    if not info.template_parameters:
        return None
    parameters = []
    for index, parameter in enumerate(info.template_parameters):
        name = parameter.name or f"P{index}"
        if not re.fullmatch(r"[A-Za-z_]\w*", name):
            return None
        if isinstance(parameter, TemplateTypeParam):
            parameters.append(f"typename {name}")
        elif parameter.type_name not in {"", "unknown_type"}:
            parameters.append(f"{parameter.type_name} {name}")
        else:
            return None
    if len({item.rsplit(" ", 1)[-1] for item in parameters}) != len(parameters):
        return None
    return f"template <{', '.join(parameters)}>"


def _plan_family(
    primary: str,
    keys: list[str],
    infos: Mapping[str, ClassInfo],
    origins: Mapping[str, set[str]],
) -> tuple[TemplateFamilyPlan, dict[str, ClassInfo]]:
    declaration = parameter_declaration(infos[keys[0]]) or ""
    by_name = _specializations(keys, infos)
    diagnostics = _family_diagnostics(primary, keys, infos, by_name)
    mode: Literal["generic", "explicit", "blocked"] = "blocked" if diagnostics else "explicit"
    projections = {
        key: replace(infos[key], template_rendering=TemplateRendering(primary, declaration, mode))
        for key in keys
    }
    if mode != "blocked" and _generic_candidates(projections):
        mode = "generic"
    projections = _select_representatives(projections, by_name, mode, diagnostics)
    plan = TemplateFamilyPlan(
        primary,
        mode,
        declaration,
        tuple(keys),
        tuple(sorted({origin for key in keys for origin in origins.get(key, ())})),
        tuple((key, infos[key].cu_offset, infos[key].die_offset) for key in keys),
        tuple(diagnostics),
        tuple((key, sha256_text(_signature(infos[key]))) for key in keys),
    )
    return plan, projections


def _specializations(keys: list[str], infos: Mapping[str, ClassInfo]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for key in keys:
        info = infos[key]
        grouped.setdefault(info.qualified_name or info.name, []).append(key)
    return grouped


def _family_diagnostics(
    primary: str,
    keys: list[str],
    infos: Mapping[str, ClassInfo],
    by_name: dict[str, list[str]],
) -> list[str]:
    declarations = {parameter_declaration(infos[key]) for key in keys}
    diagnostics = []
    if None in declarations or len(declarations) != 1:
        diagnostics.append(f"unresolved template parameter signature: {primary}")
    diagnostics.extend(_unsupported_family_evidence(primary, keys, infos))
    for name, candidates in by_name.items():
        if len({_signature(infos[key]) for key in candidates}) > 1:
            diagnostics.append(f"conflicting template specialization: {name}")
    return diagnostics


def _unsupported_family_evidence(
    primary: str,
    keys: list[str],
    infos: Mapping[str, ClassInfo],
) -> list[str]:
    diagnostics = []
    if "<" in primary or any(infos[key].containing_type for key in keys):
        diagnostics.append(f"unresolved enclosing-scope template emission: {primary}")
    for key in keys:
        info = infos[key]
        if info.is_declaration or any(
            _missing_argument(parameter) for parameter in info.template_parameters
        ):
            diagnostics.append(
                f"unresolved template argument or definition: {info.qualified_name or info.name}"
            )
    return diagnostics


def _missing_argument(parameter: TemplateTypeParam | TemplateValueParam) -> bool:
    if isinstance(parameter, TemplateTypeParam):
        return parameter.argument_type in {None, "", "unknown_type"}
    return parameter.argument_value is None


def _select_representatives(
    projections: dict[str, ClassInfo],
    by_name: dict[str, list[str]],
    mode: Literal["generic", "explicit", "blocked"],
    diagnostics: list[str],
) -> dict[str, ClassInfo]:
    result = {}
    first = next(iter(projections))
    for key, info in projections.items():
        assert info.template_rendering is not None
        name = info.qualified_name or info.name
        representative = key == (first if mode == "generic" else by_name[name][0])
        rendering = replace(
            info.template_rendering,
            mode=mode,
            representative=representative,
            diagnostic="; ".join(diagnostics) or None,
        )
        result[key] = replace(info, template_rendering=rendering)
    return result


def _type_substitutions(info: ClassInfo) -> tuple[tuple[str, str], ...] | None:
    if any((info.nested_classes, info.nested_structs, info.unions, info.enums)):
        return None
    substitutions = []
    for index, parameter in enumerate(info.template_parameters):
        if isinstance(parameter, TemplateValueParam):
            return None  # Folded integer equality does not prove a dependent expression.
        argument = parameter.argument_type or ""
        if not re.fullmatch(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", argument):
            return None
        substitutions.append((argument, parameter.name or f"P{index}"))
    if len(dict(substitutions)) != len(substitutions):
        return None
    return tuple(substitutions)


def _generic_candidates(projections: dict[str, ClassInfo]) -> bool:
    """Require discriminating observations and identical normalized declarations."""
    arguments = set()
    normalized = set()
    layouts = set()
    for key, info in projections.items():
        substitutions = _type_substitutions(info)
        if not substitutions:
            return False
        assert info.template_rendering is not None
        projection = replace(
            info,
            template_rendering=replace(
                info.template_rendering, mode="generic", substitutions=substitutions
            ),
        )
        projections[key] = projection
        arguments.add(tuple(argument for argument, _name in substitutions))
        layouts.add(
            (info.byte_size, info.alignment, tuple(member.offset for member in info.members))
        )
        normalized.add(_signature(project_template(projection), generic=True))
    if len(arguments) < 2 or len(normalized) != 1 or len(layouts) != 1:
        return False
    return _arguments_discriminate(arguments)


def _arguments_discriminate(arguments: set[tuple[str, ...]]) -> bool:
    return all(
        len({args[index] for args in arguments}) > 1 for index in range(len(next(iter(arguments))))
    )


def _signature(info: ClassInfo, *, generic: bool = False) -> str:
    """Compare declaration semantics, excluding addresses and source-location metadata."""
    value = asdict(info)
    for field in (
        "name",
        "qualified_name",
        "cu_offset",
        "die_offset",
        "declaration_file",
        "declaration_line",
        "template_parameters",
        "template_rendering",
        "diagnostics",
        "packing_info",
        "containing_type",
    ):
        value.pop(field, None)
    if generic:
        # Concrete offsets remain in the original graph and family provenance.
        value["members"] = [dict(member, offset=None) for member in value["members"]]
    return json.dumps(_without_references(value), sort_keys=True, default=str)


def _without_references(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_references(item)
            for key, item in value.items()
            if key not in {"linkage_name", "is_declaration"}
            and not key.endswith("type_offset")
            and key not in {"die_offset", "cu_offset", "owner_die_offset", "argument_offset"}
        }
    if isinstance(value, list | tuple):
        return [_without_references(item) for item in value]
    return value
