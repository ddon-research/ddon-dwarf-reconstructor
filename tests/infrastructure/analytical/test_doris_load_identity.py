"""Characterize durable Stream Load labels before any migration decision."""

from __future__ import annotations

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.doris import (
    DorisLoadPlan,
    _load_label,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional, pytest.mark.regression]


def _plan(tmp_path: Path, table: str) -> DorisLoadPlan:
    return DorisLoadPlan(
        database="test_db",
        table=table,
        sql=(),
        parquet_files=(),
        manifest_path=tmp_path / "manifest.json",
    )


def test_current_label_identity_is_source_family_and_relative_path_bound(tmp_path: Path) -> None:
    parquet = tmp_path / "parquet" / "index" / "records.parquet"
    parquet.parent.mkdir(parents=True)
    parquet.write_bytes(b"fixture")
    source = "a" * 64
    canonical = _load_label(_plan(tmp_path, "dwarf"), "index", parquet, source)
    repeated = _load_label(_plan(tmp_path, "dwarf"), "index", parquet, source)
    alternate_table = _load_label(_plan(tmp_path, "alternate"), "index", parquet, source)

    assert canonical == repeated
    assert canonical == alternate_table
    assert canonical.startswith("ddon_" + source[:16] + "_index_")


def test_changed_source_identity_changes_label_without_reusing_previous_receipt(
    tmp_path: Path,
) -> None:
    parquet = tmp_path / "parquet" / "index" / "records.parquet"
    parquet.parent.mkdir(parents=True)
    parquet.write_bytes(b"fixture")
    first = _load_label(_plan(tmp_path, "dwarf"), "index", parquet, "a" * 64)
    rebuilt = _load_label(_plan(tmp_path, "dwarf"), "index", parquet, "b" * 64)

    assert first != rebuilt
