"""Shared physical partitioning rules for the Parquet projection."""

from __future__ import annotations

from typing import Any

# Unit buckets are a derived pruning field. The authoritative identifier is
# still the source-bound unit offset; this constant only defines the directory
# layout used by Arrow and the local runtime.
UNIT_BUCKET_SIZE = 0x1000000


def hive_partitioning(pyarrow: Any, dataset_module: Any) -> Any:
    """Return the explicit Hive schema required for our partition directories.

    Arrow infers integer values in ``unit_bucket=...`` directory names as
    ``int32``. The physical row schema intentionally keeps the derived field
    as ``int64`` so offsets and partition metadata do not silently narrow.
    Passing this schema prevents Arrow from attempting to merge ``int32`` path
    fields with ``int64`` data columns.
    """

    schema = pyarrow.schema(
        [
            pyarrow.field("source_id", pyarrow.string()),
            pyarrow.field("unit_bucket", pyarrow.int64()),
        ]
    )
    return dataset_module.partitioning(schema, flavor="hive")


def source_hive_partitioning(pyarrow: Any, dataset_module: Any) -> Any:
    """Return the source-only partitioning used by the family writer layout."""
    schema = pyarrow.schema([pyarrow.field("source_id", pyarrow.string())])
    return dataset_module.partitioning(schema, flavor="hive")


def partitioning_for_layout(pyarrow: Any, dataset_module: Any, layout: str) -> Any:
    """Select the manifest-declared partition contract for a Parquet store."""
    if layout == "family":
        return source_hive_partitioning(pyarrow, dataset_module)
    if layout == "bucketed":
        return hive_partitioning(pyarrow, dataset_module)
    raise ValueError(f"Unsupported Parquet layout: {layout}")


def unit_bucket_for(unit_offset: int) -> int:
    """Map a non-negative unit offset to its physical partition bucket."""

    if unit_offset < 0:
        raise ValueError("unit_offset must be non-negative")
    return unit_offset // UNIT_BUCKET_SIZE
