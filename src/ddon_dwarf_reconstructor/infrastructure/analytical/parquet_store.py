"""Predicate-backed Parquet query adapter for the analytical runtime."""

from .parquet_store_queries import ParquetStoreQueries


class ParquetDwarfStore(ParquetStoreQueries):
    """Read only the Parquet rows needed by a query without loading JSONL."""
