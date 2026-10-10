"""Primitive, qualifier, classifier, and used-typedef edge coverage."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import MemberInfo, MethodInfo, ParameterInfo
from ddon_dwarf_reconstructor.domain.services.parsing.die_type_classifier import DIETypeClassifier
from ddon_dwarf_reconstructor.domain.services.parsing.type_resolver import LazyTypeResolver
from ddon_dwarf_reconstructor.domain.services.search_result import SearchResult, SearchStatus


class _RealDie:
    """Small concrete DIE graph for direct, offset-based type resolution."""

    def __init__(self, tag: str, offset: int, *, name: str | None = None) -> None:
        self.tag = tag
        self.offset = offset
        self.cu = SimpleNamespace(cu_offset=0x10)
        self.attributes: dict[str, Mock] = {}
        self._targets: dict[str, _RealDie | None] = {}
        self._children: list[_RealDie] = []
        if name is not None:
            self.attributes["DW_AT_name"] = Mock(value=name.encode())

    def get_DIE_from_attribute(self, name: str) -> _RealDie | None:  # noqa: N802
        return self._targets.get(name)

    def iter_children(self) -> list[_RealDie]:
        return self._children


def _real_link(source: _RealDie, name: str, target: _RealDie | None) -> None:
    source.attributes[name] = Mock(value=target.offset if target is not None else 0)
    source._targets[name] = target


def _die(tag: str, name: object | None = None, *, offset: int = 1) -> Mock:
    die = Mock(tag=tag, offset=offset)
    die.attributes = {}
    if name is not None:
        die.attributes["DW_AT_name"] = Mock(value=name)
    return die


@pytest.mark.unit
def test_classifier_distinguishes_named_forward_and_primitive_types() -> None:
    named = _die("DW_TAG_class_type", b"Thing")
    declaration = _die("DW_TAG_class_type", b"Thing")
    declaration.attributes["DW_AT_declaration"] = Mock(value=True)
    primitive = _die("DW_TAG_base_type", b"int")
    custom_base = _die("DW_TAG_base_type", b"CustomInt")
    pointer = _die("DW_TAG_pointer_type")
    enum = _die("DW_TAG_enumeration_type", b"Mode")

    assert DIETypeClassifier.is_named_type(named)
    assert DIETypeClassifier.is_forward_declarable(named)
    assert not DIETypeClassifier.requires_resolution(declaration)
    assert DIETypeClassifier.is_type_qualifier(pointer)
    assert DIETypeClassifier.is_primitive_type(primitive)
    assert not DIETypeClassifier.is_primitive_type(custom_base)
    assert DIETypeClassifier.get_type_name(named) == "Thing"
    assert DIETypeClassifier.get_type_name(pointer) is None
    assert not DIETypeClassifier.is_forward_declarable(enum)
    assert not DIETypeClassifier.requires_resolution(enum)


@pytest.mark.unit
def test_primitive_name_resolution_preserves_qualifiers_and_special_types() -> None:
    resolver = LazyTypeResolver(Mock(), Mock())
    base = _die("DW_TAG_base_type", b"int")
    assert resolver._get_primitive_base_type_name(base) == "int"

    for offset, (tag, expected) in enumerate(
        (
            ("DW_TAG_pointer_type", "int*"),
            ("DW_TAG_reference_type", "int&"),
            ("DW_TAG_const_type", "const int"),
            ("DW_TAG_volatile_type", "volatile int"),
        ),
        start=2,
    ):
        wrapper = _die(tag, offset=offset)
        wrapper.attributes["DW_AT_type"] = Mock(value=base.offset)
        wrapper.get_DIE_from_attribute.return_value = base
        assert resolver._get_primitive_base_type_name(wrapper) == expected

    member_pointer = _die("DW_TAG_ptr_to_member_type", offset=6)
    member_pointer.attributes["DW_AT_containing_type"] = Mock(value=base.offset)
    member_pointer.get_DIE_from_attribute.return_value = base
    assert resolver._get_primitive_base_type_name(member_pointer) == "unknown_type"

    subroutine_target = _die("DW_TAG_subroutine_type", offset=7)
    subroutine_target.iter_children.return_value = []
    subroutine_target.attributes["DW_AT_type"] = Mock(value=base.offset)
    subroutine_target.get_DIE_from_attribute.return_value = base
    owner = _die("DW_TAG_class_type", b"Owner", offset=8)
    member_func_ptr = _die("DW_TAG_ptr_to_member_type", offset=9)
    member_func_ptr.attributes["DW_AT_containing_type"] = Mock(value=base.offset)
    member_func_ptr.attributes["DW_AT_type"] = Mock(value=subroutine_target.offset)
    member_func_ptr.get_DIE_from_attribute.side_effect = lambda attr: (
        owner if attr == "DW_AT_containing_type" else subroutine_target
    )
    assert resolver._get_primitive_base_type_name(member_func_ptr) == "int (Owner::*)()"

    subroutine = _die("DW_TAG_subroutine_type", offset=10)
    subroutine.iter_children.return_value = []
    assert resolver._get_primitive_base_type_name(subroutine) == "void()"
    assert (
        resolver._get_primitive_base_type_name(_die("DW_TAG_unknown", offset=11)) == "unknown_type"
    )


@pytest.mark.unit
def test_direct_die_resolution_recovers_callable_parameters_and_qualifiers() -> None:
    resolver = LazyTypeResolver(Mock(), Mock())
    owner = _die("DW_TAG_class_type", b"Widget", offset=0x10)
    result_type = _die("DW_TAG_base_type", b"int", offset=0x11)
    pointee = _die("DW_TAG_pointer_type", offset=0x12)
    pointee.attributes["DW_AT_type"] = Mock(value=result_type.offset)
    pointee.get_DIE_from_attribute.return_value = result_type
    artificial_this = _die("DW_TAG_formal_parameter", offset=0x13)
    artificial_this.attributes["DW_AT_artificial"] = Mock(value=True)
    ordinary = _die("DW_TAG_formal_parameter", offset=0x14)
    ordinary.attributes["DW_AT_type"] = Mock(value=pointee.offset)
    ordinary.get_DIE_from_attribute.return_value = pointee
    subroutine = _die("DW_TAG_subroutine_type", offset=0x15)
    subroutine.attributes.update(
        {
            "DW_AT_type": Mock(value=result_type.offset),
            "DW_AT_const": Mock(value=True),
            "DW_AT_reference": Mock(value=True),
        }
    )
    subroutine.get_DIE_from_attribute.return_value = result_type
    subroutine.iter_children.return_value = [artificial_this, ordinary]
    member_pointer = _die("DW_TAG_ptr_to_member_type", offset=0x16)
    member_pointer.attributes.update(
        {
            "DW_AT_type": Mock(value=subroutine.offset),
            "DW_AT_containing_type": Mock(value=owner.offset),
        }
    )
    member_pointer.get_DIE_from_attribute.side_effect = lambda name: {
        "DW_AT_type": subroutine,
        "DW_AT_containing_type": owner,
    }[name]

    assert resolver.resolve_die_type(member_pointer) == "int (Widget::*)(int*) const &"


@pytest.mark.unit
def test_direct_real_die_resolution_preserves_alias_qualifier_and_nested_array_shape() -> None:
    resolver = LazyTypeResolver(Mock(), Mock())
    base = _RealDie("DW_TAG_class_type", 0, name="Texture")
    alias = _RealDie("DW_TAG_typedef", 1, name="TextureAlias")
    _real_link(alias, "DW_AT_type", base)
    pointer = _RealDie("DW_TAG_pointer_type", 2)
    _real_link(pointer, "DW_AT_type", alias)
    const_pointer = _RealDie("DW_TAG_const_type", 3)
    _real_link(const_pointer, "DW_AT_type", pointer)
    inner = _RealDie("DW_TAG_array_type", 4)
    _real_link(inner, "DW_AT_type", const_pointer)
    inner_range = _RealDie("DW_TAG_subrange_type", 5)
    inner_range.attributes["DW_AT_count"] = Mock(value=2)
    inner._children = [inner_range]
    outer = _RealDie("DW_TAG_array_type", 6)
    _real_link(outer, "DW_AT_type", inner)
    outer_range = _RealDie("DW_TAG_subrange_type", 7)
    outer_range.attributes["DW_AT_lower_bound"] = Mock(value=1)
    outer_range.attributes["DW_AT_upper_bound"] = Mock(value=3)
    outer._children = [outer_range]

    assert resolver.resolve_die_type(const_pointer) == "TextureAlias*const"
    assert resolver.resolve_die_type(outer) == "TextureAlias*const [3][2]"
    assert resolver.resolve_die_type(base) == "Texture"
    assert (0x10, 0) in resolver._type_name_cache


@pytest.mark.unit
def test_direct_real_die_resolution_keeps_unresolved_pointer_and_callable_object_fallback() -> None:
    resolver = LazyTypeResolver(Mock(), Mock())
    unresolved = _RealDie("DW_TAG_pointer_type", 0)
    assert resolver.resolve_die_type(unresolved) == "void*"

    result = _RealDie("DW_TAG_base_type", 1, name="int")
    implicit = _RealDie("DW_TAG_formal_parameter", 2)
    implicit.attributes["DW_AT_artificial"] = Mock(value=True)
    ordinary = _RealDie("DW_TAG_formal_parameter", 3)
    _real_link(ordinary, "DW_AT_type", unresolved)
    subroutine = _RealDie("DW_TAG_subroutine_type", 4)
    _real_link(subroutine, "DW_AT_type", result)
    subroutine._children = [implicit, ordinary]

    assert resolver.resolve_die_type(subroutine) == "int(void*)"


@pytest.mark.unit
def test_callable_object_pointer_attribute_excludes_implicit_object() -> None:
    resolver = LazyTypeResolver(Mock(), Mock())
    result = _RealDie("DW_TAG_base_type", 0x20, name="int")
    object_pointer = _RealDie("DW_TAG_formal_parameter", 0x21)
    _real_link(object_pointer, "DW_AT_type", _RealDie("DW_TAG_pointer_type", 0x22))
    object_pointer._targets["DW_AT_type"].attributes["DW_AT_type"] = Mock(value=result.offset)
    object_pointer._targets["DW_AT_type"]._targets["DW_AT_type"] = result
    ordinary = _RealDie("DW_TAG_formal_parameter", 0x23)
    _real_link(ordinary, "DW_AT_type", result)
    subroutine = _RealDie("DW_TAG_subroutine_type", 0x24)
    _real_link(subroutine, "DW_AT_type", result)
    _real_link(subroutine, "DW_AT_object_pointer", object_pointer)
    subroutine._children = [object_pointer, ordinary]

    assert resolver.resolve_die_type(subroutine) == "int(int)"


@pytest.mark.unit
def test_primitive_lookup_handles_exclusions_misses_and_typedefs() -> None:
    index = Mock()
    resolver = LazyTypeResolver(Mock(), index)
    assert resolver._resolve_primitive_typedef("int*") == "int"
    index.find_symbol_offset.return_value = None
    index.targeted_symbol_search.return_value = SearchResult(SearchStatus.NOT_FOUND, None, 0.01, 0)
    assert resolver._resolve_primitive_typedef("Alias") is None
    index.find_symbol_offset.return_value = 0x20
    index.get_die_by_offset.return_value = None
    assert resolver._resolve_primitive_typedef("Alias") is None

    base = _die("DW_TAG_base_type", b"int", offset=0x20)
    index.get_die_by_offset.return_value = base
    assert resolver._resolve_primitive_typedef("Alias") == "Alias"

    typedef = _die("DW_TAG_typedef", offset=0x21)
    index.find_symbol_offset.return_value = 0x21
    index.get_die_by_offset.return_value = typedef
    assert resolver._resolve_primitive_typedef("Alias") is None

    resolver.index = None
    assert resolver._resolve_primitive_typedef("Alias") is None


@pytest.mark.unit
def test_base_type_lookup_recovers_from_index_errors() -> None:
    index = Mock()
    resolver = LazyTypeResolver(Mock(), index)
    index.find_symbol_offset.side_effect = RuntimeError("bad index")

    assert resolver._get_base_type_from_typename("Alias") is None
    resolver.index = None
    assert resolver._get_base_type_from_typename("Alias") is None


@pytest.mark.unit
def test_used_typedef_collection_covers_unions_nested_structs_and_signatures() -> None:
    resolver = LazyTypeResolver(Mock(), Mock())
    resolver._is_known_aggregate_type = Mock(return_value=False)
    resolver._resolve_primitive_typedef = Mock(
        side_effect=lambda name: {"Alias": "int", "Other": "float"}.get(name)
    )
    member = MemberInfo("value", "Alias", type_offset=0x10)
    parameter = ParameterInfo("value", "Other", type_offset=0x20)
    method = MethodInfo("run", "void", parameters=[parameter])

    result = resolver.collect_used_typedefs([member], [method])

    assert result == {"Alias": "int", "Other": "float"}
