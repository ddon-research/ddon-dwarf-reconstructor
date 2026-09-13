"""Tests for structural type-chain traversal semantics."""

import gc
import weakref
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.services.parsing.class_parser import ClassParser
from ddon_dwarf_reconstructor.domain.services.parsing.type_chain_traverser import (
    TypeChainTraverser,
)


class _FakeDie:
    def __init__(
        self,
        *,
        cu_offset: int,
        offset: int,
        tag: str,
        attributes: dict[str, object] | None = None,
        target: _FakeDie | None = None,
    ) -> None:
        self.cu = SimpleNamespace(cu_offset=cu_offset)
        self.offset = offset
        self.tag = tag
        self.attributes = attributes or {}
        self._target = target

    def get_DIE_from_attribute(self, name: str) -> _FakeDie | None:  # noqa: N802
        return self._target if name == "DW_AT_type" else None


def _field_with_terminal(cu_offset: int, field_offset: int, terminal_offset: int) -> _FakeDie:
    terminal = _FakeDie(
        cu_offset=cu_offset,
        offset=terminal_offset,
        tag="DW_TAG_class_type",
        attributes={"DW_AT_name": SimpleNamespace(value=b"Target")},
    )
    return _FakeDie(
        cu_offset=cu_offset,
        offset=field_offset,
        tag="DW_TAG_member",
        attributes={"DW_AT_type": SimpleNamespace(value=terminal_offset)},
        target=terminal,
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

    assert TypeChainTraverser().get_terminal_type_offset(field) is None
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

    assert TypeChainTraverser().get_terminal_type_offset(field) == 0x2000


@pytest.mark.unit
def test_anonymous_aggregate_is_a_terminal_type() -> None:
    anonymous = Mock()
    anonymous.offset = 0x3000
    anonymous.tag = "DW_TAG_class_type"
    anonymous.attributes = {}

    field = Mock()
    field.attributes = {"DW_AT_type": Mock(value=0x3000)}
    field.get_DIE_from_attribute.return_value = anonymous

    assert TypeChainTraverser().get_terminal_type_offset(field) == 0x3000


@pytest.mark.unit
def test_declared_type_offset_preserves_typedef_before_terminal_type() -> None:
    typedef = Mock()
    typedef.offset = 0x4000
    typedef.tag = "DW_TAG_typedef"
    typedef.attributes = {"DW_AT_type": Mock(value=0x5000)}

    field = Mock()
    field.attributes = {"DW_AT_type": Mock(value=0x4000)}
    field.get_DIE_from_attribute.return_value = typedef

    assert TypeChainTraverser().get_declared_type_offset(field) == 0x4000


@pytest.mark.unit
def test_integer_cu_die_cache_keys_are_owned_by_each_traverser() -> None:
    first = TypeChainTraverser()
    second = TypeChainTraverser()
    first_field = _field_with_terminal(7, 0x100, 0x200)
    second_field = _field_with_terminal(7, 0x100, 0x300)

    assert first.get_terminal_type_offset(first_field) == 0x200
    assert second.get_terminal_type_offset(second_field) == 0x300


@pytest.mark.unit
def test_class_parser_constructs_a_source_bound_traverser() -> None:
    first = ClassParser(Mock(), Mock())
    second = ClassParser(Mock(), Mock())

    assert first.type_chain_traverser is not second.type_chain_traverser


@pytest.mark.unit
def test_traverser_clear_releases_cached_die_references() -> None:
    traverser = TypeChainTraverser()
    field = _field_with_terminal(7, 0x100, 0x200)
    target = field._target
    assert target is not None
    target_reference = weakref.ref(target)

    assert traverser.get_terminal_type_offset(field) == 0x200
    traverser.clear_cache()
    del field, target
    gc.collect()

    assert target_reference() is None
