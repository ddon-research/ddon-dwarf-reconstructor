"""Doris analytical schema contracts."""

from __future__ import annotations

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.doris import (
    _FAMILIES,
    _FAMILY_KEYS,
    _native_columns,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_doris_native_duplicate_keys_are_schema_prefixes() -> None:
    for family in _FAMILIES:
        columns = tuple(
            definition.split(maxsplit=1)[0].strip("`") for definition in _native_columns(family)
        )
        assert columns[: len(_FAMILY_KEYS[family])] == _FAMILY_KEYS[family]
