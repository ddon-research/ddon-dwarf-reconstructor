"""Arrow RecordBatch adapters for Doris DB-API and native readers."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

import pyarrow as pa

from .parquet_rows import schema_for


def cursor_record_batches(
    cursor: object,
    columns: Sequence[str],
    batch_size: int,
    family: str,
) -> tuple[pa.RecordBatch, ...]:
    """Prefer native Arrow, then use bounded ``fetchmany`` arrays for MySQL."""
    fetch_record_batch = getattr(cursor, "fetch_record_batch", None)
    if callable(fetch_record_batch):
        try:
            reader = fetch_record_batch(batch_size)
        except TypeError:
            reader = fetch_record_batch()
        if reader is not None:
            return _bounded_record_batches(_read_record_batches(reader), batch_size)
    fetchmany = getattr(cursor, "fetchmany", None)
    if callable(fetchmany):
        return _fetchmany_record_batches(fetchmany, columns, batch_size, family)
    rows = tuple(cursor.fetchall())  # type: ignore[attr-defined]
    return (_record_batch_from_rows(rows, columns, family),) if rows else ()


def _read_record_batches(reader: object) -> tuple[pa.RecordBatch, ...]:
    if isinstance(reader, pa.RecordBatch):
        return (reader,)
    read_next_batch = getattr(reader, "read_next_batch", None)
    if callable(read_next_batch):
        batches: list[pa.RecordBatch] = []
        while True:
            try:
                batch = read_next_batch()
            except StopIteration:
                break
            if not isinstance(batch, pa.RecordBatch):
                raise TypeError("Doris Arrow reader returned a non-RecordBatch value")
            batches.append(batch)
        return tuple(batches)
    try:
        batches = tuple(reader)  # type: ignore[arg-type]
    except TypeError as error:
        raise TypeError("Doris Arrow cursor returned an unreadable batch stream") from error
    if not all(isinstance(batch, pa.RecordBatch) for batch in batches):
        raise TypeError("Doris Arrow reader returned a non-RecordBatch value")
    return tuple(batches)


def _bounded_record_batches(
    batches: Sequence[pa.RecordBatch],
    batch_size: int,
) -> tuple[pa.RecordBatch, ...]:
    bounded: list[pa.RecordBatch] = []
    for batch in batches:
        bounded.extend(
            batch.slice(start, min(batch_size, batch.num_rows - start))
            for start in range(0, batch.num_rows, batch_size)
        )
    return tuple(bounded)


def _fetchmany_record_batches(
    fetchmany: object,
    columns: Sequence[str],
    batch_size: int,
    family: str,
) -> tuple[pa.RecordBatch, ...]:
    batches: list[pa.RecordBatch] = []
    while True:
        rows = tuple(fetchmany(batch_size))  # type: ignore[operator]
        if not rows:
            return tuple(batches)
        batches.append(_record_batch_from_rows(rows, columns, family))


def _record_batch_from_rows(
    rows: Sequence[Sequence[object]],
    columns: Sequence[str],
    family: str,
) -> pa.RecordBatch:
    family_schema = schema_for(pa, family)
    fields = tuple(family_schema.field(name) for name in columns)
    arrays = [
        pa.array(_column_values(rows, index, field), type=field.type)
        for index, field in enumerate(fields)
    ]
    return pa.RecordBatch.from_arrays(arrays, schema=pa.schema(fields))


def _column_values(
    rows: Sequence[Sequence[object]],
    index: int,
    field: pa.Field,
) -> list[object]:
    values = [row[index] for row in rows]
    if pa.types.is_boolean(field.type):
        return [_boolean_value(value, field.name) for value in values]
    if pa.types.is_integer(field.type):
        return [_integer_value(value, field.name) for value in values]
    if pa.types.is_decimal(field.type):
        return [_decimal_value(value, field.name) for value in values]
    return values


def _boolean_value(value: object, column: str) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, bytes):
        value = value.decode("ascii", errors="strict")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"0", "false"}:
            return False
        if normalized in {"1", "true"}:
            return True
    raise TypeError(f"Cannot convert {value!r} to boolean column {column!r}")


def _integer_value(value: object, column: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError(f"Cannot convert {value!r} to integer column {column!r}")
    if isinstance(value, int):
        return value
    parsed = _decimal_value(value, column)
    if parsed is not None and parsed == parsed.to_integral_value():
        return int(parsed)
    raise TypeError(f"Cannot convert {value!r} to integer column {column!r}")


def _decimal_value(value: object, column: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise _decimal_type_error(value, column)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, bytes):
        value = _decode_decimal_bytes(value, column)
    if isinstance(value, str):
        return _parse_decimal_text(value, column)
    raise _decimal_type_error(value, column)


def _decode_decimal_bytes(value: bytes, column: str) -> str:
    try:
        return value.decode("ascii", errors="strict")
    except UnicodeDecodeError as error:
        raise _decimal_type_error(value, column) from error


def _parse_decimal_text(value: str, column: str) -> Decimal:
    try:
        return Decimal(value.strip())
    except InvalidOperation as error:
        raise _decimal_type_error(value, column) from error


def _decimal_type_error(value: object, column: str) -> TypeError:
    return TypeError(f"Cannot convert {value!r} to decimal column {column!r}")


__all__ = ["cursor_record_batches"]
