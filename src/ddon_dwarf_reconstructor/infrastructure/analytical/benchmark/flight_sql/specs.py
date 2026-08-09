"""Parameterized SQL specifications shared by the Flight benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ...doris import DorisConfig
from ...doris_layout import _FAMILIES
from ..doris.queries import doris_table_name

Placeholder = Literal["%s", "?"]


@dataclass(frozen=True, slots=True)
class ParameterizedQuery:
    """One source-bound SQL statement and its bound values."""

    name: str
    sql: str
    params: tuple[object, ...]
    metadata: dict[str, object]


def definition_query(
    config: DorisConfig,
    source_id: str,
    symbol: str,
    placeholder: Placeholder,
    *,
    limit: int = 1001,
) -> ParameterizedQuery:
    """Build the bounded definition lookup without interpolating values."""
    table = _definition_table(config)
    return ParameterizedQuery(
        "find_definitions",
        (
            f"SELECT unit_offset, die_offset FROM {table} "
            f"WHERE source_id = {placeholder} AND index_type = {placeholder} "
            f"AND name = {placeholder} ORDER BY unit_offset, die_offset LIMIT {limit}"
        ),
        (source_id, "definition", symbol),
        {"symbol": symbol, "limit": limit},
    )


def contract_queries(
    config: DorisConfig,
    source_id: str,
    unit_offset: int,
    die_offset: int,
    placeholder: Placeholder,
) -> tuple[ParameterizedQuery, ...]:
    """Build the source-bound related-query contract used by both transports."""
    context = _ContractContext(
        {family: doris_table_name(config, family) for family in _FAMILIES},
        source_id,
        unit_offset,
        die_offset,
        placeholder,
    )
    return (
        *_hierarchy_queries(context),
        *_attribute_queries(context),
        *_evidence_queries(context),
        *_method_queries(context),
    )


@dataclass(frozen=True, slots=True)
class _ContractContext:
    tables: dict[str, str]
    source_id: str
    unit_offset: int
    die_offset: int
    placeholder: Placeholder

    @property
    def source(self) -> str:
        return f"source_id = {self.placeholder}"

    @property
    def unit(self) -> str:
        return f"{self.source} AND unit_offset = {self.placeholder}"

    @property
    def die(self) -> str:
        return f"{self.unit} AND die_offset = {self.placeholder}"

    @property
    def source_params(self) -> tuple[object, ...]:
        return (self.source_id,)

    @property
    def unit_params(self) -> tuple[object, ...]:
        return (self.source_id, self.unit_offset)

    @property
    def die_params(self) -> tuple[object, ...]:
        return (*self.unit_params, self.die_offset)

    @property
    def metadata(self) -> dict[str, object]:
        return {"unit_offset": self.unit_offset, "die_offset": self.die_offset}


def _query(
    context: _ContractContext,
    name: str,
    family: str,
    sql: str,
    params: tuple[object, ...],
    metadata: dict[str, object],
) -> ParameterizedQuery | None:
    if family not in context.tables:
        return None
    return ParameterizedQuery(name, sql, params, metadata)


def _present(queries: tuple[ParameterizedQuery | None, ...]) -> tuple[ParameterizedQuery, ...]:
    return tuple(query for query in queries if query is not None)


def _hierarchy_queries(context: _ContractContext) -> tuple[ParameterizedQuery, ...]:
    p = context.placeholder
    t = context.tables
    metadata = context.metadata
    return _present(
        (
            _query(
                context,
                "get_compilation_unit",
                "unit",
                f"SELECT unit_offset FROM {t.get('unit', '')} WHERE {context.unit} LIMIT 1001",
                context.unit_params,
                {"unit_offset": context.unit_offset},
            ),
            _query(
                context,
                "get_die",
                "die",
                f"SELECT die_offset, tag, parent_offset FROM {t.get('die', '')} WHERE {context.die} LIMIT 1001",
                context.die_params,
                metadata,
            ),
            _query(
                context,
                "parent",
                "die",
                f"SELECT parent_offset FROM {t.get('die', '')} WHERE {context.die} AND parent_offset IS NOT NULL LIMIT 1001",
                context.die_params,
                metadata,
            ),
            _query(
                context,
                "children",
                "die",
                f"SELECT die_offset FROM {t.get('die', '')} WHERE {context.unit} AND parent_offset = {p} ORDER BY ordinal LIMIT 1001",
                (*context.unit_params, context.die_offset),
                metadata,
            ),
            _query(
                context,
                "inheritance",
                "die",
                f"SELECT die_offset FROM {t.get('die', '')} WHERE {context.unit} AND parent_offset = {p} AND tag = {p} ORDER BY ordinal LIMIT 1001",
                (*context.unit_params, context.die_offset, "DW_TAG_inheritance"),
                metadata,
            ),
            _query(
                context,
                "field_layout",
                "die",
                f"SELECT die_offset FROM {t.get('die', '')} WHERE {context.unit} AND parent_offset = {p} AND tag = {p} ORDER BY ordinal LIMIT 1001",
                (*context.unit_params, context.die_offset, "DW_TAG_member"),
                metadata,
            ),
        )
    )


def _attribute_queries(context: _ContractContext) -> tuple[ParameterizedQuery, ...]:
    p = context.placeholder
    t = context.tables
    metadata = context.metadata
    return _present(
        (
            _query(
                context,
                "type_and_declarator_attributes",
                "attribute",
                f"SELECT name, decoded_value_kind, decoded_value_int, decoded_value_uint, decoded_value_text, decoded_value_json FROM {t.get('attribute', '')} WHERE {context.die} AND name IN ({_placeholders(9, p)}) ORDER BY ordinal LIMIT 1001",
                (*context.die_params, *_TYPE_ATTRIBUTE_NAMES),
                metadata,
            ),
            _query(
                context,
                "name_occurrences",
                "name",
                f"SELECT name, name_kind, attribute_name FROM {t.get('name', '')} WHERE {context.die} ORDER BY ordinal LIMIT 1001",
                context.die_params,
                metadata,
            ),
            _query(
                context,
                "references",
                "reference",
                f"SELECT attribute_name, relation, target_offset, resolution_status FROM {t.get('reference', '')} WHERE {context.die} ORDER BY attribute_name LIMIT 1001",
                context.die_params,
                metadata,
            ),
            _query(
                context,
                "type_reference_resolution",
                "reference",
                f"SELECT attribute_name, target_offset, resolution_status FROM {t.get('reference', '')} WHERE {context.die} AND relation <> {p} ORDER BY attribute_name LIMIT 1001",
                (*context.die_params, "parent"),
                metadata,
            ),
        )
    )


def _evidence_queries(context: _ContractContext) -> tuple[ParameterizedQuery, ...]:
    t = context.tables
    return _present(
        (
            _query(
                context,
                "ranges",
                "range",
                f"SELECT ordinal, start_address, end_address, parser_status FROM {t.get('range', '')} WHERE {context.die} ORDER BY ordinal LIMIT 1001",
                context.die_params,
                context.metadata,
            ),
            _query(
                context,
                "locations",
                "location",
                f"SELECT ordinal, start_address, end_address, expression_json FROM {t.get('location', '')} WHERE {context.die} ORDER BY ordinal LIMIT 1001",
                context.die_params,
                context.metadata,
            ),
            _query(
                context,
                "line_files",
                "line",
                f"SELECT ordinal, entry_kind, source_file, directory, file_index, directory_index, line, address FROM {t.get('line', '')} WHERE {context.unit} ORDER BY entry_kind, ordinal LIMIT 1001",
                context.unit_params,
                {"unit_offset": context.unit_offset},
            ),
            _query(
                context,
                "source_provenance",
                "section",
                f"SELECT section_index, section_name, raw_path, raw_sha256 FROM {t.get('section', '')} WHERE {context.source} ORDER BY section_index LIMIT 1001",
                context.source_params,
                {"unit_offset": context.unit_offset},
            ),
            _query(
                context,
                "raw_section_chunks",
                "raw_chunk",
                f"SELECT section_index, chunk_index, byte_offset, byte_size, raw_sha256 FROM {t.get('raw_chunk', '')} WHERE {context.source} ORDER BY section_index, chunk_index LIMIT 1001",
                context.source_params,
                {"unit_offset": context.unit_offset},
            ),
        )
    )


def _method_queries(context: _ContractContext) -> tuple[ParameterizedQuery, ...]:
    p = context.placeholder
    query = _query(
        context,
        "method_implementation_by_declaration",
        "index",
        f"SELECT unit_offset, die_offset FROM {context.tables.get('index', '')} WHERE {context.source} AND index_type = {p} AND target_offset = {p} ORDER BY unit_offset, die_offset LIMIT 1001",
        (*context.source_params, "method_implementation", context.die_offset),
        {"declaration_offset": context.die_offset},
    )
    return (query,) if query is not None else ()


def field_attribute_query(
    config: DorisConfig,
    source_id: str,
    unit_offset: int,
    die_offsets: tuple[int, ...],
    placeholder: Placeholder,
) -> ParameterizedQuery:
    """Build the bounded field-attribute projection for a field result set."""
    table = doris_table_name(config, "attribute")
    offsets = die_offsets[:1000]
    values = (*offsets, *_FIELD_ATTRIBUTE_NAMES)
    return ParameterizedQuery(
        "field_layout_attributes",
        f"SELECT die_offset, name, decoded_value_kind, decoded_value_int, "
        f"decoded_value_uint, decoded_value_text FROM {table} "
        f"WHERE source_id = {placeholder} AND unit_offset = {placeholder} "
        f"AND die_offset IN ({_placeholders(len(offsets), placeholder) or '-1'}) "
        f"AND name IN ({_placeholders(len(_FIELD_ATTRIBUTE_NAMES), placeholder)}) "
        "ORDER BY die_offset, ordinal LIMIT 1001",
        (source_id, unit_offset, *values),
        {"unit_offset": unit_offset},
    )


def derived_aggregation_queries(
    config: DorisConfig,
    source_id: str,
    unit_offset: int,
    placeholder: Placeholder,
) -> tuple[tuple[ParameterizedQuery, ParameterizedQuery], ...]:
    """Build raw Arrow-reduction and Doris GROUP BY variants for derived counts."""
    result: list[tuple[ParameterizedQuery, ParameterizedQuery]] = []
    for family, column, aggregation in (
        ("die", "tag", "child_tag_counts"),
        ("name", "name", "name_counts"),
    ):
        table = doris_table_name(config, family)
        params = (source_id, unit_offset)
        metadata = {
            "aggregation": aggregation,
            "reducer": "count_by_first_column",
            "parallel_result_sink": True,
            "unit_offset": unit_offset,
        }
        raw = ParameterizedQuery(
            f"client_{aggregation}",
            f"SELECT {column} FROM {table} WHERE source_id = {placeholder} "
            f"AND unit_offset = {placeholder} ORDER BY ordinal LIMIT 100001",
            params,
            {**metadata, "role": "client_reduction", "parallel_result_sink": False},
        )
        server = ParameterizedQuery(
            f"doris_{aggregation}",
            f"SELECT /*+ SET_VAR(enable_parallel_result_sink=true) */ {column}, "
            f"COUNT(*) AS row_count FROM {table} "
            f"WHERE source_id = {placeholder} AND unit_offset = {placeholder} "
            f"GROUP BY {column} ORDER BY {column} LIMIT 100001",
            params,
            {
                **metadata,
                "role": "doris_aggregation",
            },
        )
        result.append((raw, server))
    return tuple(result)


_TYPE_ATTRIBUTE_NAMES = (
    "DW_AT_type",
    "DW_AT_byte_size",
    "DW_AT_encoding",
    "DW_AT_data_member_location",
    "DW_AT_upper_bound",
    "DW_AT_count",
    "DW_AT_lower_bound",
    "DW_AT_declaration",
    "DW_AT_const_value",
)
_FIELD_ATTRIBUTE_NAMES = (
    "DW_AT_data_member_location",
    "DW_AT_byte_size",
    "DW_AT_bit_size",
    "DW_AT_bit_offset",
    "DW_AT_type",
    "DW_AT_upper_bound",
    "DW_AT_count",
    "DW_AT_lower_bound",
    "DW_AT_declaration",
)


def _definition_table(config: DorisConfig) -> str:
    return (
        doris_table_name(config, "index")
        if config.definition_lookup_table is None
        else f"{_identifier(config.database)}.{_identifier(config.definition_lookup_table)}"
    )


def _identifier(value: str) -> str:
    if not value or not all(character.isalnum() or character == "_" for character in value):
        raise ValueError(f"Unsafe Doris identifier: {value!r}")
    return f"`{value}`"


def _placeholders(count: int, placeholder: Placeholder) -> str:
    return ", ".join(placeholder for _ in range(count))
