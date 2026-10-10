"""Symbol closure and ownership tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ddon_dwarf_reconstructor.application.generators.dwarf_symbol_generation import (
    SymbolExtractionService,
    _allocate_header_paths,
    _cycle_diagnostics,
    _generation_diagnostics,
    _header_groups,
    _header_names_for_group,
    _rendered_class_name,
    _validate_rendered_headers,
)
from ddon_dwarf_reconstructor.application.generators.generation_contracts import (
    SymbolExtractionRequest,
)
from ddon_dwarf_reconstructor.application.generators.symbol_definition_graph import (
    CanonicalDefinitionGraph,
)
from ddon_dwarf_reconstructor.application.generators.symbol_header_validation import (
    diagnostic_mentions_origin,
    root_statuses,
)
from ddon_dwarf_reconstructor.application.generators.symbol_method_diagnostics import (
    is_builtin_signature_type as _is_builtin_signature_type,
)
from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    MemberInfo,
    MethodInfo,
    ParameterInfo,
)
from ddon_dwarf_reconstructor.domain.services.generation.header_dependency_plan import (
    HeaderDependencyPlan,
    build_header_name_index,
)


@pytest.mark.unit
@pytest.mark.regression
def test_unscheduled_owner_cycle_has_explicit_witness() -> None:
    renderer = SimpleNamespace(cyclic_dependency_components=lambda *args, **kwargs: ())
    context = SimpleNamespace(header_renderer=renderer)
    plan = HeaderDependencyPlan(
        {"owner": frozenset({"consumer"}), "consumer": frozenset()},
        {},
        build_header_name_index({}),
        {"owner": frozenset(), "consumer": frozenset({"owner"})},
        (("consumer", "owner"),),
    )

    diagnostics = _cycle_diagnostics(context, {}, [], plan)
    assert diagnostics == (
        "cyclic lexical owner prerequisite is unscheduled: consumer requires owner owner; "
        "component: consumer, owner",
    )


@pytest.mark.unit
@pytest.mark.regression
def test_by_value_cycle_witness_keeps_template_commas_inside_identity() -> None:
    nested_key = "nDDOUtility::cArray<Owner::Node, 16>|1|2"
    owner_key = "Owner|1|1"
    renderer = SimpleNamespace(
        cyclic_dependency_components=lambda *args, **kwargs: ((nested_key, owner_key),)
    )
    context = SimpleNamespace(header_renderer=renderer)

    diagnostics = _cycle_diagnostics(context, {}, [])

    assert diagnostics == (
        f"unschedulable cyclic by-value dependency for symbol rendering: {nested_key}; {owner_key}",
    )
    assert diagnostic_mentions_origin(diagnostics[0], nested_key, _class(nested_key, 2, "Array.h"))
    assert diagnostic_mentions_origin(diagnostics[0], owner_key, _class("Owner", 1, "Owner.h"))
    assert not diagnostic_mentions_origin(
        diagnostics[0], "Other|1|3", _class("Other", 3, "Other.h")
    )


@pytest.mark.unit
@pytest.mark.regression
def test_ambiguous_complete_base_diagnostic_reaches_symbol_result() -> None:
    renderer = SimpleNamespace(cyclic_dependency_components=lambda *args, **kwargs: ())
    context = SimpleNamespace(header_renderer=renderer)
    graph = SimpleNamespace(class_infos={}, hierarchy_order=[], diagnostics=())
    witness = "ambiguous complete base requirement for derived: Node candidates first, second"
    plan = HeaderDependencyPlan({}, {}, build_header_name_index({}), {}, (), (witness,))

    assert _generation_diagnostics(context, graph, plan) == (witness,)


def _class(
    name: str,
    die_offset: int,
    source: str,
    method: MethodInfo | None = None,
    *,
    is_declaration: bool = False,
) -> ClassInfo:
    return ClassInfo(
        name=name,
        byte_size=8,
        members=[],
        methods=[method] if method is not None else [],
        base_classes=[],
        enums=[],
        nested_structs=[],
        unions=[],
        declaration_file=source,
        die_offset=die_offset,
        cu_offset=die_offset + 100,
        qualified_name=name,
        is_declaration=is_declaration,
    )


def _symbol_union_context() -> tuple[dict[str, ClassInfo], MagicMock, MagicMock, SimpleNamespace]:
    method = MethodInfo(
        name="load",
        return_type="void",
        parameters=[ParameterInfo("reader", "MtDataReader&", type_offset=3)],
        die_offset=11,
        cu_offset=101,
    )
    classes = {
        "RootA": _class("RootA", 1, "RootA.h", method),
        "RootB": _class("RootB", 2, "RootB.h"),
        "MtDataReader": _class("MtDataReader", 3, "MtDataReader.h"),
    }
    builder = MagicMock()
    builder.build_symbol_union_with_dependencies.return_value = (
        classes,
        ["RootA", "RootB", "MtDataReader"],
    )
    builder.dependency_extractor.extract_dependencies.side_effect = (
        lambda info, *, include_method_signatures: (
            {3} if include_method_signatures and info.name in {"RootA", "RootB"} else set()
        )
    )
    renderer = MagicMock()
    renderer.external_dependency_headers.return_value = {}
    renderer.external_dependency_headers_for_group_specs.side_effect = (
        lambda _infos, groups, *_args, **_kwargs: {
            group_id: ({"MtDataReader": "shared/MtDataReader.h"} if "RootA" in names else {})
            for group_id, names in groups.items()
        }
    )
    renderer.generate_single_file_hierarchy_header.side_effect = lambda infos, *_args, **_kwargs: (
        "\n".join(f"class {info.name} {{}};" for info in infos.values()) + "\n"
    )
    resolver = MagicMock()
    resolver.collect_used_typedefs.return_value = {}
    context = SimpleNamespace(
        hierarchy_builder=builder,
        type_resolver=resolver,
        header_renderer=renderer,
    )
    return classes, builder, renderer, context


@pytest.mark.unit
@pytest.mark.functional
def test_symbols_use_one_union_and_assign_shared_method_dependency_once() -> None:
    classes, builder, renderer, context = _symbol_union_context()

    result = SymbolExtractionService.generate(
        context,
        SymbolExtractionRequest(("RootA", "RootB")),
    )

    builder.build_symbol_union_with_dependencies.assert_called_once_with(
        ("RootA", "RootB"), max_depth=10, include_method_signatures=True
    )
    reader_key = next(
        name for name, info in result.class_infos.items() if info.name == "MtDataReader"
    )
    assert result.class_owners[reader_key] == "shared"
    assert result.class_origins[reader_key] == ("RootA", "RootB")
    assert tuple(result.header_owners.values()).count("shared") == 1
    assert len([path for path in result.headers if "MtDataReader" in path]) == 1
    renderer.build_dependency_plan.assert_called_once()
    assert renderer.external_dependency_headers_for_group_specs.call_count == 1
    renderer.external_dependency_headers.assert_not_called()
    assert renderer.generate_single_file_hierarchy_header.call_args_list
    assert all(
        call.kwargs["allow_cyclic_dependencies"] is True
        for call in renderer.generate_single_file_hierarchy_header.call_args_list
    )


@pytest.mark.unit
@pytest.mark.functional
def test_symbols_retain_declaration_only_method_dependency_diagnostic() -> None:
    method = MethodInfo(
        name="load",
        return_type="void",
        parameters=[ParameterInfo("reader", "MtDataReader&", type_offset=3)],
    )
    classes = {
        "Root": _class("Root", 1, "Root.h", method),
        "MtDataReader": _class("MtDataReader", 3, "MtDataReader.h", is_declaration=True),
    }
    builder = MagicMock()
    builder.build_symbol_union_with_dependencies.return_value = (
        classes,
        ["Root", "MtDataReader"],
    )
    builder.dependency_extractor.extract_dependencies.return_value = {3}
    renderer = MagicMock()
    renderer.external_dependency_headers.return_value = {}
    renderer.generate_single_file_hierarchy_header.side_effect = lambda infos, *_args, **_kwargs: (
        "\n".join(f"class {info.name} {{}};" for info in infos.values()) + "\n"
    )
    context = SimpleNamespace(
        hierarchy_builder=builder,
        type_resolver=MagicMock(),
        header_renderer=renderer,
    )

    result = SymbolExtractionService.generate(context, SymbolExtractionRequest(("Root",)))

    assert any(
        "declaration-only method-signature parameter dependency" in item
        for item in result.diagnostics
    )


@pytest.mark.unit
@pytest.mark.regression
def test_namespace_symbol_uses_namespace_header_in_symbol_route() -> None:
    namespace = _class("rAcquirement", 1, "ignored.cpp")
    namespace.kind = "namespace"
    builder = MagicMock()
    builder.build_symbol_union_with_dependencies.return_value = (
        {"rAcquirement|101|1": namespace},
        ["rAcquirement|101|1"],
    )
    builder.dependency_extractor.extract_dependencies.return_value = set()
    namespace_die = MagicMock(tag="DW_TAG_namespace", offset=0x20, attributes={})
    namespace_die.iter_children.return_value = []
    class_parser = MagicMock()
    class_parser.find_class.return_value = (SimpleNamespace(cu_offset=0x30), namespace_die)
    context = SimpleNamespace(
        hierarchy_builder=builder,
        class_parser=class_parser,
        type_resolver=MagicMock(),
        header_renderer=MagicMock(),
    )

    result = SymbolExtractionService.generate(
        context,
        SymbolExtractionRequest(("rAcquirement",)),
    )

    assert tuple(result.headers) == ("rAcquirement/rAcquirement.h",)
    assert "namespace rAcquirement" in result.headers["rAcquirement/rAcquirement.h"]
    assert "class rAcquirement" not in result.headers["rAcquirement/rAcquirement.h"]
    builder.build_symbol_union_with_dependencies.assert_called_once_with(
        ("rAcquirement",), max_depth=10, include_method_signatures=True
    )
    builder.build_full_hierarchy_with_dependencies.assert_not_called()


@pytest.mark.unit
@pytest.mark.regression
def test_ps4_builtin_aliases_do_not_create_unresolved_signature_diagnostics() -> None:
    assert _is_builtin_signature_type("u32")
    assert _is_builtin_signature_type("f32")
    assert not _is_builtin_signature_type("MtDataReader")


@pytest.mark.unit
@pytest.mark.functional
def test_symbol_header_collision_gets_deterministic_identity_suffix() -> None:
    first = _class("First", 11, r"one\common.cpp")
    second = _class("Second", 22, r"two\common.cpp")
    classes = {"First": first, "Second": second}
    groups = _header_groups(classes, {"First": "Root", "Second": "Root"})

    paths = _allocate_header_paths(groups, classes)

    assert len(paths) == 2
    assert all(path.startswith("Root/common-") and path.endswith(".h") for path in paths)
    assert len(set(paths)) == 2


@pytest.mark.unit
@pytest.mark.regression
def test_conflicting_same_name_definitions_get_separate_headers() -> None:
    first = _class("Shared", 11, "common.h")
    second = _class("Shared", 22, "common.h")
    first.qualified_name = second.qualified_name = "Shared"
    second.members.append(MemberInfo(name="value", type_name="int", offset=0))
    classes = {"first": first, "second": second}
    groups = _header_groups(classes, {"first": "Root", "second": "Root"})
    paths = _allocate_header_paths(groups, classes)

    assert len(paths) == 2
    assert len({path for path in paths if path.startswith("Root/common-")}) == 2


@pytest.mark.unit
@pytest.mark.regression
def test_cross_owner_conflicts_get_identity_suffixes_and_no_conflicting_include() -> None:
    first = _class("Shared", 11, "common.h")
    second = _class("Shared", 22, "common.h")
    first.qualified_name = second.qualified_name = "Shared"
    classes = {"first": first, "second": second}
    groups = _header_groups(classes, {"first": "shared", "second": "Root"})

    paths = _allocate_header_paths(groups, classes)
    header_names = _header_names_for_group(
        classes,
        ("second",),
        {name: path for path, (_owner, names) in paths.items() for name in names},
        "Root",
    )

    assert all("common-" in path for path in paths)
    assert "second" not in header_names
    assert "first" not in header_names


@pytest.mark.unit
@pytest.mark.regression
def test_header_validation_rejects_missing_includes_and_duplicate_definitions() -> None:
    info = _class("Root", 1, "Root.h")
    key = "Root|101|1"
    with pytest.raises(ValueError, match="include"):
        _validate_rendered_headers(
            {"Root/Root.h": '#include "shared/Missing.h"\nclass Root {};\n'},
            {"Root/Root.h": ("Root", (key,))},
            {key: info},
            {key: "Root"},
        )

    with pytest.raises(ValueError, match="duplicate complete definitions"):
        _validate_rendered_headers(
            {"Root/Root.h": "class Root\n{ };\nclass Root {};\n"},
            {"Root/Root.h": ("Root", (key,))},
            {key: info},
            {key: "Root"},
        )


@pytest.mark.unit
@pytest.mark.regression
def test_header_validation_accepts_multiline_complete_definition() -> None:
    info = _class("Root", 1, "Root.h")
    key = "Root|101|1"

    _validate_rendered_headers(
        {"Root/Root.h": "class Root\n{ };\n"},
        {"Root/Root.h": ("Root", (key,))},
        {key: info},
        {key: "Root"},
    )


@pytest.mark.unit
@pytest.mark.regression
def test_header_validation_distinguishes_nested_same_name_definitions() -> None:
    info = _class("MyDTI", 1, "Root.h")
    key = "MyDTI|101|1"

    _validate_rendered_headers(
        {"Root/Root.h": "class MyDTI\n{ class Outer { class MyDTI {}; }; };\n"},
        {"Root/Root.h": ("Root", (key,))},
        {key: info},
        {key: "Root"},
    )


@pytest.mark.unit
@pytest.mark.regression
def test_template_specialization_with_qualified_argument_validates_primary_name() -> None:
    info = _class("MtTypedArray<cAbilityParam::cParamData>", 1, "MtCollection.h")

    assert _rendered_class_name(info) == "MtTypedArray"
    _validate_rendered_headers(
        {"Root/MtCollection.h": "template <typename T>\nclass MtTypedArray\n{ };\n"},
        {"Root/MtCollection.h": ("Root", ("specialization|101|1",))},
        {"specialization|101|1": info},
        {"specialization|101|1": "Root"},
    )


@pytest.mark.unit
@pytest.mark.functional
def test_diagnostic_mentions_origin_and_root_statuses() -> None:
    mt_object = _class("MtObject", 1, "MtObject.h")
    c_resource = _class("cResource", 2, "cResource.h")
    root_a = _class("RootA", 3, "RootA.h")
    other = _class("cDelegateCore", 4, "cDelegate.h")

    unrelated_diag = (
        "unresolved method-signature return dependency for "
        "cDelegateCore|104|4::getNodeAt: cNodeT<MtVector3 (MtObject::*)()>*"
    )
    assert not diagnostic_mentions_origin(unrelated_diag, "MtObject|101|1", mt_object)
    assert not diagnostic_mentions_origin(unrelated_diag, "cResource|102|2", c_resource)
    assert not diagnostic_mentions_origin(unrelated_diag, "RootA|103|3", root_a)
    assert diagnostic_mentions_origin(unrelated_diag, "cDelegateCore|104|4", other)

    root_diag = (
        "unresolved method-signature parameter dependency for RootA|103|3::init: MissingType"
    )
    assert diagnostic_mentions_origin(root_diag, "RootA|103|3", root_a)

    class_infos = {
        "RootA|103|3": root_a,
        "MtObject|101|1": mt_object,
        "cResource|102|2": c_resource,
    }
    graph = CanonicalDefinitionGraph(
        class_infos=class_infos,
        hierarchy_order=["RootA|103|3", "cResource|102|2", "MtObject|101|1"],
        root_keys={"RootA": "RootA|103|3"},
        origins={
            "RootA|103|3": {"RootA"},
            "cResource|102|2": {"RootA"},
            "MtObject|101|1": {"RootA"},
        },
        dependencies={},
        aliases={},
        diagnostics=(),
    )

    statuses = root_statuses(graph, (unrelated_diag,))
    assert statuses == {"RootA": "success"}

    statuses_partial = root_statuses(graph, (root_diag,))
    assert statuses_partial == {"RootA": "partial"}
