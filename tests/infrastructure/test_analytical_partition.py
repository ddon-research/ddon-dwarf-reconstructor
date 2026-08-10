"""Parquet partition typing and discovery contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.parquet_layout import (
    hive_partitioning,
    source_hive_partitioning,
)

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_parquet_hive_partition_schema_preserves_int64_bucket(tmp_path: Path) -> None:
    pyarrow = pytest.importorskip("pyarrow")
    dataset_module = pytest.importorskip("pyarrow.dataset")
    parquet = pytest.importorskip("pyarrow.parquet")
    root = tmp_path / "parquet" / "die" / "source_id=source" / "unit_bucket=1"
    root.mkdir(parents=True)
    parquet.write_table(
        pyarrow.table(
            {
                "record_type": ["die"],
                "source_id": ["source"],
                "unit_bucket": pyarrow.array([1], type=pyarrow.int64()),
            }
        ),
        root / "part-00000.parquet",
    )

    dataset = dataset_module.dataset(
        str(tmp_path / "parquet" / "die"),
        format="parquet",
        partitioning=hive_partitioning(pyarrow, dataset_module),
    )

    assert dataset.schema.field("unit_bucket").type == pyarrow.int64()
    assert dataset.to_table().column("unit_bucket").to_pylist() == [1]


def test_family_partitioning_keeps_physical_unit_bucket_values(tmp_path: Path) -> None:
    pyarrow = pytest.importorskip("pyarrow")
    dataset_module = pytest.importorskip("pyarrow.dataset")
    parquet = pytest.importorskip("pyarrow.parquet")
    root = tmp_path / "parquet" / "die" / "source_id=source"
    root.mkdir(parents=True)
    parquet.write_table(
        pyarrow.table(
            {
                "record_type": ["die", "die"],
                "source_id": ["source", "source"],
                "unit_bucket": pyarrow.array([1, 2], type=pyarrow.int64()),
            }
        ),
        root / "part-00000.parquet",
    )

    dataset = dataset_module.dataset(
        str(tmp_path / "parquet" / "die"),
        format="parquet",
        partitioning=source_hive_partitioning(pyarrow, dataset_module),
    )

    assert dataset.schema.field("unit_bucket").type == pyarrow.int64()
    assert dataset.to_table().column("unit_bucket").to_pylist() == [1, 2]
