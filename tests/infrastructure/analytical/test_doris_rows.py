"""Focused tests for restoring typed Doris row values."""

from __future__ import annotations

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.doris_rows import restore_row

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_restore_row_converts_doris_largeint_uint_strings() -> None:
    row = {
        "record_type": "attribute",
        "decoded_value_kind": "uint",
        "decoded_value_uint": "8",
        "raw_value_kind": "uint",
        "raw_value_uint": "8",
    }

    restored = restore_row(row)

    assert restored["decoded_value"] == 8
    assert restored["raw_value"] == 8
