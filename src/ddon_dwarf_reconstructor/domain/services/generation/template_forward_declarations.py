"""Forward declarations derived from the same evidence plan as definitions."""

from ...models.dwarf import ClassInfo
from .rendering.operations import HeaderRenderingHost
from .template_families import plan_template_families


def planned_template_forwards(
    renderer: HeaderRenderingHost,
    declarations: set[str],
    infos: dict[str, ClassInfo],
    local_infos: dict[str, ClassInfo],
) -> set[str]:
    needed = {renderer._forward_declaration_name(declaration) for declaration in declarations}
    needed.update(
        renderer._unqualify_type_expression(info.template_rendering.primary)
        for info in local_infos.values()
        if info.template_rendering is not None
    )
    plans = {
        renderer._unqualify_type_expression(
            info.template_rendering.primary
        ): info.template_rendering
        for info in infos.values()
        if info.template_rendering is not None
    }
    result = {
        declaration
        for declaration in declarations
        if renderer._forward_declaration_name(declaration) not in plans
    }
    for primary in needed & plans.keys():
        plan = plans[primary]
        if plan.mode != "blocked":
            result.add(f"{plan.declaration} class {primary};")
    return result


def ensure_family_plans(infos: dict[str, ClassInfo]) -> dict[str, ClassInfo]:
    if any("<" in info.name and info.template_rendering is None for info in infos.values()):
        return plan_template_families(infos, {})[0]
    return infos
