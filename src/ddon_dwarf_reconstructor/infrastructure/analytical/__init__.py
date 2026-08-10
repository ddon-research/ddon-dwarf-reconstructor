"""Infrastructure adapters for analytical DWARF stores.

The generation import surface is Doris-only. File-backed JSONL/Parquet adapters
remain available through lazy attributes for explicit inspection and migration
commands, but are not imported while a normal generation session is composed.
"""

from importlib import import_module
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
]


_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "DwarfMaterializer": ("materializer", "DwarfMaterializer"),
    "JsonlDwarfStore": ("jsonl_store", "JsonlDwarfStore"),
    "MaterializedDwarfIndex": ("jsonl_store", "MaterializedDwarfIndex"),
    "ParquetDwarfStore": ("parquet_store", "ParquetDwarfStore"),
    "load_analytical_store": ("artifact_store", "load_analytical_store"),
    "materialization_manifest_path": ("manifest", "materialization_manifest_path"),
}


def __getattr__(name: str) -> Any:
    """Load explicit artifact tooling only when a caller requests it."""
    try:
        module_name, attribute_name = _LAZY_IMPORTS[name]
    except KeyError:
        raise AttributeError(name) from None
    module = import_module(f".{module_name}", __name__)
    return getattr(module, attribute_name)
