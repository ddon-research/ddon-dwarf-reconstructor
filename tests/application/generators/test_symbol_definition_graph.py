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
