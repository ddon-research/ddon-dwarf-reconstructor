"""Focused sidecar query and repair-status coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from ddon_dwarf_reconstructor.infrastructure.zstd_dump_parser import ZstdDumpParser
from ddon_dwarf_reconstructor.infrastructure.zstd_dump_query import _as_int


def _parser(tmp_path: Path) -> ZstdDumpParser:
    dump = tmp_path / "dump.zst"
    dump.write_bytes(b"fixture")
    return ZstdDumpParser(dump, tmp_path / "index.sqlite3")


@pytest.mark.unit
def test_query_inspection_distinguishes_missing_invalid_stale_and_unavailable(
    tmp_path: Path,
) -> None:
    parser = _parser(tmp_path)
    assert parser.inspect_index()["status"] == "missing"

    parser.index_path.write_bytes(b"not sqlite")
    assert parser.inspect_index()["status"] == "invalid"

    parser._read_metadata = Mock(return_value={"schema_version": "1.2"})
    parser._source_metadata = Mock(return_value={"source_size": "1"})
    assert parser.inspect_index()["status"] == "ready"
    parser._metadata_matches_source = Mock(return_value=False)
    assert parser.inspect_index()["status"] == "stale"
    parser._source_metadata = Mock(side_effect=OSError("source unavailable"))
    assert parser.inspect_index()["status"] == "unavailable"


@pytest.mark.unit
def test_method_query_and_repair_adapters_cover_present_absent_and_forced_paths(
    tmp_path: Path,
) -> None:
    parser = _parser(tmp_path)
    parser._ensure_index = Mock()
    connection = Mock()
    connection.execute.return_value.fetchone.side_effect = [(12,), None]
    parser._connect_index = Mock(return_value=connection)

    assert parser.find_method_implementation(10) == 12
    assert parser.find_method_implementation(11) is None
    assert parser.repair_index()["action"] == "repair"
    assert parser.rebuild_index()["action"] == "rebuild"
    parser._ensure_index.assert_any_call()
    parser._ensure_index.assert_any_call(force=True)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, 1), (7, 7), (b"0x10", 16), ("12", 12), ("ff", 255)],
)
def test_sidecar_integer_conversion_accepts_supported_sqlite_values(
    value: object, expected: int
) -> None:
    assert _as_int(value) == expected


@pytest.mark.unit
def test_sidecar_integer_conversion_rejects_unknown_values() -> None:
    with pytest.raises(TypeError, match="Expected an integer"):
        _as_int(object())
    with pytest.raises(ValueError):
        _as_int("not-a-number")
