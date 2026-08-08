"""Infrastructure adapters for analytical DWARF stores.

The generation import surface is Doris-only. File-backed JSONL/Parquet adapters
remain available through lazy attributes for explicit inspection and migration
commands, but are not imported while a normal generation session is composed.
"""

from typing import Any

from .doris_store import DorisDwarfIndex, DorisDwarfStore
from .session import AnalyticalDwarfSession

__all__ = [
    "AnalyticalDwarfSession",
    "DorisDwarfIndex",
    "DorisDwarfStore",
    "DwarfMaterializer",
    "JsonlDwarfStore",
    "MaterializedDwarfIndex",
    "ParquetDwarfStore",
    "load_analytical_store",
    "materialization_manifest_path",
    "run_store_benchmark",
]


def __getattr__(name: str) -> Any:
    """Load explicit artifact tooling only when a caller requests it."""
    if name == "DwarfMaterializer":
        from .materializer import DwarfMaterializer

        return DwarfMaterializer
    if name == "load_analytical_store":
        from .artifact_store import load_analytical_store

        return load_analytical_store
    if name == "JsonlDwarfStore" or name == "MaterializedDwarfIndex":
        from .jsonl_store import JsonlDwarfStore, MaterializedDwarfIndex

        return {
            "JsonlDwarfStore": JsonlDwarfStore,
            "MaterializedDwarfIndex": MaterializedDwarfIndex,
        }[name]
    if name == "ParquetDwarfStore":
        from .parquet_store import ParquetDwarfStore

        return ParquetDwarfStore
    if name == "materialization_manifest_path":
        from .manifest import materialization_manifest_path

        return materialization_manifest_path
    if name == "run_store_benchmark":
        from .benchmark import run_store_benchmark

        return run_store_benchmark
    raise AttributeError(name)
