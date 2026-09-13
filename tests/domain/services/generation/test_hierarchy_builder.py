"""Unit tests for hierarchy builder search-mode behavior."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import ClassInfo
from ddon_dwarf_reconstructor.domain.services.generation.hierarchy_builder import HierarchyBuilder


@pytest.mark.unit
def test_build_full_hierarchy_uses_exhaustive_only_for_root() -> None:
    """Root lookup may stay exhaustive, but base-class lookups must force the fast path."""
    type_resolver = Mock()
    class_parser = Mock()
    class_parser.type_resolver = type_resolver
    dwarf_index = Mock()
    builder = HierarchyBuilder(class_parser, dwarf_index)

    root_inheritance = Mock()
    root_inheritance.tag = "DW_TAG_inheritance"
    root_die = Mock()
    root_die.iter_children.return_value = [root_inheritance]

    base_die = Mock()
    base_die.iter_children.return_value = []

    root_cu = Mock()
    base_cu = Mock()
    class_parser.find_class.side_effect = [(root_cu, root_die), (base_cu, base_die)]
    class_parser.parse_class_info.side_effect = [
        ClassInfo("rLayout", 528, [], [], [], [], [], []),
        ClassInfo("cResource", 112, [], [], [], [], [], []),
    ]
    type_resolver.resolve_type_name.side_effect = ["cResource"]

    builder.build_full_hierarchy("rLayout")

    assert class_parser.find_class.call_args_list[0].kwargs == {"exhaustive_override": None}
    assert class_parser.find_class.call_args_list[1].kwargs == {"exhaustive_override": False}


@pytest.mark.unit
def test_build_full_hierarchy_uses_approved_root_offset() -> None:
    """A build authority bypasses ambiguous name/cache selection for the root only."""
    class_parser = Mock()
    class_parser.type_resolver = Mock()
    builder = HierarchyBuilder(class_parser, Mock())
    root_cu = Mock()
    root_die = Mock()
    root_die.iter_children.return_value = []
    class_parser._find_die_and_cu_by_offset.return_value = (root_cu, root_die)
    class_parser.parse_class_info.return_value = ClassInfo(
        "rLayout", 528, [], [], [], [], [], [], die_offset=0x117EC452
    )

    classes, order = builder.build_full_hierarchy("rLayout", root_die_offset=0x117EC452)

    assert classes["rLayout"].die_offset == 0x117EC452
    assert order == ["rLayout"]
    class_parser._find_die_and_cu_by_offset.assert_called_once_with(0x117EC452)
    class_parser.find_class.assert_not_called()


@pytest.mark.unit
def test_dependency_resolution_forces_fast_lookup() -> None:
    """Dependency resolution must not inherit exhaustive root lookup behavior."""
    type_resolver = Mock()
    class_parser = Mock()
    class_parser.type_resolver = type_resolver
    dwarf_index = Mock()
    builder = HierarchyBuilder(class_parser, dwarf_index)

    resolved_die = Mock()
    resolved_die.tag = "DW_TAG_class_type"
    resolved_cu = Mock()
    class_parser._find_die_and_cu_by_offset.return_value = None
    class_parser.find_class.return_value = (resolved_cu, resolved_die)
    class_parser.parse_class_info.return_value = ClassInfo("cResource", 112, [], [], [], [], [], [])

    result = builder._try_resolve_type_by_offset(0x12E3F, "cResource")

    assert result is not None
    assert class_parser.find_class.call_args.kwargs == {"exhaustive_override": False}


@pytest.mark.unit
def test_dependency_resolution_prefers_exact_offset_over_name_lookup() -> None:
    """A referenced DIE must win over an unrelated same-name definition."""
    type_resolver = Mock()
    class_parser = Mock()
    class_parser.type_resolver = type_resolver
    dwarf_index = Mock()
    builder = HierarchyBuilder(class_parser, dwarf_index)

    exact_cu = Mock()
    exact_die = Mock(tag="DW_TAG_class_type", attributes={})
    unrelated_cu = Mock()
    unrelated_die = Mock(tag="DW_TAG_class_type", attributes={})
    class_parser._find_die_and_cu_by_offset.return_value = (exact_cu, exact_die)
    class_parser.find_class.return_value = (unrelated_cu, unrelated_die)
    exact_info = ClassInfo("cResource", 112, [], [], [], [], [], [], die_offset=0x12E3F)
    class_parser.parse_class_info.return_value = exact_info

    result = builder._try_resolve_type_by_offset(0x12E3F, "cResource")

    assert result is exact_info
    class_parser._find_die_and_cu_by_offset.assert_called_once_with(0x12E3F)
    class_parser.find_class.assert_not_called()


@pytest.mark.unit
def test_dependency_resolution_uses_exact_offset_for_unindexed_nested_type() -> None:
    """A nested definition may be resolvable only through its referenced DIE."""
    class_parser = Mock()
    class_parser.type_resolver = Mock()
    builder = HierarchyBuilder(class_parser, Mock())
    class_parser.find_class.return_value = None
    nested_cu = Mock()
    nested_die = Mock()
    nested_die.tag = "DW_TAG_structure_type"
    nested_die.attributes = {}
    class_parser._find_die_and_cu_by_offset.return_value = (nested_cu, nested_die)
    nested_info = ClassInfo("SetInfoBuffer", 64, [], [], [], [], [], [])
    class_parser.parse_class_info.return_value = nested_info

    result = builder._try_resolve_type_by_offset(0x117EC86E, "SetInfoBuffer")

    assert result is nested_info
    class_parser.find_class.assert_not_called()
    class_parser._find_die_and_cu_by_offset.assert_called_once_with(0x117EC86E)


@pytest.mark.unit
def test_direct_dependency_does_not_refind_itself_for_base_chain(mocker) -> None:
    """Known ClassInfo supplies direct bases without another global name search."""
    class_parser = Mock()
    class_parser.type_resolver = Mock()
    builder = HierarchyBuilder(class_parser, Mock())
    dependency_extractor = Mock()
    dependency_extractor.extract_dependencies.side_effect = [{0x1234}, set()]
    dependency_extractor.filter_resolvable_types.side_effect = lambda offsets: offsets
    dependency_extractor.get_type_name.return_value = "SetInfoBuffer"
    builder.dependency_extractor = dependency_extractor
    resolved = ClassInfo("SetInfoBuffer", 64, [], [], [], [], [], [])
    mocker.patch.object(builder, "_try_resolve_type_by_offset", return_value=resolved)

    classes = {"rLayout": ClassInfo("rLayout", 528, [], [], [], [], [], [])}
    builder._process_dependencies_offset_based(classes, classes, max_depth=10)

    class_parser.find_class.assert_not_called()


@pytest.mark.unit
@pytest.mark.performance
@pytest.mark.non_functional
def test_dependency_resolution_prefetches_one_sorted_offset_frontier(mocker) -> None:
    """Doris can hydrate the next dependency frontier in one bounded request."""
    class_parser = Mock()
    class_parser.type_resolver = Mock()
    dwarf_index = Mock()
    builder = HierarchyBuilder(class_parser, dwarf_index)
    dependency_extractor = Mock()
    dependency_extractor.extract_dependencies.side_effect = [{0x11, 0x10}, set()]
    dependency_extractor.filter_resolvable_types.side_effect = lambda offsets: offsets
    dependency_extractor.get_type_name.return_value = "Shared"
    builder.dependency_extractor = dependency_extractor
    shared = ClassInfo("Shared", 64, [], [], [], [], [], [])
    mocker.patch.object(builder, "_try_resolve_type_by_offset", return_value=shared)

    root = ClassInfo("Root", 8, [], [], [], [], [], [])
    classes = {"Root": root}
    builder._process_dependencies_offset_based(classes, classes, max_depth=10)

    dwarf_index.prefetch_dies.assert_called_once_with((0x10, 0x11))


@pytest.mark.unit
@pytest.mark.performance
@pytest.mark.non_functional
def test_dependency_resolution_reuses_prefetched_die_classification(mocker) -> None:
    """A prefetched frontier must not fall back to one DIE lookup per offset."""
    class_parser = Mock()
    class_parser.type_resolver = Mock()
    dwarf_index = Mock()
    builder = HierarchyBuilder(class_parser, dwarf_index)
    dependency_extractor = Mock()
    dependency_extractor.extract_dependencies.side_effect = [{0x10}, set()]
    builder.dependency_extractor = dependency_extractor
    dwarf_index.prefetch_dies.return_value = (
        SimpleNamespace(
            offset=0x10,
            tag="DW_TAG_class_type",
            attributes={"DW_AT_name": SimpleNamespace(value="Shared")},
        ),
    )
    shared = ClassInfo("Shared", 64, [], [], [], [], [], [])
    mocker.patch.object(builder, "_try_resolve_type_by_offset", return_value=shared)

    root = ClassInfo("Root", 8, [], [], [], [], [], [])
    classes = {"Root": root}
    builder._process_dependencies_offset_based(classes, classes, max_depth=10)

    dependency_extractor.filter_resolvable_types.assert_not_called()
    dependency_extractor.get_type_name.assert_not_called()


@pytest.mark.unit
@pytest.mark.regression
def test_identity_preserving_offset_resolution_satisfies_pending_base_name(mocker) -> None:
    """An offset-resolved class must prevent a second same-name global lookup."""
    class_parser = Mock()
    class_parser.type_resolver = Mock()
    dwarf_index = Mock()
    builder = HierarchyBuilder(class_parser, dwarf_index)
    dependency_extractor = Mock()
    dependency_extractor.extract_dependencies.side_effect = [{0x10}, set()]
    dependency_extractor.filter_resolvable_types.side_effect = lambda offsets: offsets
    dependency_extractor.get_type_name.return_value = "Shared"
    builder.dependency_extractor = dependency_extractor
    target_cu = SimpleNamespace(cu_offset=7)
    target_die = SimpleNamespace(offset=0x99, tag="DW_TAG_class_type", attributes={})
    class_parser._find_die_and_cu_by_offset.return_value = (target_cu, target_die)
    shared = ClassInfo("Shared", 64, [], [], [], [], [], [], cu_offset=7, die_offset=0x99)
    class_parser.parse_class_info.return_value = shared

    root = ClassInfo("Root", 8, [], [], ["Shared"], [], [], [], cu_offset=1, die_offset=2)
    classes = {"Root|1|2": root}
    builder._process_dependencies_offset_based(
        classes,
        classes,
        max_depth=10,
        preserve_definition_identity=True,
    )

    class_parser.find_class.assert_not_called()
    class_parser.parse_class_info.assert_called_once_with(target_cu, target_die)
    assert "Shared|7|153" in classes


@pytest.mark.unit
@pytest.mark.regression
def test_symbol_seed_parsing_reuses_exact_cu_die_definition(mocker) -> None:
    """Roots sharing an exact ancestor parse that ancestor only once."""
    class_parser = Mock()
    class_parser.type_resolver = Mock()
    builder = HierarchyBuilder(class_parser, Mock())

    root_a_cu = SimpleNamespace(cu_offset=1)
    root_a_die = SimpleNamespace(
        offset=0x10, tag="DW_TAG_class_type", attributes={}, iter_children=lambda: ()
    )
    root_b_cu = SimpleNamespace(cu_offset=2)
    root_b_die = SimpleNamespace(
        offset=0x20, tag="DW_TAG_class_type", attributes={}, iter_children=lambda: ()
    )
    shared_cu = SimpleNamespace(cu_offset=9)
    shared_die = SimpleNamespace(
        offset=0x99, tag="DW_TAG_class_type", attributes={}, iter_children=lambda: ()
    )
    definitions = {
        "RootA": (root_a_cu, root_a_die),
        "RootB": (root_b_cu, root_b_die),
        "Shared": (shared_cu, shared_die),
    }
    class_parser.find_class.side_effect = lambda name, **_kwargs: definitions.get(name)
    parsed = {
        0x10: ClassInfo("RootA", 8, [], [], ["Shared"], [], [], [], cu_offset=1, die_offset=0x10),
        0x20: ClassInfo("RootB", 8, [], [], ["Shared"], [], [], [], cu_offset=2, die_offset=0x20),
        0x99: ClassInfo("Shared", 64, [], [], [], [], [], [], cu_offset=9, die_offset=0x99),
    }
    class_parser.parse_class_info.side_effect = lambda _cu, die: parsed[die.offset]

    classes, order = builder._collect_symbol_hierarchy_seeds(("RootA", "RootB"))

    assert list(classes) == ["RootA|1|16", "Shared|9|153", "RootB|2|32"]
    assert order == ["Shared|9|153", "RootA|1|16", "RootB|2|32"]
    assert class_parser.parse_class_info.call_count == 3


@pytest.mark.unit
@pytest.mark.functional
def test_declaration_only_method_type_follows_named_complete_definition(mocker) -> None:
    """Method-signature closure must not stop at a forward MtDataReader DIE."""
    class_parser = Mock()
    class_parser.type_resolver = Mock()
    dwarf_index = Mock()
    builder = HierarchyBuilder(class_parser, dwarf_index)
    dependency_extractor = Mock()
    dependency_extractor.extract_dependencies.side_effect = [{0x1234}, set()]
    dependency_extractor.filter_resolvable_types.return_value = set()
    dependency_extractor.get_type_name.return_value = "MtDataReader"
    builder.dependency_extractor = dependency_extractor
    dwarf_index.get_die_by_offset.return_value = SimpleNamespace(
        tag="DW_TAG_class_type",
        attributes={"DW_AT_declaration": SimpleNamespace(value=True)},
    )
    resolved = ClassInfo("MtDataReader", 64, [], [], [], [], [], [], die_offset=0x1234)
    mocker.patch.object(builder, "_try_resolve_type_by_offset", return_value=resolved)

    classes = {"rAchievement": ClassInfo("rAchievement", 528, [], [], [], [], [], [])}
    builder._process_dependencies_offset_based(
        classes,
        classes,
        max_depth=10,
        include_method_signatures=True,
    )

    assert "MtDataReader" in classes


@pytest.mark.unit
@pytest.mark.regression
def test_identity_preserving_dependencies_reuse_one_parsed_source_target(mocker) -> None:
    """Distinct reference offsets must not reparse one exact CU/DIE definition."""
    class_parser = Mock()
    class_parser.type_resolver = Mock()
    builder = HierarchyBuilder(class_parser, Mock())
    dependency_extractor = Mock()
    dependency_extractor.extract_dependencies.side_effect = [{0x10, 0x11}, set()]
    dependency_extractor.filter_resolvable_types.side_effect = lambda offsets: offsets
    dependency_extractor.get_type_name.return_value = "Shared"
    builder.dependency_extractor = dependency_extractor

    target_cu = SimpleNamespace(cu_offset=7)
    target_die = SimpleNamespace(offset=0x99, tag="DW_TAG_class_type", attributes={})
    class_parser._find_die_and_cu_by_offset.side_effect = [
        (target_cu, target_die),
        (target_cu, target_die),
    ]
    shared = ClassInfo("Shared", 64, [], [], [], [], [], [], cu_offset=7, die_offset=0x99)
    class_parser.parse_class_info.return_value = shared

    root = ClassInfo("Root", 8, [], [], [], [], [], [], cu_offset=1, die_offset=2)
    classes = {"Root|1|2": root}
    builder._process_dependencies_offset_based(
        classes,
        classes,
        max_depth=10,
        preserve_definition_identity=True,
    )

    class_parser.parse_class_info.assert_called_once_with(target_cu, target_die)
    assert list(classes) == ["Root|1|2", "Shared|7|153"]


@pytest.mark.unit
@pytest.mark.regression
def test_symbol_union_preserves_definition_identity_during_dependency_resolution(mocker) -> None:
    builder = HierarchyBuilder(Mock(), Mock())
    root = ClassInfo("Root", 8, [], [], [], [], [], [], cu_offset=1, die_offset=2)
    mocker.patch.object(
        builder, "_collect_symbol_hierarchy_seeds", return_value=({"Root|1|2": root}, ["Root|1|2"])
    )
    process = mocker.patch.object(builder, "_process_dependencies_offset_based")

    builder.build_symbol_union_with_dependencies(("Root",))

    assert process.call_args.kwargs["preserve_definition_identity"] is True


@pytest.mark.unit
@pytest.mark.regression
def test_dependency_resolution_follows_specification_to_complete_definition() -> None:
    class_parser = Mock()
    class_parser.type_resolver = Mock()
    builder = HierarchyBuilder(class_parser, Mock())

    declaration = Mock(
        tag="DW_TAG_class_type",
        attributes={
            "DW_AT_declaration": SimpleNamespace(value=True),
            "DW_AT_specification": SimpleNamespace(value=0x99),
        },
    )
    complete = Mock(tag="DW_TAG_class_type", attributes={})
    complete.offset = 0x99
    declaration.get_DIE_from_attribute.return_value = complete
    declaration_cu = SimpleNamespace(cu_offset=1)
    complete_cu = SimpleNamespace(cu_offset=2)
    class_parser._find_die_and_cu_by_offset.side_effect = [
        (declaration_cu, declaration),
        (complete_cu, complete),
    ]
    expected = ClassInfo("MtDataReader", 64, [], [], [], [], [], [], die_offset=0x99)
    class_parser.parse_class_info.return_value = expected

    result = builder._try_resolve_type_by_offset(0x10, "MtDataReader")

    assert result is expected
    class_parser.parse_class_info.assert_called_once_with(complete_cu, complete)
    class_parser.find_class.assert_not_called()
