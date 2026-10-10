"""Render retained alias declarations in their evidenced lexical scope."""

from collections.abc import Iterable

from ...models.dwarf import ClassInfo, MemberInfo, TypeReference


class AliasDeclarationError(ValueError):
    """Alias evidence cannot supply a unique, ordered C++ declaration."""


def ordered_aliases(aliases: Iterable[TypeReference]) -> tuple[TypeReference, ...]:
    """Order alias chains; incompatible observations and cycles fail explicitly."""
    by_name = _index_aliases_by_name(aliases)
    return _sort_alias_dependencies(by_name)


def _index_aliases_by_name(aliases: Iterable[TypeReference]) -> dict[str, TypeReference]:
    by_name: dict[str, TypeReference] = {}
    for alias in sorted(aliases, key=repr):
        _validate_alias(alias)
        prior = by_name.get(alias.name)
        if prior is not None and _signature(prior) != _signature(alias):
            raise AliasDeclarationError(f"conflicting alias declarations: {alias.name}")
        by_name[alias.name] = alias
    return by_name


def _sort_alias_dependencies(by_name: dict[str, TypeReference]) -> tuple[TypeReference, ...]:
    dependencies = {
        name: _alias_dependencies(alias) & by_name.keys()
        for name, alias in by_name.items()
        if alias.alias_target is not None
    }
    result: list[TypeReference] = []
    while dependencies:
        ready = sorted(name for name, needs in dependencies.items() if not needs)
        if not ready:
            raise AliasDeclarationError(
                f"cyclic alias declarations: {', '.join(sorted(dependencies))}"
            )
        for name in ready:
            result.append(by_name[name])
            del dependencies[name]
        for needs in dependencies.values():
            needs.difference_update(ready)
    return tuple(result)


def _alias_dependencies(alias: TypeReference) -> set[str]:
    if alias.alias_target is None:
        return set()
    return {
        ref.declarator.base_name
        for ref in alias.alias_target.references()
        if not (ref.is_anonymous and ref.name == alias.name)
    }


def _signature(alias: TypeReference) -> tuple[object, ...]:
    return (alias.alias_target.name if alias.alias_target else None, alias.declaration_access)


def _validate_alias(alias: TypeReference) -> None:
    if alias.kind != "DW_TAG_typedef" or alias.alias_target is None:
        raise AliasDeclarationError(f"missing alias target: {alias.name}")
    if alias.diagnostics or not alias.scope.complete:
        raise AliasDeclarationError(f"incomplete alias evidence: {alias.name}: {alias.diagnostics}")
    prefix = "::".join(part.name for part in alias.scope.components)
    local = alias.name.removeprefix(prefix + "::") if prefix else alias.name
    if not local.isidentifier():
        raise AliasDeclarationError(f"alias spelling disagrees with lexical scope: {alias.name}")


def _declaration(alias: TypeReference) -> str:
    assert alias.alias_target is not None
    prefix = "::".join(part.name for part in alias.scope.components)
    local = alias.name.removeprefix(prefix + "::") if prefix else alias.name
    return f"using {local} = {alias.alias_target.name};"


def member_alias_lines(info: ClassInfo, *, after_definitions: bool = False) -> list[str]:
    """Place each member alias before consumers, preserving declaration access."""
    lines: list[str] = []
    owner = info.qualified_name or info.name
    for alias in ordered_aliases(info.declared_aliases):
        if alias.scope.containing_aggregate != owner or alias.declaration_access is None:
            raise AliasDeclarationError(f"missing alias ownership/access: {alias.name}")
        if alias.alias_target is None:
            continue
        if alias.name == alias.alias_target.name:
            continue
        needs_definition = any(ref.is_anonymous for ref in alias.alias_target.references())
        if needs_definition != after_definitions:
            continue
        lines.extend([f"{alias.declaration_access}:", f"    {_declaration(alias)}"])
    return lines


def external_alias_lines(aliases: Iterable[TypeReference]) -> list[str]:
    """Publish namespace/global aliases; member aliases belong to their owner."""
    lines: list[str] = []
    for alias in ordered_aliases(aliases):
        if not alias.scope.namespace_only:
            raise AliasDeclarationError(f"alias requires enclosing aggregate: {alias.name}")
        if alias.alias_target is not None and alias.name == alias.alias_target.name:
            continue
        namespace = "::".join(part.name for part in alias.scope.components)
        declaration = _declaration(alias)
        lines.append(f"namespace {namespace} {{ {declaration} }}" if namespace else declaration)
    return lines


def referenced_namespace_aliases(
    infos: Iterable[ClassInfo], typedef_names: Iterable[str]
) -> dict[str, TypeReference]:
    """Retain lexical scope for used aliases flattened by legacy typedef lookup."""
    by_local: dict[str, TypeReference] = {}
    wanted = set(typedef_names)
    for info in infos:
        for reference in _class_references(info):
            for alias in reference.references():
                _add_namespace_alias(by_local, alias, wanted)
    return by_local


def _add_namespace_alias(
    by_local: dict[str, TypeReference], alias: TypeReference, wanted: set[str]
) -> None:
    if alias.kind != "DW_TAG_typedef" or not alias.scope.components:
        return
    if not alias.scope.complete or not alias.scope.namespace_only:
        return
    local = alias.name.rsplit("::", 1)[-1]
    if local not in wanted:
        return
    previous = by_local.get(local)
    if previous is not None and (
        previous.name != alias.name or _signature(previous) != _signature(alias)
    ):
        raise AliasDeclarationError(f"ambiguous alias scope or target: {local}")
    by_local[local] = alias


def _member_references(members: Iterable[MemberInfo]) -> Iterable[TypeReference]:
    for member in members:
        if member.type_reference is not None:
            yield member.type_reference


def _class_references(info: ClassInfo) -> Iterable[TypeReference]:
    yield from _member_references(info.members)
    for method in info.methods:
        if method.return_type_reference is not None:
            yield method.return_type_reference
        for parameter in method.parameters or ():
            if parameter.type_reference is not None:
                yield parameter.type_reference
    for struct in info.nested_structs:
        yield from _member_references(struct.members)
    for union in info.unions:
        yield from _member_references(union.members)
        for struct in union.nested_structs:
            yield from _member_references(struct.members)
    for nested in info.nested_classes:
        yield from _class_references(nested)


def scoped_typedef_line(line: str, alias: TypeReference | None) -> str:
    """Use the source alias target and namespace over a flattened legacy map."""
    if alias is None:
        return line
    _validate_alias(alias)
    if alias.alias_target is not None and alias.name == alias.alias_target.name:
        raise AliasDeclarationError(f"self-referential used alias: {alias.name}")
    namespace = "::".join(part.name for part in alias.scope.components)
    return f"namespace {namespace} {{ {_declaration(alias)} }}"
