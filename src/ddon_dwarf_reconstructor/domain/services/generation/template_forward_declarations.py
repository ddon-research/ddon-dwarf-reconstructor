"""Forward declarations derived from the same evidence plan as definitions."""

from ...models.dwarf import ClassInfo
from .rendering.operations import HeaderRenderingHost
from .template_declarations import primary_declaration
from .template_families import plan_template_families, template_primary


def planned_template_forwards(
    renderer: HeaderRenderingHost,
    declarations: set[str],
    infos: dict[str, ClassInfo],
    local_infos: dict[str, ClassInfo],
) -> set[str]:
    needed = {renderer._forward_declaration_name(declaration) for declaration in declarations}
    needed.update(
        info.template_rendering.primary
        for info in local_infos.values()
        if info.template_rendering is not None
    )
    needed.update(_referenced_primaries(renderer, local_infos))
    plans = {
        info.template_rendering.primary: info
        for info in infos.values()
        if info.template_rendering is not None
    }
    result = {
        declaration
        for declaration in declarations
        if renderer._forward_declaration_name(declaration) not in plans
    }
    for primary in needed & plans.keys():
        declaration = primary_declaration(plans[primary])
        if declaration is not None:
            result.add(declaration)
    return result


def _referenced_primaries(renderer: HeaderRenderingHost, infos: dict[str, ClassInfo]) -> set[str]:
    needed: set[str] = set()
    for info in infos.values():
        for expression in _type_expressions(info):
            for specialization in renderer._template_expressions(expression):
                primary = template_primary(specialization)
                if primary is not None:
                    needed.add(primary)
    return needed


def _type_expressions(info: ClassInfo) -> list[str]:
    """Inspect hydrated evidence without repeating symbol or DIE lookups."""
    expressions = [*info.base_classes, *(member.type_name for member in info.members)]
    for method in info.methods:
        expressions.append(method.return_type)
        expressions.extend(parameter.type_name for parameter in method.parameters or ())
    expressions.extend(
        alias.alias_target.name for alias in info.declared_aliases if alias.alias_target is not None
    )
    for child in info.nested_classes:
        expressions.extend(_type_expressions(child))
    return expressions


def ensure_family_plans(infos: dict[str, ClassInfo]) -> dict[str, ClassInfo]:
    if any("<" in info.name and info.template_rendering is None for info in infos.values()):
        return plan_template_families(infos, {})[0]
    return infos
