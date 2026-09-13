"""
Simplified unit tests for HeaderGenerator module.
Tests the core C++ header generation functionality.
"""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.dwarf import (
    ClassInfo,
    MemberInfo,
    MethodInfo,
    ParameterInfo,
)
from ddon_dwarf_reconstructor.domain.services.generation import HeaderRenderer


class TestHeaderGenerator:
    """Test suite for HeaderGenerator functionality."""

    @pytest.fixture
    def mock_dwarf_index(self):
        """Mock DWARF index for testing."""
        return Mock()

    @pytest.fixture
    def header_generator(self, mock_dwarf_index):
        """HeaderGenerator instance with mock dwarf_index."""
        return HeaderRenderer(mock_dwarf_index)

    @pytest.fixture
    def sample_class(self):
        """Create a sample class for testing."""
        members = [
            MemberInfo(name="m_value", type_name="int", offset=0),
            MemberInfo(name="m_name", type_name="std::string", offset=8),
        ]

        methods = [
            MethodInfo(name="TestClass", return_type="", parameters=[], is_constructor=True),
            MethodInfo(name="getValue", return_type="int", parameters=[]),
            MethodInfo(name="~TestClass", return_type="", parameters=[], is_destructor=True),
        ]

        return ClassInfo(
            name="TestClass",
            byte_size=48,
            members=members,
            methods=methods,
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x1000,
        )

    @pytest.mark.unit
    def test_hierarchy_orders_nested_class_bases_before_containing_class(self, header_generator):
        """Nested class inheritance must not depend on a later definition."""
        dti_class = ClassInfo(
            name="MtDTI",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5000,
        )
        nested_class = ClassInfo(
            name="MyDTI",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=["MtDTI"],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5100,
        )
        outer_class = ClassInfo(
            name="MtObject",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            nested_classes=[nested_class],
            die_offset=0x5200,
        )

        header = header_generator.generate_single_file_hierarchy_header(
            {"MtObject": outer_class, "MtDTI": dti_class},
            ["MtObject"],
            "MtObject",
            include_metadata=False,
        )

        assert header.index("class MtDTI") < header.index("class MtObject")
        assert "class MyDTI : public MtDTI" in header

    @pytest.mark.unit
    def test_by_value_dependency_cycles_are_blocking(self, header_generator) -> None:
        with pytest.raises(ValueError, match="cyclic by-value dependencies"):
            header_generator.stable_topological_order({"A": {"B"}, "B": {"A"}}, ["A", "B"])

    @pytest.mark.unit
    def test_symbol_cycle_ordering_uses_deterministic_recovery(self, header_generator) -> None:
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
                die_offset=0x5500 + index,
            )
            for index, (name, peer) in enumerate((("A", "B"), ("B", "A")))
        }

        header = header_generator.generate_single_file_hierarchy_header(
            classes,
            ["A", "B"],
            "A",
            include_metadata=False,
            allow_cyclic_dependencies=True,
        )

        assert "class A" in header
        assert "class B" in header

    @pytest.mark.unit
    def test_hierarchy_declares_opaque_typedef_targets(self, header_generator):
        """Typedefs to external opaque types must be declared before the alias."""
        sample_class = ClassInfo(
            name="OpaqueOwner",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5300,
        )

        header = header_generator.generate_single_file_hierarchy_header(
            {"OpaqueOwner": sample_class},
            ["OpaqueOwner"],
            "OpaqueOwner",
            typedefs={"OpaqueHandle": "pthread_mutex*"},
            include_metadata=False,
        )

        assert "class pthread_mutex;" in header
        assert header.index("class pthread_mutex;") < header.index(
            "typedef pthread_mutex* OpaqueHandle;"
        )

    @pytest.mark.unit
    def test_conversion_operator_omits_return_type(self, header_generator):
        """C++ conversion operators must not repeat their return type."""
        class_info = ClassInfo(
            name="Convertible",
            byte_size=8,
            members=[],
            methods=[MethodInfo(name="operator const char *", return_type="MT_CTSTR")],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5400,
        )

        header = header_generator.generate_header(class_info, include_metadata=False)

        assert "operator const char *();" in header
        assert "MT_CTSTR operator const char *" not in header

    @pytest.mark.unit
    def test_duplicate_method_signatures_are_emitted_once(self, header_generator):
        """Repeated DWARF entries must not create illegal return-only overloads."""
        class_info = ClassInfo(
            name="DuplicateMethods",
            byte_size=8,
            members=[],
            methods=[
                MethodInfo(
                    name="cast",
                    return_type="MtObject*",
                    parameters=[ParameterInfo(name="dti", type_name="const MtDTI&")],
                ),
                MethodInfo(
                    name="cast",
                    return_type="const MtObject*",
                    parameters=[ParameterInfo(name="dti", type_name="const MtDTI&")],
                ),
            ],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5500,
        )

        header = header_generator.generate_header(class_info, include_metadata=False)

        assert header.count("cast(const MtDTI& dti);") == 1

    @pytest.mark.unit
    def test_method_signature_dependency_receives_complete_header_include(self, header_generator):
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

        dependencies = header_generator.external_dependency_headers(
            {"rAchievement": owner, "MtDataReader": reader},
            {"rAchievement"},
            {
                "rAchievement": "rAchievement/rAchievement.h",
                "MtDataReader": "../shared/MtDataReader.h",
            },
        )

        assert dependencies == {"MtDataReader": "../shared/MtDataReader.h"}

    @pytest.mark.unit
    def test_template_base_arguments_are_ordered_before_their_user(self, header_generator):
        data = ClassInfo(
            name="cAchievementData",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5521,
        )
        base = ClassInfo(
            name="rTbl2<cAchievementData>",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5522,
        )
        root = ClassInfo(
            name="rAchievement",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=["rTbl2<cAchievementData>"],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5523,
        )

        header = header_generator.generate_single_file_hierarchy_header(
            {
                "rAchievement": root,
                "rTbl2<cAchievementData>": base,
                "cAchievementData": data,
            },
            ["rAchievement", "rTbl2<cAchievementData>", "cAchievementData"],
            "rAchievement",
            include_metadata=False,
            allow_cyclic_dependencies=True,
        )

        assert header.index("class cAchievementData") < header.index("class rAchievement")

    @pytest.mark.unit
    def test_pointer_method_types_get_opaque_forward_declarations(self, header_generator):
        owner = ClassInfo(
            name="Owner",
            byte_size=8,
            members=[],
            methods=[
                MethodInfo(
                    name="load",
                    return_type="void",
                    parameters=[ParameterInfo("value", "ExternalType*", type_offset=0x5524)],
                )
            ],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5525,
        )

        header = header_generator.generate_header(owner, include_metadata=False)

        assert "class ExternalType;" in header

    @pytest.mark.unit
    def test_class_does_not_forward_declare_itself(self, header_generator):
        owner = ClassInfo(
            name="Owner",
            byte_size=8,
            members=[],
            methods=[
                MethodInfo(
                    name="clone",
                    return_type="Owner*",
                    parameters=[ParameterInfo("other", "Owner&")],
                )
            ],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5525,
        )

        header = header_generator.generate_header(owner, include_metadata=False)

        assert "class Owner;" not in header
        assert "Owner* clone(Owner& other);" in header

    @pytest.mark.unit
    def test_nested_forward_declarations_stay_inside_the_containing_class(self, header_generator):
        nested = ClassInfo(
            name="MyDTI",
            qualified_name="Owner::MyDTI",
            containing_type="Owner",
            byte_size=8,
            members=[MemberInfo(name="DTI", type_name="MyDTI", is_static=True)],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5526,
        )
        owner = ClassInfo(
            name="Owner",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            nested_classes=[nested],
            die_offset=0x5527,
        )

        header = header_generator.generate_single_file_hierarchy_header(
            {"Owner": owner}, ["Owner"], "Owner", include_metadata=False
        )

        assert "\nclass MyDTI;\n" not in header
        assert "    class MyDTI;" in header

    @pytest.mark.unit
    def test_typedef_method_pointers_do_not_become_class_forward_declarations(
        self, header_generator
    ):
        owner = ClassInfo(
            name="Owner",
            byte_size=8,
            members=[],
            methods=[
                MethodInfo(
                    name="load",
                    return_type="void",
                    parameters=[ParameterInfo("value", "MT_CTSTR*", type_offset=0x5528)],
                )
            ],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5529,
        )

        header = header_generator.generate_single_file_hierarchy_header(
            {"Owner": owner},
            ["Owner"],
            "Owner",
            typedefs={"MT_CTSTR": "const char*"},
            include_metadata=False,
        )

        assert "typedef const char* MT_CTSTR;" in header
        assert "class MT_CTSTR;" not in header

    @pytest.mark.unit
    def test_same_header_later_definition_keeps_required_forward_declaration(
        self, header_generator
    ):
        """A later same-header type must be declared before an earlier method use."""
        owner = ClassInfo(
            name="Owner",
            byte_size=8,
            members=[],
            methods=[
                MethodInfo(
                    name="setValue",
                    return_type="void",
                    parameters=[ParameterInfo("value", "LaterType*")],
                )
            ],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5800,
        )
        later = ClassInfo(
            name="LaterType",
            byte_size=8,
            members=[],
            methods=[],
            base_classes=[],
            enums=[],
            nested_structs=[],
            unions=[],
            die_offset=0x5810,
        )

        header = header_generator.generate_single_file_hierarchy_header(
            {"Owner": owner, "LaterType": later},
            ["Owner", "LaterType"],
            "Owner",
            include_metadata=False,
        )

        assert header.index("class LaterType;") < header.index("class Owner")
