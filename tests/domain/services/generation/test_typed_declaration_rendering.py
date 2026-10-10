"""Structural declarations preserve identity and C++ operator precedence."""

from dataclasses import replace
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    EnumInfo,
    MemberInfo,
    MethodInfo,
    ParameterInfo,
    TemplateTypeParam,
)
from ddon_dwarf_reconstructor.domain.models.dwarf.type_reference import (
    DeclaratorLayer,
    TypeDeclarator,
    TypeReference,
)
from ddon_dwarf_reconstructor.domain.models.dwarf.type_scope import ScopeComponent, TypeScope
from ddon_dwarf_reconstructor.domain.services.generation import HeaderRenderer
from ddon_dwarf_reconstructor.domain.services.generation.enum_declarations import (
    EnumDeclarationError,
)
from ddon_dwarf_reconstructor.domain.services.generation.header_member_rendering import (
    BitfieldDeclarationError,
)
from ddon_dwarf_reconstructor.domain.services.generation.method_signature_policy import (
    MethodDeclarationError,
)
from ddon_dwarf_reconstructor.domain.services.generation.scoped_declarations import (
    reference_forward_declaration,
    scoped_declaration,
)

pytestmark = [pytest.mark.unit, pytest.mark.regression]


def _class(members=(), methods=()) -> ClassInfo:
    return ClassInfo("Consumer", 8, list(members), list(methods), [], [], [], [])


def _render(info: ClassInfo) -> str:
    lookup = Mock()
    lookup.get_die_by_offset.return_value = None
    lookup.find_symbol_offset.return_value = None
    return HeaderRenderer(lookup).generate_header(info, include_metadata=False)


@pytest.mark.parametrize(
    "other",
    [
        MethodInfo("f", "float"),
        MethodInfo("f", "int", is_noexcept=True),
        MethodInfo("f", "int", is_static=True),
        MethodInfo("f", "int", is_virtual=True),
        MethodInfo("f", "int", access="private"),
        MethodInfo("f", "int", ref_qualifier="&"),
    ],
)
def test_renderer_does_not_hide_conflicting_method_declarations(other: MethodInfo) -> None:
    with pytest.raises(MethodDeclarationError, match="conflicting method declaration"):
        _render(_class(methods=[MethodInfo("f", "int"), other]))


def test_renderer_preserves_legal_cv_ref_overloads_and_deduplicates_observations() -> None:
    methods = [
        MethodInfo("f", "int", ref_qualifier="&"),
        MethodInfo("f", "int", ref_qualifier="&&"),
        MethodInfo("f", "int", is_const=True, ref_qualifier="&"),
        MethodInfo("f", "int", is_const=True, ref_qualifier="&"),
    ]
    header = _render(_class(methods=methods))
    assert header.count("int f() &;") == 1
    assert header.count("int f() &&;") == 1
    assert header.count("int f() const &;") == 1


def test_method_template_uses_matching_type_argument_die_even_at_offset_zero() -> None:
    actual = "uGrass::cRenderOperatorCDRAW<rGrass::cCluster>"
    reference = TypeReference(
        TypeDeclarator(actual, layers=(DeclaratorLayer("reference"),)),
        die_offset=0,
        cu_offset=7,
        kind="DW_TAG_class_type",
    )
    parameter = ParameterInfo(
        "value", reference.name, type_offset=0, cu_offset=7, type_reference=reference
    )
    method = MethodInfo(
        f"searchT<{actual}>",
        "void",
        parameters=[parameter],
        template_parameters=(
            TemplateTypeParam("T", argument_type=actual, cu_offset=7, argument_offset=0),
        ),
    )
    assert "    template <typename T>\n    void searchT(T &value);" in _render(
        _class(methods=[method])
    )
    other_cu = replace(
        method,
        parameters=[replace(parameter, cu_offset=8)],
    )
    assert "template <typename T>" not in _render(_class(methods=[other_cu]))


def test_member_pointer_owner_and_arguments_are_declared_from_typed_evidence() -> None:
    owner = TypeReference(TypeDeclarator("cpCharacterEdit"), kind="DW_TAG_class_type")
    argument = TypeReference(
        TypeDeclarator("gfx::Joint", layers=(DeclaratorLayer("pointer"),)),
        kind="DW_TAG_structure_type",
        scope=TypeScope((ScopeComponent("gfx", "namespace"),)),
    )
    callback = TypeReference(
        TypeDeclarator(
            "void",
            layers=(
                DeclaratorLayer("member_pointer", owner=owner),
                DeclaratorLayer("function", parameters=(argument,), qualifiers=("const",)),
            ),
        ),
        kind="DW_TAG_base_type",
    )
    parameter = ParameterInfo("callback", callback.name, type_reference=callback)
    header = _render(_class(methods=[MethodInfo("bind", "void", parameters=[parameter])]))
    assert "class cpCharacterEdit;" in header
    assert "namespace gfx { struct Joint; }" in header
    assert "void bind(void (cpCharacterEdit::*callback)(gfx::Joint*) const);" in header


def test_named_array_of_callbacks_and_method_returning_callback() -> None:
    callback = TypeReference(
        TypeDeclarator("int", layers=(DeclaratorLayer("pointer"), DeclaratorLayer("function")))
    )
    array = TypeReference(
        TypeDeclarator(
            "int", layers=(DeclaratorLayer("array", extent=3), *callback.declarator.layers)
        )
    )
    header = _render(
        _class(
            members=[MemberInfo("callbacks", array.name, type_reference=array)],
            methods=[MethodInfo("factory", callback.name, return_type_reference=callback)],
        )
    )
    assert "int (*callbacks[3])();" in header
    assert "int (*factory())();" in header


def test_parameter_adjustment_deduplicates_array_and_function_observations() -> None:
    argument = TypeReference(TypeDeclarator("int"), kind="DW_TAG_base_type")
    array = TypeReference(TypeDeclarator("int", layers=(DeclaratorLayer("array", extent=4),)))
    pointer = TypeReference(TypeDeclarator("int", layers=(DeclaratorLayer("pointer"),)))
    function = TypeReference(
        TypeDeclarator("int", layers=(DeclaratorLayer("function", parameters=(argument,)),))
    )
    callback = TypeReference(
        TypeDeclarator(
            "int",
            layers=(
                DeclaratorLayer("pointer"),
                DeclaratorLayer("function", parameters=(argument,)),
            ),
        )
    )
    methods = [
        MethodInfo("f", "void", parameters=[ParameterInfo("items", item.name, type_reference=item)])
        for item in (array, pointer)
    ]
    methods.extend(
        MethodInfo(
            "g", "void", parameters=[ParameterInfo("callback", item.name, type_reference=item)]
        )
        for item in (function, callback)
    )
    header = _render(_class(methods=methods))
    assert header.count("void f(") == 1
    assert header.count("void g(") == 1
    assert "void f(int items[4]);" in header
    assert "void g(int callback(int));" in header


def test_pure_virtual_callable_return_initializer_is_outside_return_declarator() -> None:
    callback = TypeReference(
        TypeDeclarator("int", layers=(DeclaratorLayer("pointer"), DeclaratorLayer("function")))
    )
    method = MethodInfo(
        "factory",
        callback.name,
        return_type_reference=callback,
        is_virtual=True,
        is_pure_virtual=True,
        is_const=True,
    )
    assert "virtual int (*factory() const)() = 0;" in _render(_class(methods=[method]))


@pytest.mark.parametrize("kind", ["class", "struct", "union"])
def test_aggregate_scope_never_becomes_namespace(kind) -> None:
    scope = TypeScope((ScopeComponent("ns", "namespace"), ScopeComponent("Outer", kind)))
    assert scoped_declaration("ns::Outer::Inner", scope=scope) is None
    assert scoped_declaration("ns::Outer::Inner") is None


def test_only_proven_namespace_ancestry_can_wrap_a_declaration() -> None:
    scope = TypeScope((ScopeComponent("ns", "namespace"), ScopeComponent("detail", "namespace")))
    assert scoped_declaration("ns::detail::Value", "struct", scope) == (
        "namespace ns::detail { struct Value; }"
    )
    assert scoped_declaration("other::Value", scope=scope) is None
    assert scoped_declaration("ns::detail::Value", scope=TypeScope(scope.components, False)) is None


@pytest.mark.parametrize("kind", ["DW_TAG_typedef", "DW_TAG_enumeration_type"])
def test_alias_and_enum_kinds_cannot_be_invented_as_classes(kind) -> None:
    reference = TypeReference(TypeDeclarator("Value"), kind=kind)
    assert reference_forward_declaration(reference) is None


@pytest.mark.parametrize("offsets", [[], [0], [42]])
def test_missing_base_name_map_never_strips_qualification(offsets) -> None:
    info = _class()
    info.base_classes = ["cZoneLayout::cInGameGroupManager"]
    info.base_class_offsets = offsets
    assert "class Consumer : public cZoneLayout::cInGameGroupManager" in _render(info)


def test_unknown_named_enum_scopedness_does_not_become_enum_class() -> None:
    info = _class()
    info.enums = [EnumInfo("Mode", 4, [], scoped=None, scopedness_evidence="absent")]
    with pytest.raises(EnumDeclarationError, match="unknown enum scopedness"):
        _render(info)


def test_known_scoped_enum_uses_observed_representation_in_forward_and_definition() -> None:
    info = _class()
    info.enums = [
        EnumInfo(
            "Mode",
            1,
            [],
            scoped=True,
            scopedness_evidence="present",
            representation_type=TypeReference(TypeDeclarator("unsigned char")),
        )
    ]
    header = _render(info)
    assert "enum class Mode : unsigned char;" in header
    assert "enum class Mode : unsigned char\n" in header


def test_scoped_enum_without_integral_representation_fails_explicitly() -> None:
    info = _class()
    info.enums = [EnumInfo("Mode", 4, [], scoped=True, scopedness_evidence="present")]
    with pytest.raises(EnumDeclarationError, match="lacks integral representation"):
        _render(info)


def test_known_unscoped_enum_has_no_opaque_forward_or_invented_fixed_base() -> None:
    info = _class()
    info.enums = [
        EnumInfo(
            "Mode",
            4,
            [],
            scoped=False,
            scopedness_evidence="explicit_false",
            representation_type=TypeReference(TypeDeclarator("unsigned int")),
            fixed_base_evidence=None,
        )
    ]
    header = _render(info)
    assert "enum Mode\n" in header
    assert "enum Mode;" not in header
    assert "enum class Mode" not in header
    assert "enum Mode :" not in header


def test_proven_fixed_unscoped_enum_has_legal_opaque_forward_and_definition() -> None:
    info = _class()
    info.enums = [
        EnumInfo(
            "Mode",
            4,
            [],
            scoped=False,
            fixed_base_evidence=True,
            representation_type=TypeReference(TypeDeclarator("unsigned int")),
        )
    ]
    header = _render(info)
    assert "enum Mode : unsigned int;" in header
    assert "enum Mode : unsigned int\n" in header


def test_legacy_fixed_enum_does_not_guess_scopedness() -> None:
    info = _class()
    info.enums = [
        EnumInfo(
            "Mode",
            4,
            [],
            scoped=None,
            scopedness_evidence="legacy_fixed",
            enum_class_flag=True,
            fixed_base_evidence=True,
            representation_type=TypeReference(TypeDeclarator("unsigned int")),
        )
    ]
    with pytest.raises(EnumDeclarationError, match="unknown enum scopedness"):
        _render(info)


def test_member_pointer_alias_storage_width_does_not_become_bitfield() -> None:
    member = MemberInfo(
        "mpUpdateFunc",
        "MtOscillator::UpdateFunc",
        bit_size=128,
        storage_bit_offset=18446744073709551488,
        bitfield_base_kind="member_pointer_storage",
        type_reference=TypeReference(TypeDeclarator("MtOscillator::UpdateFunc")),
    )
    header = _render(_class(members=[member]))
    assert "UpdateFunc mpUpdateFunc;" in header
    assert "mpUpdateFunc : 128" not in header


def test_unnamed_zero_width_bitfield_is_emitted() -> None:
    member = MemberInfo(
        "", "unsigned int", bit_size=0, bitfield_base_kind="integral", bitfield_base_bits=32
    )
    assert "unsigned int : 0;" in _render(_class(members=[member]))


@pytest.mark.parametrize(
    ("member", "message"),
    [
        (MemberInfo("named", "unsigned int", bit_size=0), "named zero-width"),
        (MemberInfo("bad", "float", bit_size=1), "unproven integral"),
        (
            MemberInfo(
                "wide",
                "unsigned char",
                bit_size=9,
                bitfield_base_kind="integral",
                bitfield_base_bits=8,
            ),
            "width exceeds 8",
        ),
        (MemberInfo("static", "unsigned int", bit_size=1, is_static=True), "illegal bitfield"),
        (MemberInfo("negative", "unsigned int", bit_size=-1), "illegal bitfield"),
        (MemberInfo("boolean", "unsigned int", bit_size=True), "illegal bitfield"),
    ],
)
def test_illegal_bitfields_fail_explicitly(member: MemberInfo, message: str) -> None:
    with pytest.raises(BitfieldDeclarationError, match=message):
        _render(_class(members=[member]))


def test_member_pointer_storage_width_is_not_rendered_as_bitfield() -> None:
    owner = TypeReference(TypeDeclarator("Owner"), kind="DW_TAG_class_type")
    callback = TypeReference(
        TypeDeclarator(
            "void",
            layers=(
                DeclaratorLayer("member_pointer", owner=owner),
                DeclaratorLayer("function"),
            ),
        ),
        kind="DW_TAG_ptr_to_member_type",
    )
    member = MemberInfo(
        "callback",
        callback.name,
        bit_size=128,
        bitfield_base_kind="non_integral",
        type_reference=callback,
    )
    header = _render(_class(members=[member]))
    assert "void (Owner::*callback)();" in header
    assert "callback : 128" not in header
    assert "std::uint8_t callback" not in header
