"""Method and code-range query mixin for the Doris store façade."""

from __future__ import annotations

from collections.abc import Sequence

from ...domain.models.analytical_dwarf import MethodContextRequest, QueryResult
from .doris_store_queries import DorisStoreQueryOperations


class DorisMethodQueries:
    """Expose method identity and range queries without enlarging the store façade."""

    _query_operations: DorisStoreQueryOperations

    @property
    def _method_queries(self) -> DorisStoreQueryOperations:
        return self._query_operations

    def find_method_implementation(self, declaration_offset: int) -> QueryResult:
        return self._method_queries.find_method_implementation(declaration_offset)

    def find_method_implementations(self, declaration_offset: int) -> QueryResult:
        return self._method_queries.find_method_implementations(declaration_offset)

    def find_method_implementation_rows(self, declaration_offsets: Sequence[int]) -> QueryResult:
        return self._method_queries.find_method_implementation_rows(declaration_offsets)

    def find_method_context_batch(self, requests: Sequence[MethodContextRequest]) -> QueryResult:
        return self._method_queries.find_method_context_batch(requests)

    def find_code_ranges(self, die_offset: int) -> QueryResult:
        return self._method_queries.find_code_ranges(die_offset)

    def find_locations(self, die_offset: int, *, attribute_name: str | None = None) -> QueryResult:
        return self._method_queries.find_locations(die_offset, attribute_name=attribute_name)

    def find_frames(
        self, *, start_address: int | None = None, end_address: int | None = None
    ) -> QueryResult:
        return self._method_queries.find_frames(
            start_address=start_address, end_address=end_address
        )


__all__ = ["DorisMethodQueries"]
