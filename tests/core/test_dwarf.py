from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.core.dwarf import dwarf_reference_offset


@pytest.mark.unit
@pytest.mark.regression
def test_reference_offset_uses_resolved_target_for_cu_relative_form() -> None:
    declaration = Mock(offset=0x1090)
    implementation = Mock()
    implementation.attributes = {"DW_AT_specification": Mock(value=0x90)}
    implementation.get_DIE_from_attribute.return_value = declaration

    assert dwarf_reference_offset(implementation, "DW_AT_specification") == 0x1090
