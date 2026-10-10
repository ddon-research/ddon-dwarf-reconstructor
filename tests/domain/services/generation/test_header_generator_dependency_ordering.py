"""Focused tests for grouped header dependency ordering and forwards."""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    EnumeratorInfo,
    EnumInfo,
    MemberInfo,
    MethodInfo,
    ParameterInfo,
    StructInfo,
)
from ddon_dwarf_reconstructor.domain.models.dwarf.type_reference import (
    TypeDeclarator,
    TypeReference,
)
from ddon_dwarf_reconstructor.domain.services.generation import HeaderRenderer
from ddon_dwarf_reconstructor.domain.services.generation.header_hierarchy import (
    HierarchyHeaderGenerationService,
)
from ddon_dwarf_reconstructor.domain.services.generation.header_ordering import (
    HeaderOrderingService,
)
from ddon_dwarf_reconstructor.domain.services.generation.rendering import TypeExpressionPolicy


@pytest.fixture
def header_generator() -> HeaderRenderer:
    return HeaderRenderer(Mock())


class TestHeaderGeneratorDependencyOrdering:
    @pytest.mark.unit
    def test_grouped_external_dependencies_are_planned_from_one_graph(self, header_generator):
        reader = ClassInfo(
            name="MtDataReader",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5520,
        )
        owner = ClassInfo(
            name="rAchievement",
            byte_size=8,
            members=[],
            methods=[
                MethodInfo(
                    name="load",
                    return_type="void",
                    parameters=[ParameterInfo("reader", "MtDataReader&", type_offset=0x5520)],
                )
            ],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5530,
        )

        dependencies = header_generator.external_dependency_headers_for_groups(
            {"rAchievement": owner, "MtDataReader": reader},
            {
                "rAchievement/rAchievement.h": {"rAchievement"},
                "shared/MtDataReader.h": {"MtDataReader"},
            },
            {
                "rAchievement": "rAchievement/rAchievement.h",
                "MtDataReader": "shared/MtDataReader.h",
            },
        )

        assert dependencies == {
            "rAchievement/rAchievement.h": {
                "MtDataReader": "shared/MtDataReader.h",
            },
            "shared/MtDataReader.h": {},
        }

    @pytest.mark.unit
    @pytest.mark.performance
    @pytest.mark.non_functional
    def test_group_specs_reuse_one_dependency_plan_and_name_index(self, header_generator):
        reader = ClassInfo(
            name="MtDataReader",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5520,
        )
        owner = ClassInfo(
            name="rAchievement",
            byte_size=8,
            members=[],
            methods=[
                MethodInfo(
                    name="load",
                    return_type="void",
                    parameters=[ParameterInfo("reader", "MtDataReader&", type_offset=0x5520)],
                )
            ],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5530,
        )
        classes = {"rAchievement": owner, "MtDataReader": reader}
        plan = header_generator.build_dependency_plan(classes, ["rAchievement", "MtDataReader"])

        dependencies = header_generator.external_dependency_headers_for_group_specs(
            classes,
            {
                "rAchievement/rAchievement.h": {"rAchievement"},
                "shared/MtDataReader.h": {"MtDataReader"},
            },
            {
                "rAchievement/rAchievement.h": {
                    "rAchievement": "rAchievement/rAchievement.h",
                    "MtDataReader": "shared/MtDataReader.h",
                },
                "shared/MtDataReader.h": {"MtDataReader": "shared/MtDataReader.h"},
            },
            dependency_plan=plan,
        )

        assert plan.name_index["MtDataReader"] == "MtDataReader"
        assert dependencies == {
            "rAchievement/rAchievement.h": {
                "MtDataReader": "shared/MtDataReader.h",
            },
            "shared/MtDataReader.h": {},
        }

    @pytest.mark.unit
    def test_grouped_external_dependencies_include_value_typedef_targets(self, header_generator):
        owner = ClassInfo(
            name="Owner",
            byte_size=8,
            members=[MemberInfo(name="value", type_name="ValueAlias", offset=0)],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5540,
        )
        value = ClassInfo(
            name="ConcreteValue",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5550,
        )

        dependencies = header_generator.external_dependency_headers_for_groups(
            {"Owner": owner, "ConcreteValue": value},
            {"owner.h": {"Owner"}, "value.h": {"ConcreteValue"}},
            {"Owner": "owner.h", "ConcreteValue": "value.h"},
            typedefs={"ValueAlias": "ConcreteValue"},
        )

        assert dependencies == {"owner.h": {"ConcreteValue": "value.h"}, "value.h": {}}

    @pytest.mark.unit
    def test_cyclic_dependency_components_are_deterministic(self, header_generator):
        classes = {
            name: ClassInfo(
                name=name,
                byte_size=8,
                members=[MemberInfo(name="peer", type_name=peer, offset=0)],
                methods=[],
                base_classes=[],
                enums=[],
                nested_structs=[],
                unions=[],
                die_offset=0x5560 + index,
            )
            for index, (name, peer) in enumerate((("A", "B"), ("B", "A"), ("C", "int")))
        }

        assert header_generator.cyclic_dependency_components(classes, ["A", "B", "C"]) == (
            ("A", "B"),
        )

    @pytest.mark.unit
    def test_alias_equivalent_method_parameters_are_emitted_once(self, header_generator):
        class_info = ClassInfo(
            name="AliasMethods",
            byte_size=8,
            members=[],
            methods=[
                MethodInfo(
                    name="concat",
                    return_type="void",
                    parameters=[ParameterInfo("value", "MT_CHAR", type_offset=0x10, cu_offset=0)],
                ),
                MethodInfo(
                    name="concat",
                    return_type="void",
                    parameters=[ParameterInfo("value", "MT_CTSTR", type_offset=0x10, cu_offset=0)],
                ),
            ],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5510,
        )

        header = header_generator.generate_header(class_info, include_metadata=False)

        assert header.count("concat(MT_CHAR value);") == 1
        assert "concat(MT_CTSTR value);" not in header

    @pytest.mark.unit
    def test_parameter_declarators_remain_distinct(self, header_generator):
        class_info = ClassInfo(
            name="QualifiedMethods",
            byte_size=8,
            members=[],
            methods=[
                MethodInfo(
                    name="read",
                    return_type="void",
                    parameters=[ParameterInfo("value", "Value*", type_offset=0x10)],
                ),
                MethodInfo(
                    name="read",
                    return_type="void",
                    parameters=[ParameterInfo("value", "const Value*", type_offset=0x10)],
                ),
            ],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5520,
        )

        header = header_generator.generate_header(class_info, include_metadata=False)

        assert "read(Value* value);" in header
        assert "read(const Value* value);" in header

    @pytest.mark.unit
    def test_const_pointer_and_nonconst_reference_overloads_remain_distinct(self, header_generator):
        class_info = ClassInfo(
            name="PointerOverloads",
            byte_size=8,
            members=[],
            methods=[
                MethodInfo(
                    name="read",
                    return_type="void",
                    parameters=[ParameterInfo("value", "const Value*")],
                ),
                MethodInfo(
                    name="read",
                    return_type="void",
                    parameters=[ParameterInfo("value", "Value*&")],
                ),
            ],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5521,
        )

        header = header_generator.generate_header(class_info, include_metadata=False)

        assert "read(const Value* value);" in header
        assert "read(Value*& value);" in header

    @pytest.mark.unit
    def test_ref_qualified_method_overloads_remain_distinct(self, header_generator):
        class_info = ClassInfo(
            name="RefOverloads",
            byte_size=8,
            members=[],
            methods=[
                MethodInfo(name="value", return_type="int", ref_qualifier="&"),
                MethodInfo(name="value", return_type="int", ref_qualifier="&&"),
            ],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5522,
        )

        header = header_generator.generate_header(class_info, include_metadata=False)

        assert "value() &;" in header
        assert "value() &&;" in header

    @pytest.mark.unit
    def test_nested_struct_pointer_members_receive_forward_declarations(self, header_generator):
        """Pointer-only members in nested structs must name declared aggregate types."""
        class_info = ClassInfo(
            name="Layout",
            byte_size=16,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[
                StructInfo(
                    name="Buffer",
                    byte_size=8,
                    members=[MemberInfo("items", "Item*", offset=0)],
                )
            ],
            unions=[],
            die_offset=0x5600,
        )

        header = header_generator.generate_header(class_info, include_metadata=False)

        assert "class Item;" in header
        assert "Item* items;" in header

    @pytest.mark.unit
    def test_enum_method_types_are_defined_before_method_users(self, header_generator):
        """Method signatures using recovered enums must compile without external stubs."""
        class_info = ClassInfo(
            name="Texture",
            byte_size=8,
            members=[],
            methods=[
                MethodInfo(
                    name="setMode",
                    return_type="void",
                    parameters=[ParameterInfo("mode", "Mode")],
                )
            ],
            base_classes=[],
            enums=[
                EnumInfo(
                    name="Mode",
                    byte_size=4,
                    enumerators=[EnumeratorInfo(name="MODE_A", value=0)],
                    scoped=True,
                    representation_type=TypeReference(TypeDeclarator("int")),
                )
            ],
            nested_structs=[],
            unions=[],
            die_offset=0x5700,
        )

        header = header_generator.generate_header(class_info, include_metadata=False)

        assert "enum class Mode : int" in header
        assert "void setMode(Mode mode);" in header

    @pytest.mark.unit
    def test_conflicting_aggregate_forward_declarations_use_source_kind(self):
        result = HierarchyHeaderGenerationService._preferred_forward_declaration(
            "stOcdActiveData",
            ["class stOcdActiveData;", "struct stOcdActiveData;"],
            {},
        )

        assert result == "struct stOcdActiveData;"

    @pytest.mark.unit
    def test_ambiguous_typedef_forward_declaration_uses_renderer_policy(self):
        assert TypeExpressionPolicy.preferred_forward_kind("Texture") == "class"

    @pytest.mark.unit
    def test_conflicting_template_forward_signatures_are_rejected(self):
        with pytest.raises(ValueError, match="conflicting template primary declarations"):
            HierarchyHeaderGenerationService._preferred_forward_declaration(
                "rTbl2",
                [
                    "template <typename T> class rTbl2;",
                    "template <typename T, typename U, typename V> class rTbl2;",
                ],
                {},
            )

    @pytest.mark.unit
    def test_enum_class_forward_declaration_prefers_enum_class_over_class(self):
        result = HierarchyHeaderGenerationService._preferred_forward_declaration(
            "MOT_TYPE",
            ["class MOT_TYPE;", "enum class MOT_TYPE : int;"],
            {},
        )

        assert result == "enum class MOT_TYPE : int;"

    @pytest.mark.unit
    def test_template_argument_pointers_do_not_mark_outer_member_as_indirection(self):
        assert not HeaderOrderingService._is_indirection_type(
            "cDelegate_4<void, cpSequenceCtrl *, u32, u32, u16>"
        )
        assert HeaderOrderingService._is_indirection_type(
            "cDelegate_4<void, cpSequenceCtrl *, u32, u32, u16>*"
        )
        assert HeaderOrderingService._is_indirection_type("int*")
        assert not HeaderOrderingService._is_indirection_type("int")

    @pytest.mark.unit
    def test_nested_base_class_resolves_to_outer_owner_class(self):
        from ddon_dwarf_reconstructor.domain.services.generation.header_dependency_plan import (
            build_header_name_index,
        )

        inner = ClassInfo(
            name="Constraint",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            qualified_name="uModel::Constraint",
        )
        outer = ClassInfo(
            name="uModel",
            byte_size=100,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            qualified_name="uModel",
            nested_classes=[inner],
        )
        derived = ClassInfo(
            name="uConstraint",
            byte_size=50,
            members=[],
            methods=[],
            base_classes=["uModel::Constraint"],
            enums=[],
            nested_structs=[],
            unions=[],
            qualified_name="uConstraint",
        )
        index = build_header_name_index({"uModel": outer, "uConstraint": derived})

        assert index["uModel::Constraint"] == "uModel"

    @pytest.mark.unit
    def test_generic_template_instantiations_do_not_inject_dependencies_into_container_header(
        self, header_generator
    ):
        from ddon_dwarf_reconstructor.domain.models.dwarf import (
            TemplateTypeParam,
            TemplateValueParam,
        )
        from ddon_dwarf_reconstructor.domain.services.generation.template_families import (
            plan_template_families,
        )

        carray1 = ClassInfo(
            name="cArray<bool, 8>",
            qualified_name="nDDOUtility::cArray<bool, 8>",
            byte_size=8,
            members=[MemberInfo("elems", "bool[8]", offset=0)],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            template_parameters=[
                TemplateTypeParam("T", "bool"),
                TemplateValueParam("N", "unsigned int", 8),
            ],
            declaration_file="nDDOUtility.h",
        )
        carray2 = ClassInfo(
            name="cArray<cContextPlayerInfo::cAbility, 10>",
            qualified_name="nDDOUtility::cArray<cContextPlayerInfo::cAbility, 10>",
            byte_size=100,
            members=[MemberInfo("elems", "cContextPlayerInfo::cAbility[10]", offset=0)],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            template_parameters=[
                TemplateTypeParam("T", "cContextPlayerInfo::cAbility"),
                TemplateValueParam("N", "unsigned int", 10),
            ],
            declaration_file="nDDOUtility.h",
        )
        player_info = ClassInfo(
            name="cContextPlayerInfo",
            qualified_name="cContextPlayerInfo",
            byte_size=200,
            members=[
                MemberInfo(
                    "mAbilities", "nDDOUtility::cArray<cContextPlayerInfo::cAbility, 10>", offset=0
                ),
            ],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            declaration_file="cContextPlayerInfo.h",
        )
        planned, _ = plan_template_families(
            {"carray1": carray1, "carray2": carray2, "player": player_info}, {}
        )
        deps = header_generator.external_dependency_headers_for_groups(
            planned,
            {"nddo.h": {"carray1", "carray2"}, "player.h": {"player"}},
            {"carray1": "nddo.h", "carray2": "nddo.h", "player": "player.h"},
        )
        assert deps["nddo.h"] == {}
        assert deps["player.h"] == {"carray2": "nddo.h"}
