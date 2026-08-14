"""Small fake DB-API objects shared by Doris statistics tests."""

from __future__ import annotations


class StatisticsCursor:
    """Cursor that records statements without returning rows."""

    description: tuple[tuple[str], ...] = ()

    def __init__(self, connection: StatisticsConnection) -> None:
        self.connection = connection

    def __enter__(self) -> StatisticsCursor:
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        del exc_type, exc_value, traceback

    def execute(self, statement: str, params: object = ()) -> None:
        del params
        self.connection.statements.append(statement)

    def fetchall(self) -> list[tuple[object, ...]]:
        return []


class StatisticsConnection:
    """Connection that supplies the statement-recording fake cursor."""

    def __init__(self) -> None:
        self.statements: list[str] = []

    def cursor(self) -> StatisticsCursor:
        return StatisticsCursor(self)
