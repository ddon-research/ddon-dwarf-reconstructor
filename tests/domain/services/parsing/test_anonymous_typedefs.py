"""Anonymous declaration identity survives typedef collection and rendering."""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.services.generation import HeaderRenderer
from ddon_dwarf_reconstructor.domain.services.parsing import ClassParser, LazyTypeResolver
from ddon_dwarf_reconstructor.domain.services.parsing.anonymous_typedefs import (
    AnonymousTypedefIndex,
)
from tests.support.type_graph import TypeAttribute, TypeDie

pytestmark = [pytest.mark.unit, pytest.mark.regression]


def _owner(tag: str, *, reverse: bool = False) -> TypeDie:
    owner = TypeDie("DW_TAG_structure_type", 10).named("Owner")
    target = TypeDie(tag, 0, parent=owner)
    first = TypeDie("DW_TAG_typedef", 20, parent=owner).named("First").link(target)
    second = TypeDie("DW_TAG_typedef", 30, parent=owner).named("Second").link(target)
    first.attributes["DW_AT_accessibility"] = TypeAttribute(3)
    member = TypeDie("DW_TAG_member", 40, parent=owner).named("value").link(second)
    member.attributes["DW_AT_data_member_location"] = TypeAttribute(0, "DW_FORM_data1")
    owner.children = [target, first, second, member]
    if reverse:
        owner.children.reverse()
    return owner


@pytest.mark.parametrize("kind", ["structure", "union", "class", "enumeration"])
@pytest.mark.parametrize("reverse", [False, True])
def test_all_aliases_to_anonymous_type_retain_one_definition(kind: str, reverse: bool) -> None:
    owner = _owner(f"DW_TAG_{kind}_type", reverse=reverse)
    parser = ClassParser(LazyTypeResolver(Mock(), Mock()), Mock())
    info = parser.parse_class_info(owner.cu, owner)
    aliases = {alias.name: alias for alias in info.declared_aliases}
    assert set(aliases) == {"Owner::First", "Owner::Second"}
    for alias in aliases.values():
        assert alias.alias_target.name == "Owner::First"
        assert alias.alias_target.die_offset == 0
        assert alias.alias_target.cu_offset == 0
        assert not alias.diagnostics
    header = HeaderRenderer(Mock()).generate_single_class_header(info, include_metadata=False)
    keyword = {"structure": "struct", "enumeration": "enum"}.get(kind, kind)
    assert f"typedef {keyword}\n" in header
    assert "} First;" in header
    assert "using Second = Owner::First;" in header
    assert "using First =" not in header
    assert f"{keyword} First;" not in header
    assert header.index("} First;") < header.index("using Second") < header.index("Second value;")
    assert "private:" in header[: header.index(f"typedef {keyword}")]


def test_anonymous_alias_choice_is_independent_of_resolution_order() -> None:
    owner = _owner("DW_TAG_structure_type", reverse=True)
    aliases = [child for child in owner.children if child.tag == "DW_TAG_typedef"]
    resolver = LazyTypeResolver(Mock(), Mock())
    references = [resolver.resolve_type_reference(alias) for alias in aliases]
    assert [reference.alias_target.name for reference in references] == ["Owner::First"] * 2
    assert [reference.name for reference in references] == ["Owner::Second", "Owner::First"]


def test_alias_index_reuses_parent_lookup_and_clears_with_resolver() -> None:
    owner = _owner("DW_TAG_structure_type")
    target, first, second, _ = owner.children
    calls = Mock(wraps=owner.iter_children)
    owner.iter_children = calls
    resolver = LazyTypeResolver(Mock(), Mock())
    assert resolver.anonymous_typedef_die(target) is first
    assert resolver.resolve_type_reference(second).alias_target.name == "Owner::First"
    assert resolver.anonymous_typedef_die(target) is first
    assert calls.call_count == 1
    resolver.clear_caches()
    assert resolver.anonymous_typedef_die(target) is first
    assert calls.call_count == 2


@pytest.mark.parametrize("tag", ["DW_TAG_compile_unit", "DW_TAG_namespace"])
def test_unavailable_reverse_alias_evidence_never_scans_whole_cu(tag: str) -> None:
    scope = TypeDie(tag, 10)
    scope.iter_children = Mock(side_effect=AssertionError("unbounded scope scan"))
    target = TypeDie("DW_TAG_structure_type", 0, parent=scope)
    alias = TypeDie("DW_TAG_typedef", 20, parent=scope).named("Alias").link(target)
    reference = LazyTypeResolver(Mock(), Mock()).resolve_type_reference(alias)
    assert len(reference.diagnostics) == 1
    assert reference.diagnostics[0].startswith("unnamed type declaration")
    assert AnonymousTypedefIndex().find(target) is None


def test_alias_index_rejects_excessive_scope_instead_of_returning_partial_choice() -> None:
    owner = _owner("DW_TAG_structure_type")
    target = owner.children[0]
    owner.children = [target] * 65537
    with pytest.raises(ValueError, match="bounded child lookup"):
        AnonymousTypedefIndex().find(target)


@pytest.mark.parametrize("kind", ["structure", "enumeration"])
def test_private_anonymous_typedef_does_not_change_later_named_type_access(kind: str) -> None:
    owner = _owner(f"DW_TAG_{kind}_type")
    visible = TypeDie(f"DW_TAG_{kind}_type", 50, parent=owner).named("Visible")
    if kind == "enumeration":
        visible.attributes["DW_AT_enum_class"] = TypeAttribute(0)
    owner.children.append(visible)
    info = ClassParser(LazyTypeResolver(Mock(), Mock()), Mock()).parse_class_info(owner.cu, owner)
    header = HeaderRenderer(Mock()).generate_single_class_header(info, include_metadata=False)
    keyword = "struct" if kind == "structure" else "enum"
    definition = header.index(f"{keyword} Visible\n")
    assert header.rfind("public:", 0, definition) > header.rfind("private:", 0, definition)
