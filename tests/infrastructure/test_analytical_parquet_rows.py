"""Typed Parquet value-column regressions."""

from __future__ import annotations

import pyarrow
import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.json_codec import tag_value, untag_value
from ddon_dwarf_reconstructor.infrastructure.analytical.parquet_rows import (
    normalize_record,
    restore_record,
    schema_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


@pytest.mark.parametrize("value", [bytearray(b"raw"), memoryview(b"decoded")])
def test_byte_like_values_keep_lossless_binary_tags(value: bytearray | memoryview) -> None:
    tagged = tag_value(value)

    assert tagged["kind"] == "bytes"
    assert untag_value(tagged) == bytes(value)


def test_typed_parquet_bytes_keep_canonical_json_and_binary_columns() -> None:
    record = {
        "record_type": "attribute",
        "source_id": "a" * 64,
        "unit_offset": 0,
        "die_offset": 0,
        "ordinal": 0,
        "name": "DW_AT_name",
        "form": "DW_FORM_block1",
        "raw_value": {"kind": "bytes", "encoding": "base64", "value": "cmF3"},
        "decoded_value": {
            "kind": "bytes",
            "encoding": "base64",
            "value": "ZGVjb2RlZA==",
        },
    }

    row = normalize_record(record)
    restored = restore_record(row)

    assert row["decoded_value_kind"] == "bytes"
    assert row["decoded_value_binary"] == b"decoded"
    assert row["decoded_value_json"] == (
        '{"encoding":"base64","kind":"bytes","value":"ZGVjb2RlZA=="}'
    )
    assert restored["decoded_value"] == b"decoded"


def test_unsigned_values_use_exact_doris_compatible_decimal_columns() -> None:
    schema = schema_for(pyarrow, "attribute")
    row = normalize_record(
        {
            "record_type": "attribute",
            "source_id": "a" * 64,
            "unit_offset": 0,
            "die_offset": 0,
            "ordinal": 0,
            "name": "DW_AT_const_value",
            "form": "DW_FORM_udata",
            "raw_value": 2**64 - 1,
            "decoded_value": 2**64 - 1,
        }
    )

    assert schema.field("raw_value_uint").type == pyarrow.decimal128(20, 0)
    assert schema.field("raw_value_size").type == pyarrow.decimal128(20, 0)
    assert row["raw_value_uint"] == 18446744073709551615
    assert restore_record(row)["raw_value"] == 18446744073709551615
