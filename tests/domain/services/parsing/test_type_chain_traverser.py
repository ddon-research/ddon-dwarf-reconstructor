"""Tests for structural type-chain traversal semantics."""

from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.services.parsing.type_chain_traverser import (
    TypeChainTraverser,
)


@pytest.mark.unit
def test_member_function_pointer_typedef_is_not_a_structural_dependency() -> None:
    """A typedef to a member pointer must not resolve to its containing class."""
    containing_class = Mock()
    containing_class.offset = 0xFB4D56A
    containing_class.tag = "DW_TAG_class_type"
    containing_class.attributes = {"DW_AT_name": Mock(value=b"MtObject")}

    member_pointer = Mock()
    member_pointer.offset = 0xA62E
    member_pointer.tag = "DW_TAG_ptr_to_member_type"
    member_pointer.attributes = {
        "DW_AT_type": Mock(value=0xA637),
        "DW_AT_containing_type": Mock(value=0xFB4D56A),
    }
    member_pointer.get_DIE_from_attribute.return_value = containing_class

    typedef = Mock()
    typedef.offset = 0xA623
    typedef.tag = "DW_TAG_typedef"
    typedef.attributes = {
        "DW_AT_name": Mock(value=b"MT_MFUNC"),
        "DW_AT_type": Mock(value=0xA62E),
    }
    typedef.get_DIE_from_attribute.return_value = member_pointer

    field = Mock()
    field.offset = 0x91B2
    field.attributes = {"DW_AT_type": Mock(value=0xA623)}
    field.get_DIE_from_attribute.return_value = typedef

    assert TypeChainTraverser.get_terminal_type_offset(field) is None
    member_pointer.get_DIE_from_attribute.assert_not_called()


@pytest.mark.unit
def test_pointer_to_class_still_resolves_structural_terminal() -> None:
    """Ordinary pointer/const chains must continue to resolve their class type."""
    target = Mock()
    target.offset = 0x2000
    target.tag = "DW_TAG_class_type"
    target.attributes = {"DW_AT_name": Mock(value=b"MtObject")}

    pointer = Mock()
    pointer.offset = 0x1800
    pointer.tag = "DW_TAG_pointer_type"
    pointer.attributes = {"DW_AT_type": Mock(value=0x2000)}
    pointer.get_DIE_from_attribute.return_value = target

    field = Mock()
    field.offset = 0x1000
    field.attributes = {"DW_AT_type": Mock(value=0x1800)}
    field.get_DIE_from_attribute.return_value = pointer

    assert TypeChainTraverser.get_terminal_type_offset(field) == 0x2000
