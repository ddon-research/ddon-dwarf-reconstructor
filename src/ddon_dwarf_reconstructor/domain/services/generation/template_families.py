"""Conservative reconstruction of compatible, source-bound template instantiations."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import asdict, replace
from typing import Any, Literal

from ....core.content_hash import sha256_text
from ...models.dwarf import (
    ClassInfo,
    MethodInfo,
    TemplateTypeParam,
    TemplateValueParam,
)
from ...models.dwarf.template_rendering import TemplateFamilyPlan, TemplateRendering
from .alias_evidence import source_aliases
from .method_signature_policy import canonical_method_signature, method_declaration_conflicts
from .scoped_declarations import scoped_declaration
from .template_declarations import primary_declaration


def plan_template_families(
    infos: Mapping[str, ClassInfo], origins: Mapping[str, set[str]]
) -> tuple[dict[str, ClassInfo], tuple[TemplateFamilyPlan, ...]]:
    """Plan each qualified family once; input definitions remain untouched."""
    families = _family_members(infos)
    rendered = dict(infos)
    plans = []
    for primary, keys in sorted(families.items()):
        plan, projections = _plan_family(primary, keys, infos, origins)
        plans.append(plan)
        rendered.update(projections)
    rendered, nested_plans = _plan_nested_families(rendered, origins)
    plans.extend(nested_plans)
    return rendered, tuple(plans)


def _family_members(
    infos: Mapping[str, ClassInfo], *, include_primaries: bool = False
) -> dict[str, list[str]]:
    families: dict[str, list[str]] = {}
    for key, info in sorted(infos.items()):
        name = info.qualified_name or info.name
        primary = template_primary(name)
        if primary is None and include_primaries and info.template_parameters:
            primary = name
        if primary is not None:
            families.setdefault(primary, []).append(key)
    return families


def primary_declarations(infos: Mapping[str, ClassInfo]) -> tuple[set[str], tuple[str, ...]]:
    """Use the same primary policy for declaration-only namespace observations."""
    declarations: set[str] = set()
    diagnostics: list[str] = []
    for primary, keys in sorted(_family_members(infos, include_primaries=True).items()):
        errors = _primary_diagnostics(primary, keys, infos)
        if errors:
            diagnostics.extend(errors)
            continue
        info = replace(
            infos[keys[0]],
            template_rendering=TemplateRendering(
                primary, parameter_declaration(infos[keys[0]]) or "", "explicit"
            ),
        )
        declaration = primary_declaration(info)
        if declaration is not None:
            declarations.add(declaration)
    return declarations, tuple(diagnostics)


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
    projections = {
        key: replace(
            infos[key],
            template_rendering=TemplateRendering(primary, declaration, "explicit"),
        )
        for key in keys
    }
    mode: Literal["explicit", "blocked"] = "blocked" if diagnostics else "explicit"
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
        _method_provenance(keys, infos),
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
    diagnostics = _primary_diagnostics(primary, keys, infos)
    diagnostics.extend(_unsupported_family_evidence(primary, keys, infos))
    for name, candidates in by_name.items():
        if len({_signature(infos[key], include_methods=False) for key in candidates}) > 1:
            diagnostics.append(f"conflicting template specialization: {name}")
        conflicts = _method_conflicts([infos[key] for key in candidates])
        diagnostics.extend(
            f"conflicting method declaration: {name}::{conflict}" for conflict in conflicts
        )
    return diagnostics


def _parameter_signature(info: ClassInfo) -> tuple[str, ...] | None:
    """Parameter names do not change a primary's kind/type signature."""
    if parameter_declaration(info) is None:
        return None
    return tuple(
        "type"
        if isinstance(parameter, TemplateTypeParam)
        else " ".join(parameter.type_name.split())
        for parameter in info.template_parameters
    )


def _primary_diagnostics(
    primary: str, keys: list[str], infos: Mapping[str, ClassInfo]
) -> list[str]:
    declarations = {_parameter_signature(infos[key]) for key in keys}
    diagnostics = _primary_scope_diagnostics(primary, keys, infos)
    if None in declarations or len(declarations) != 1:
        diagnostics.append(f"unresolved template parameter signature: {primary}")
    return diagnostics


def _unsupported_family_evidence(
    primary: str,
    keys: list[str],
    infos: Mapping[str, ClassInfo],
) -> list[str]:
    diagnostics = []
    for key in keys:
        info = infos[key]
        if info.is_declaration or any(
            _missing_argument(parameter) for parameter in info.template_parameters
        ):
            diagnostics.append(
                f"unresolved template argument or definition: {info.qualified_name or info.name}"
            )
    return diagnostics


def _primary_scope_diagnostics(
    primary: str, keys: list[str], infos: Mapping[str, ClassInfo]
) -> list[str]:
    diagnostics = []
    if "<" in primary or any(infos[key].containing_type for key in keys):
        diagnostics.append(f"unresolved enclosing-scope template emission: {primary}")
    if any(scoped_declaration(primary, infos[key].kind, infos[key].scope) is None for key in keys):
        diagnostics.append(f"unresolved template primary scope: {primary}")
    if len({infos[key].kind for key in keys}) != 1:
        diagnostics.append(f"conflicting template aggregate kind: {primary}")
    return diagnostics


def _missing_argument(parameter: TemplateTypeParam | TemplateValueParam) -> bool:
    if isinstance(parameter, TemplateTypeParam):
        return parameter.argument_type in {None, "", "unknown_type"}
    return parameter.argument_value is None


def _method_conflicts(infos: list[ClassInfo]) -> tuple[str, ...]:
    """Find return/attribute disagreements for one source-level overload."""
    return method_declaration_conflicts(method for info in infos for method in info.methods)


def _method_provenance(
    keys: list[str], infos: Mapping[str, ClassInfo]
) -> tuple[tuple[str, tuple[tuple[str, int | None, int | None], ...]], ...]:
    """Retain the source DIE for every observed method in the family manifest."""
    evidence: dict[str, list[tuple[str, int | None, int | None]]] = {}
    for key in keys:
        info = infos[key]
        for method in info.methods:
            signature = repr(canonical_method_signature(method))
            evidence.setdefault(signature, []).append((key, method.cu_offset, method.die_offset))
    return tuple(
        (signature, tuple(sorted(records))) for signature, records in sorted(evidence.items())
    )


def _select_representatives(
    projections: dict[str, ClassInfo],
    by_name: dict[str, list[str]],
    mode: Literal["explicit", "blocked"],
    diagnostics: list[str],
) -> dict[str, ClassInfo]:
    result = {}
    methods = {
        name: _specialization_methods([projections[key] for key in keys])
        for name, keys in by_name.items()
    }
    for key, info in projections.items():
        assert info.template_rendering is not None
        name = info.qualified_name or info.name
        representative = key == by_name[name][0]
        rendering = replace(
            info.template_rendering,
            mode=mode,
            representative=representative,
            diagnostic="; ".join(diagnostics) or None,
        )
        updated_info = replace(info, template_rendering=rendering)
        if representative and mode != "blocked":
            updated_info = replace(
                updated_info,
                methods=methods[name],
                source_aliases=source_aliases(projections[item] for item in by_name[name]),
            )
        result[key] = updated_info
    return result


def _specialization_methods(infos: list[ClassInfo]) -> list[MethodInfo]:
    """Combine compatible observations only of the same concrete specialization."""
    methods: dict[tuple[object, ...], MethodInfo] = {}
    for info in infos:
        for method in info.methods:
            methods.setdefault(canonical_method_signature(method), method)
    return list(methods.values())


def _signature(info: ClassInfo, *, include_methods: bool = True) -> str:
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
        "base_class_offsets",
        "source_aliases",
    ):
        value.pop(field, None)
    if not include_methods:
        value.pop("methods", None)
    return json.dumps(_without_references(value), sort_keys=True, default=str)


def _without_references(value: Any) -> Any:
    if isinstance(value, dict):
        excluded = _signature_exclusions(value)
        return {
            key: _without_references(item)
            for key, item in value.items()
            if key not in excluded and not key.endswith("type_offset")
        }
    if isinstance(value, list | tuple):
        return [_without_references(item) for item in value]
    return value


def _signature_exclusions(value: dict[str, Any]) -> set[str]:
    excluded = {
        "linkage_name",
        "is_declaration",
        "die_offset",
        "cu_offset",
        "owner_die_offset",
        "argument_offset",
    }
    if value.get("type_reference") is not None:
        excluded.add("type_name")
    if value.get("return_type_reference") is not None:
        excluded.add("return_type")
    return excluded
