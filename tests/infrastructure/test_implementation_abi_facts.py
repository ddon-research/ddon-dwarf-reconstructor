"""DIE acquisition preserves lookup precedence, offsets, and traversal failure evidence."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.domain.models.implementation_validation import ValidationStatus
from ddon_dwarf_reconstructor.infrastructure.implementation_abi_facts import acquire_return_type

pytestmark = [pytest.mark.unit, pytest.mark.regression]


@pytest.mark.parametrize(
    "form,value,cu,expected", [("DW_FORM_ref_addr", 0, 100, 0), ("DW_FORM_ref4", 0, 100, 100)]
)
def test_lookup_preserves_absolute_and_cu_relative_zero_offsets(
    form: str, value: int, cu: int, expected: int
) -> None:
    declaration = SimpleNamespace(
        attributes={"DW_AT_type": SimpleNamespace(value=value, form=form)},
        cu=SimpleNamespace(cu_offset=cu),
    )
    target = SimpleNamespace(offset=expected, tag="DW_TAG_pointer_type", attributes={})
    store = Mock()
    store.get_die.return_value = SimpleNamespace(items=(target,))
    diagnostics: list[str] = []
    evidence = acquire_return_type(store, declaration, diagnostics)
    assert evidence.tag == "DW_TAG_pointer_type"
    assert evidence.status is ValidationStatus.OBSERVED
    store.get_die.assert_called_once_with(expected)
    assert not diagnostics


@pytest.mark.parametrize(
    "depth,status", [(15, ValidationStatus.OBSERVED), (16, ValidationStatus.PARTIAL)]
)
def test_qualifier_depth_bound_is_unchanged(depth: int, status: ValidationStatus) -> None:
    target = SimpleNamespace(offset=100, tag="DW_TAG_base_type", attributes={})
    for offset in range(depth):
        target = SimpleNamespace(
            offset=offset,
            tag="DW_TAG_const_type",
            attributes={"DW_AT_type": object()},
            get_DIE_from_attribute=lambda _name, value=target: value,
        )
    declaration = SimpleNamespace(
        attributes={"DW_AT_type": object()}, get_DIE_from_attribute=lambda _name: target
    )
    diagnostics: list[str] = []
    assert acquire_return_type(object(), declaration, diagnostics).status is status
    assert bool(diagnostics) is (status is ValidationStatus.PARTIAL)


@pytest.mark.parametrize("value,diagnostic", [("bad", "not an integer"), (0, "was not found")])
def test_unresolved_reference_retains_diagnostic(value: object, diagnostic: str) -> None:
    declaration = SimpleNamespace(attributes={"DW_AT_type": SimpleNamespace(value=value)})
    store = Mock()
    store.get_die.return_value = SimpleNamespace(items=())
    diagnostics: list[str] = []
    assert (
        acquire_return_type(store, declaration, diagnostics).status is ValidationStatus.NOT_OBSERVED
    )
    assert diagnostic in diagnostics[0]


def test_reference_getter_failure_is_not_swallowed() -> None:
    failure = ValueError("reference resolution failed")
    declaration = SimpleNamespace(
        attributes={"DW_AT_type": object()}, get_DIE_from_attribute=Mock(side_effect=failure)
    )
    with pytest.raises(ValueError) as raised:
        acquire_return_type(object(), declaration, [])
    assert raised.value is failure


def test_qualifier_without_a_target_retains_missing_reference_diagnostic() -> None:
    target = SimpleNamespace(offset=0, tag="DW_TAG_typedef", attributes={})
    declaration = SimpleNamespace(
        attributes={"DW_AT_type": object()}, get_DIE_from_attribute=lambda _name: target
    )
    diagnostics: list[str] = []
    evidence = acquire_return_type(object(), declaration, diagnostics)
    assert evidence.status is ValidationStatus.NOT_OBSERVED
    assert diagnostics == ["return type chain ended without DW_AT_type"]
