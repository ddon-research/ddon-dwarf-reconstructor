"""Behavior tests for the production lazy type resolver."""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import MemberInfo, MethodInfo, ParameterInfo
from ddon_dwarf_reconstructor.domain.services.definition_selection import DefinitionCandidate
from ddon_dwarf_reconstructor.domain.services.parsing.type_resolver import LazyTypeResolver
from ddon_dwarf_reconstructor.domain.services.search_result import SearchResult, SearchStatus


@pytest.fixture
def index() -> Mock:
    return Mock()


@pytest.fixture
def resolver(index: Mock) -> LazyTypeResolver:
    return LazyTypeResolver(Mock(), index)


@pytest.mark.unit
def test_initialization_and_hierarchy_expansion(resolver: LazyTypeResolver) -> None:
    assert "u32" in resolver._primitive_typedefs
    assert "std::size_t" not in resolver._primitive_typedefs

    resolver.expand_primitive_search(full_hierarchy=True)

    assert "std::size_t" in resolver._primitive_typedefs
    assert "ptrdiff_t" in resolver._primitive_typedefs


@pytest.mark.unit
def test_named_type_resolution_is_cached(resolver: LazyTypeResolver) -> None:
    source = Mock(tag="DW_TAG_member")
    source.attributes = {"DW_AT_type": Mock()}
    target = Mock(tag="DW_TAG_base_type", offset=0x100)
    target.attributes = {"DW_AT_name": Mock(value=b"unsigned int")}
    source.get_DIE_from_attribute.return_value = target

    assert resolver.resolve_type_name(source) == "unsigned int"
    assert resolver.resolve_type_name(source) == "unsigned int"
    assert resolver.get_cache_stats()["type_name_cache_size"] == 1


@pytest.mark.unit
def test_pointer_resolution_preserves_qualifier(resolver: LazyTypeResolver) -> None:
    source = Mock(tag="DW_TAG_member")
    source.attributes = {"DW_AT_type": Mock()}
    pointer = Mock(tag="DW_TAG_pointer_type", offset=0x100)
    pointer.attributes = {"DW_AT_type": Mock()}
    base = Mock(tag="DW_TAG_base_type", offset=0x200)
    base.attributes = {"DW_AT_name": Mock(value=b"int")}
    source.get_DIE_from_attribute.return_value = pointer
    pointer.get_DIE_from_attribute.return_value = base

    assert resolver.resolve_type_name(source) == "int*"


@pytest.mark.unit
def test_find_typedef_uses_offset_cache(resolver: LazyTypeResolver, index: Mock) -> None:
    index.find_symbol_offset.return_value = 0x100
    typedef = Mock(tag="DW_TAG_typedef", offset=0x100)
    typedef.attributes = {"DW_AT_type": Mock()}
    base = Mock(tag="DW_TAG_base_type", offset=0x200)
    base.attributes = {"DW_AT_name": Mock(value=b"unsigned int")}
    typedef.get_DIE_from_attribute.return_value = base
    index.get_die_by_offset.return_value = typedef

    assert resolver.find_typedef("u32_alias") == ("u32_alias", "unsigned int")
    assert resolver.find_typedef("u32_alias") == ("u32_alias", "unsigned int")
    index.get_die_by_offset.assert_called_once_with(0x100)


@pytest.mark.unit
def test_find_typedef_falls_back_to_targeted_search(
    resolver: LazyTypeResolver, index: Mock
) -> None:
    index.find_symbol_offset.return_value = None
    index.targeted_symbol_search.return_value = SearchResult(
        SearchStatus.COMPLETE,
        DefinitionCandidate("alias", 0x10, 0x100, 100, True),
        0.01,
        1,
    )
    typedef = Mock(tag="DW_TAG_typedef", offset=0x100)
    typedef.attributes = {"DW_AT_type": Mock()}
    base = Mock(tag="DW_TAG_base_type", offset=0x200)
    base.attributes = {"DW_AT_name": Mock(value=b"int")}
    typedef.get_DIE_from_attribute.return_value = base
    index.get_die_by_offset.return_value = typedef

    assert resolver.find_typedef("alias") == ("alias", "int")
    index.find_symbol_offset.assert_called_once_with("alias")
    index.targeted_symbol_search.assert_called_once_with("alias")


@pytest.mark.unit
def test_typedef_cycles_terminate_and_clear_recursion_state(
    resolver: LazyTypeResolver, mocker
) -> None:
    mapping = {"A": ("A", "B"), "B": ("B", "A")}
    mocker.patch.object(resolver, "find_typedef", side_effect=mapping.get)

    assert resolver.resolve_typedef_chain("A") == "A"
    assert resolver._types_in_progress == set()


@pytest.mark.unit
def test_collect_typedefs_from_die_uses_lazy_resolution(resolver: LazyTypeResolver, mocker) -> None:
    member = Mock(tag="DW_TAG_member")
    class_die = Mock()
    class_die.iter_children.return_value = [member]
    mocker.patch.object(resolver, "resolve_type_name", return_value="Alias")
    mocker.patch.object(resolver, "find_typedef", return_value=("Alias", "int"))
    mocker.patch.object(resolver, "resolve_typedef_chain", return_value="int")

    assert resolver.collect_typedefs_from_die(class_die) == {"int"}


@pytest.mark.unit
def test_clear_caches_resets_all_runtime_state(resolver: LazyTypeResolver) -> None:
    resolver._typedef_cache[1] = "int"
    resolver._type_name_cache[2] = "float"
    resolver._typedef_chains["Alias"] = "int"
    resolver._types_in_progress.add("Alias")

    resolver.clear_caches()

    assert resolver.get_cache_stats() == {
        "typedef_cache_size": 0,
        "type_name_cache_size": 0,
        "typedef_chains_size": 0,
        "types_in_progress": 0,
        "primitive_typedefs": len(resolver._primitive_typedefs),
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    ("type_name", "expected"),
    [
        ("const unsigned int *", "unsigned int"),
        ("volatile Alias&", "Alias"),
        ("struct Example", "struct Example"),
        ("Value[4]", "Value"),
        ("const MT_CHAR*[5]", "MT_CHAR"),
    ],
)
def test_extract_base_type(resolver: LazyTypeResolver, type_name: str, expected: str) -> None:
    assert resolver._extract_base_type(type_name) == expected


@pytest.mark.unit
def test_collect_used_typedefs_skips_known_aggregate_method_types(
    resolver: LazyTypeResolver, index: Mock
) -> None:
    """Class signature types must not trigger a full typedef search."""
    aggregate = Mock(tag="DW_TAG_class_type")
    index.get_die_by_offset.return_value = aggregate
    index.find_symbol_offset.return_value = None

    method = MethodInfo(
        name="apply",
        return_type="InputLot*",
        return_type_offset=0x1234,
        parameters=[ParameterInfo("value", "OtherClass&", type_offset=0x5678)],
    )

    assert resolver.collect_used_typedefs([], [method]) == {}
    index.targeted_symbol_search.assert_not_called()


@pytest.mark.unit
def test_collect_used_typedefs_skips_known_aggregate_member_types(
    resolver: LazyTypeResolver, index: Mock
) -> None:
    """Aggregate fields must not fall back to a full-name CU search."""
    index.get_die_by_offset.return_value = Mock(tag="DW_TAG_structure_type")
    index.find_symbol_offset.return_value = None

    member = MemberInfo("layout", "stLayoutID", type_offset=0x74820)

    assert resolver.collect_used_typedefs([member], []) == {}
    index.targeted_symbol_search.assert_not_called()


@pytest.mark.unit
def test_collect_used_typedefs_resolves_alias_from_exact_declared_die() -> None:
    index = Mock()
    resolver = LazyTypeResolver(Mock(), index)
    typedef = Mock(tag="DW_TAG_typedef")
    index.get_die_by_offset.return_value = typedef
    resolver._resolve_primitive_die = Mock(return_value="DataFormat")
    member = MemberInfo(
        "format",
        "GPUFORMAT_TYPE",
        type_offset=0x1AEFF,
        declared_type_offset=0x1FA39,
    )

    assert resolver.collect_used_typedefs([member], []) == {"GPUFORMAT_TYPE": "DataFormat"}
    resolver._resolve_primitive_die.assert_called_once_with("GPUFORMAT_TYPE", typedef)
    index.targeted_symbol_search.assert_not_called()
