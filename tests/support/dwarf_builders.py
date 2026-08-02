"""Shared typed mock DWARF builders for generator tests."""

from __future__ import annotations

from unittest.mock import Mock


def build_mock_elf_file() -> Mock:
    """Create a realistic ELF test double with line-program metadata."""
    mock_elf = Mock()
    mock_elf.has_dwarf_info.return_value = True
    mock_dwarf_info = Mock()
    mock_line_program = Mock()
    mock_file1 = Mock()
    mock_file1.name = b"MtObject.h"
    mock_file1.dir_index = 1
    mock_file2 = Mock()
    mock_file2.name = b"MtDTI.h"
    mock_file2.dir_index = 1
    mock_line_program.header = {"file_entry": [mock_file1, mock_file2]}
    mock_dwarf_info.line_program_for_CU.return_value = mock_line_program
    mock_elf.get_dwarf_info.return_value = mock_dwarf_info
    mock_elf.header = {
        "e_machine": "EM_X86_64",
        "e_class": "ELFCLASS64",
        "e_data": "ELFDATA2LSB",
        "e_version": "EV_CURRENT",
    }
    return mock_elf


def _base_type(name: str, offset: int) -> Mock:
    die = Mock()
    die.tag = "DW_TAG_base_type"
    die.offset = offset
    die.attributes = {"DW_AT_name": Mock(value=name.encode())}
    return die


def _class_type(name: str, offset: int) -> Mock:
    die = Mock()
    die.tag = "DW_TAG_class_type"
    die.offset = offset
    die.attributes = {"DW_AT_name": Mock(value=name.encode())}
    return die


def _member(
    name: str,
    offset: int,
    type_die: Mock,
    *,
    external: bool = False,
    declaration: bool = False,
    const_value: int | None = None,
    artificial: bool = False,
) -> Mock:
    member = Mock()
    member.tag = "DW_TAG_member"
    member.offset = offset
    member.has_children = False
    member.iter_children.return_value = []
    member.attributes = {
        "DW_AT_name": Mock(value=name.encode()),
        "DW_AT_type": Mock(value=type_die.offset),
        "DW_AT_data_member_location": Mock(value=offset),
        "DW_AT_accessibility": Mock(value=1),
    }
    if external:
        member.attributes["DW_AT_external"] = Mock(value=True)
    if declaration:
        member.attributes["DW_AT_declaration"] = Mock(value=True)
    if const_value is not None:
        member.attributes["DW_AT_const_value"] = Mock(value=const_value)
    if artificial:
        member.attributes["DW_AT_artificial"] = Mock(value=True)
    member.get_DIE_from_attribute = Mock(return_value=type_die)
    return member


def _method(
    name: str,
    offset: int,
    *,
    declaration_line: int,
    return_type: Mock | None = None,
    virtual: bool = False,
) -> Mock:
    method = Mock()
    method.tag = "DW_TAG_subprogram"
    method.offset = offset
    method.has_children = True
    method.iter_children.return_value = []
    method.attributes = {
        "DW_AT_name": Mock(value=name.encode()),
        "DW_AT_decl_file": Mock(value=0x0B),
        "DW_AT_decl_line": Mock(value=declaration_line),
        "DW_AT_declaration": Mock(value=True),
        "DW_AT_accessibility": Mock(value=1),
    }
    if return_type is not None:
        method.attributes["DW_AT_type"] = Mock(value=return_type.offset)
        method.get_DIE_from_attribute = Mock(return_value=return_type)
    if virtual:
        method.attributes["DW_AT_virtuality"] = Mock(value=1)
    return method


def _create_ui_method() -> Mock:
    ui_class = _class_type("MtUI", 0x89C5)
    ui_pointer = Mock()
    ui_pointer.tag = "DW_TAG_pointer_type"
    ui_pointer.offset = 0x89C0
    ui_pointer.attributes = {"DW_AT_type": Mock(value=ui_class.offset)}
    ui_pointer.get_DIE_from_attribute = Mock(return_value=ui_class)
    return _method("createUI", 0x8587, declaration_line=0x42, return_type=ui_pointer, virtual=True)


def _operator_new_method() -> Mock:
    void_pointer = Mock()
    void_pointer.tag = "DW_TAG_pointer_type"
    void_pointer.offset = 0xA622
    void_pointer.attributes = {}
    return _method("operator new", 0x85A6, declaration_line=0x4B, return_type=void_pointer)


def build_mock_die() -> Mock:
    """Create a realistic MtObject class DIE and its direct children."""
    mock_die = Mock()
    mock_die.tag = "DW_TAG_class_type"
    mock_die.offset = 0x84ED
    mock_die.has_children = True
    mock_die.is_null.return_value = False
    mock_die.attributes = {
        "DW_AT_name": Mock(value=b"MtObject"),
        "DW_AT_byte_size": Mock(value=8),
        "DW_AT_decl_file": Mock(value=0x0B),
        "DW_AT_decl_line": Mock(value=0x20),
        "DW_AT_containing_type": Mock(value=0x84ED),
    }
    void_type = _base_type("void*", 0x8667)
    u32_type = _base_type("u32", 0x4193)
    dti_type = _class_type("MyDTI", 0x851D)
    mock_die.iter_children.return_value = [
        _member("_vptr$MtObject", 0x84F9, void_type, artificial=True),
        _member(
            "INITIAL_ALLOCATOR", 0x8504, u32_type, external=True, declaration=True, const_value=0
        ),
        _member("DTI", 0x8511, dti_type, external=True, declaration=True),
        _method("~MtObject", 0x8581, declaration_line=0x3F, virtual=True),
        _create_ui_method(),
        _operator_new_method(),
    ]
    return mock_die


def build_mock_compilation_unit(mock_die: Mock) -> Mock:
    """Create a compilation unit containing the canonical MtObject DIE."""
    mock_cu = Mock()
    mock_cu.cu_offset = 0xC9D
    mock_cu.header = {
        "version": 4,
        "address_size": 8,
        "offset_size": 4,
        "unit_length": 0xC99,
    }
    mock_base_type_u32 = _base_type("unsigned int", 0x4193)
    mock_base_type_u32.is_null.return_value = False
    mock_base_type_u32.attributes.update(
        {"DW_AT_encoding": Mock(value=7), "DW_AT_byte_size": Mock(value=4)}
    )
    mock_pointer_type = Mock()
    mock_pointer_type.tag = "DW_TAG_pointer_type"
    mock_pointer_type.offset = 0x8667
    mock_pointer_type.is_null.return_value = False
    mock_pointer_type.attributes = {"DW_AT_type": Mock(value=0x84ED)}
    mock_cu.iter_DIEs.return_value = [mock_base_type_u32, mock_pointer_type, mock_die]

    def mock_get_die_from_attribute(attr: Mock) -> Mock | None:
        offset_map = {0x4193: mock_base_type_u32, 0x8667: mock_pointer_type, 0x84ED: mock_die}
        return offset_map.get(attr.value) if hasattr(attr, "value") else None

    mock_cu.get_DIE_from_attribute.side_effect = mock_get_die_from_attribute
    return mock_cu
