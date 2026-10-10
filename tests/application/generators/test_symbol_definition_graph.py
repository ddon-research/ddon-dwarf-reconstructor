"""Canonical symbol identity, reachability, and method-signature regressions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ddon_dwarf_reconstructor.application.generators.symbol_definition_graph import (
    build_canonical_definition_graph,
)
from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    MemberInfo,
    MethodInfo,
    ParameterInfo,
    TypeDeclarator,
    TypeReference,
)


def _class(
    name: str,
    *,
    cu: int,
    die: int,
    members: list[MemberInfo] | None = None,
    methods: list[MethodInfo] | None = None,
    qualified_name: str | None = None,
) -> ClassInfo:
    return ClassInfo(
        name=name,
        byte_size=8,
        members=members or [],
        methods=methods or [],
        base_classes=[],
        enums=[],
        nested_structs=[],
        unions=[],
        cu_offset=cu,
        die_offset=die,
        qualified_name=qualified_name or name,
    )


def _context(edges: dict[str, set[int]], names: dict[int, str]) -> SimpleNamespace:
    class Extractor:
        def extract_dependencies(
            self, info: ClassInfo, *, include_method_signatures: bool
        ) -> set[int]:
            del include_method_signatures
            return set(edges.get(info.name, set()))

        def get_type_name(self, offset: int) -> str | None:
            return names.get(offset)

    return SimpleNamespace(
        hierarchy_builder=SimpleNamespace(
            dependency_extractor=Extractor(),
        )
    )


@pytest.mark.unit
@pytest.mark.functional
def test_exact_identity_aliases_collapse_to_one_definition() -> None:
    root = _class("Root", cu=1, die=2)
    duplicate = _class("Root", cu=1, die=2)

    graph = build_canonical_definition_graph(
        _context({}, {}),
        ("Root",),
        {"Root": root, "Root-alias": duplicate},
        ["Root", "Root-alias"],
    )

    assert len(graph.class_infos) == 1
    canonical = next(iter(graph.class_infos))
    assert graph.aliases[canonical] == ("Root|1|2",)


@pytest.mark.unit
@pytest.mark.regression
@pytest.mark.parametrize("second_cu", [1, 2])
def test_alias_observations_survive_exact_and_cross_cu_definition_merging(second_cu) -> None:
    root = _class("Root", cu=1, die=2)
    duplicate = _class("Root", cu=second_cu, die=2)
    first_alias = TypeReference(TypeDeclarator("First"), die_offset=3, cu_offset=1)
    second_alias = TypeReference(TypeDeclarator("Second"), die_offset=4, cu_offset=second_cu)
    root.source_aliases = (first_alias,)
    duplicate.source_aliases = (second_alias,)
    graph = build_canonical_definition_graph(
        _context({}, {}), ("Root",), {"Root": root, "duplicate": duplicate}, ["Root"]
    )
    assert len(graph.class_infos) == 1
    assert set(next(iter(graph.class_infos.values())).source_aliases) == {first_alias, second_alias}
    assert not any("conflicting" in diagnostic for diagnostic in graph.diagnostics)


@pytest.mark.unit
@pytest.mark.functional
def test_same_content_across_compilation_units_merges() -> None:
    first = _class("Shared", cu=1, die=2)
    second = _class("Shared", cu=3, die=4)
    first.members = [MemberInfo("value", "int", type_offset=101, offset=0)]
    second.members = [MemberInfo("value", "int", type_offset=201, offset=0)]
    first.methods = [
        MethodInfo(
            name="read",
            return_type="int",
            return_type_offset=102,
            owner_die_offset=2,
            linkage_name="_ZN6Shared4readEv",
            parameters=[ParameterInfo("arg", "int", type_offset=103, die_offset=104)],
        )
    ]
    second.methods = [
        MethodInfo(
            name="read",
            return_type="int",
            return_type_offset=202,
            owner_die_offset=4,
            linkage_name="_ZN6Shared4readEv",
            parameters=[ParameterInfo("arg", "int", type_offset=203, die_offset=204)],
        )
    ]
    first.base_class_offsets = [105]
    second.base_class_offsets = [205]
    first.containing_type = "namespace_a"
    second.containing_type = "namespace_b"

    graph = build_canonical_definition_graph(
        _context({}, {}),
        ("Shared",),
        {"first": first, "second": second},
        ["first", "second"],
    )

    assert len(graph.class_infos) == 1
    canonical = next(iter(graph.class_infos))
    assert set(graph.aliases[canonical]) == {"Shared|1|2", "Shared|3|4"}


@pytest.mark.unit
@pytest.mark.regression
def test_same_layout_with_method_subset_has_one_cpp_definition() -> None:
    field = MemberInfo("value", "int", offset=0)
    shared = MethodInfo("identity", "void")
    full = _class(
        "MtMatrix", cu=1, die=2, members=[field], methods=[shared, MethodInfo("extra", "void")]
    )
    subset = _class("MtMatrix", cu=3, die=4, members=[field], methods=[shared])

    graph = build_canonical_definition_graph(
        _context({}, {}), ("full", "subset"), {"full": full, "subset": subset}, ["full", "subset"]
    )

    assert len(graph.class_infos) == 1
    assert len(next(iter(graph.class_infos.values())).methods) == 2
    assert set(next(iter(graph.aliases.values()))) == {"MtMatrix|1|2", "MtMatrix|3|4"}
    assert len(set(graph.root_keys.values())) == 1
    assert not any("conflicting complete definitions" in item for item in graph.diagnostics)


@pytest.mark.unit
@pytest.mark.regression
def test_same_layout_with_incompatible_method_declarations_stays_conflicted() -> None:
    field = MemberInfo("value", "int", offset=0)
    first = _class("MtMatrix", cu=1, die=2, members=[field], methods=[MethodInfo("read", "int")])
    second = _class("MtMatrix", cu=3, die=4, members=[field], methods=[MethodInfo("read", "float")])

    graph = build_canonical_definition_graph(
        _context({}, {}),
        ("first", "second"),
        {"first": first, "second": second},
        ["first", "second"],
    )

    assert len(graph.class_infos) == 2
    assert any("conflicting complete definitions" in item for item in graph.diagnostics)


@pytest.mark.unit
@pytest.mark.functional
def test_conflicting_definitions_remain_distinct_and_reachable() -> None:
    first = _class("First", cu=1, die=2, qualified_name="Shared")
    second = _class(
        "Second",
        cu=3,
        die=4,
        qualified_name="Shared",
        members=[MemberInfo(name="value", type_name="int", offset=0)],
    )

    graph = build_canonical_definition_graph(
        _context({}, {}),
        ("First", "Second"),
        {"First": first, "Second": second},
        ["First", "Second"],
    )

    assert len(graph.class_infos) == 2
    assert any("conflicting complete definitions for Shared" in item for item in graph.diagnostics)


@pytest.mark.unit
@pytest.mark.functional
def test_unreachable_definitions_are_dropped() -> None:
    root = _class("Root", cu=1, die=2)
    unreachable = _class("Unreachable", cu=3, die=4)

    graph = build_canonical_definition_graph(
        _context({}, {}),
        ("Root",),
        {"Root": root, "Unreachable": unreachable},
        ["Root", "Unreachable"],
    )

    assert [info.name for info in graph.class_infos.values()] == ["Root"]
    assert any("dropped 1 unreachable" in item for item in graph.diagnostics)


@pytest.mark.unit
@pytest.mark.regression
def test_embedded_nested_definitions_are_not_published_as_top_level_classes() -> None:
    root = _class("Outer", cu=1, die=2)
    nested = _class("Inner", cu=1, die=3, qualified_name="Outer::Inner")
    nested.containing_type = "Outer"
    root.nested_classes = [nested]

    graph = build_canonical_definition_graph(
        _context({"Outer": {3}}, {3: "Inner"}),
        ("Outer",),
        {"Outer": root, "Inner": nested},
        ["Outer", "Inner"],
    )

    assert [info.name for info in graph.class_infos.values()] == ["Outer"]
    assert any("collapsed 1 nested" in item for item in graph.diagnostics)


@pytest.mark.unit
@pytest.mark.regression
def test_method_signature_dependency_is_reachable_once() -> None:
    reader = _class("MtDataReader", cu=20, die=30)
    owner = _class(
        "rAchievement",
        cu=10,
        die=11,
        methods=[
            MethodInfo(
                name="loadData",
                return_type="void",
                parameters=[ParameterInfo("reader", "MtDataReader&", type_offset=30)],
            )
        ],
    )

    graph = build_canonical_definition_graph(
        _context({"rAchievement": {30}}, {30: "MtDataReader"}),
        ("rAchievement",),
        {"rAchievement": owner, "MtDataReader": reader},
        ["rAchievement", "MtDataReader"],
    )

    readers = [name for name, info in graph.class_infos.items() if info.name == "MtDataReader"]
    assert len(readers) == 1
    assert graph.origins[readers[0]] == {"rAchievement"}


@pytest.mark.unit
@pytest.mark.regression
def test_merged_cu_definition_keeps_source_offset_dependency_edge() -> None:
    owner = _class("cDraw", cu=1, die=1)
    nested = _class("SHADER_STATE", cu=1, die=15, qualified_name="cDraw::SHADER_STATE")
    nested.containing_type = "cDraw"
    nested.members = [MemberInfo("tag", "int", offset=0)]
    namespace_first = _class("SHADER_STATE", cu=1, die=10, qualified_name="nDraw::SHADER_STATE")
    namespace_second = _class("SHADER_STATE", cu=2, die=20, qualified_name="nDraw::SHADER_STATE")
    graph = build_canonical_definition_graph(
        _context({"cDraw": {20}}, {20: "SHADER_STATE"}),
        ("cDraw",),
        {
            "cDraw": owner,
            "nested": nested,
            "namespace_first": namespace_first,
            "namespace_second": namespace_second,
        },
        ["cDraw", "nested", "namespace_first", "namespace_second"],
    )

    published = [
        key
        for key, info in graph.class_infos.items()
        if info.qualified_name == "nDraw::SHADER_STATE"
    ]
    assert len(published) == 1
    assert graph.origins[published[0]] == {"cDraw"}
