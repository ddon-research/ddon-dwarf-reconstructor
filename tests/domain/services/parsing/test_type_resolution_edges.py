"""Primitive, qualifier, classifier, and used-typedef edge coverage."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import MemberInfo, MethodInfo, ParameterInfo
from ddon_dwarf_reconstructor.domain.services.parsing.die_type_classifier import DIETypeClassifier
from ddon_dwarf_reconstructor.domain.services.parsing.type_resolver import LazyTypeResolver
from ddon_dwarf_reconstructor.domain.services.search_result import SearchResult, SearchStatus


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

    for tag, expected in (
        ("DW_TAG_pointer_type", "int*"),
        ("DW_TAG_reference_type", "int&"),
        ("DW_TAG_const_type", "const int"),
        ("DW_TAG_volatile_type", "volatile int"),
    ):
        wrapper = _die(tag)
        wrapper.attributes["DW_AT_type"] = Mock(value=base.offset)
        wrapper.get_DIE_from_attribute.return_value = base
        assert resolver._get_primitive_base_type_name(wrapper) == expected

    member_pointer = _die("DW_TAG_ptr_to_member_type")
    member_pointer.attributes["DW_AT_containing_type"] = Mock(value=base.offset)
    member_pointer.get_DIE_from_attribute.return_value = base
    assert resolver._get_primitive_base_type_name(member_pointer) == "int"

    subroutine = _die("DW_TAG_subroutine_type")
    assert resolver._get_primitive_base_type_name(subroutine) == "void"
    assert resolver._get_primitive_base_type_name(_die("DW_TAG_unknown")) == "unknown_type"


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
