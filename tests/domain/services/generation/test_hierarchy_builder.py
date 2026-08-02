"""Unit tests for hierarchy builder search-mode behavior."""

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
