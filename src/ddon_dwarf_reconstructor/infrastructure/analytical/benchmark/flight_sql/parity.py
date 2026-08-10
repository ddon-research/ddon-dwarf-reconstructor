"""Cross-transport parity summaries for the opt-in Doris benchmark."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def compare_transport_reports(
    mysql: Mapping[str, Any], flight: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare strict result digests without retaining result rows in the report."""
    symbols = sorted(set(mysql.get("symbols", {})) & set(flight.get("symbols", {})))
    modes = sorted(set(mysql.get("connection_modes", ())) & set(flight.get("connection_modes", ())))
    comparisons: list[dict[str, Any]] = []
    for symbol in symbols:
        comparisons.extend(_compare_symbol_reports(mysql, flight, symbol, modes))
    mismatches = [item for item in comparisons if item["mismatched"]]
    compared = sum(item["compared"] for item in comparisons)
    matched = sum(item["matched"] for item in comparisons)
    return {
        "status": "observed" if compared and not mismatches else "partial",
        "comparison_basis": "strict result_digest including Python scalar types",
        "compared": compared,
        "matched": matched,
        "mismatched": sum(item["mismatched"] for item in comparisons),
        "categories": comparisons,
    }


def _compare_symbol_reports(
    mysql: Mapping[str, Any],
    flight: Mapping[str, Any],
    symbol: str,
    modes: list[str],
) -> list[dict[str, Any]]:
    mysql_symbol = mysql["symbols"][symbol]
    flight_symbol = flight["symbols"][symbol]
    comparisons: list[dict[str, Any]] = []
    for connection_mode in modes:
        for category in ("definition", "contract", "arrays"):
            comparisons.append(
                _compare_query_category(
                    symbol,
                    connection_mode,
                    category,
                    mysql_symbol[connection_mode].get(category, ()),
                    flight_symbol[connection_mode].get(category, ()),
                )
            )
        comparisons.append(
            _compare_hydration(
                symbol,
                connection_mode,
                mysql_symbol[connection_mode].get("hydration", ()),
                flight_symbol[connection_mode].get("hydration", ()),
            )
        )
    return comparisons


def _compare_query_category(
    symbol: str,
    connection_mode: str,
    category: str,
    mysql_reports: Any,
    flight_reports: Any,
) -> dict[str, Any]:
    mysql = _reports_by_query(mysql_reports)
    flight = _reports_by_query(flight_reports)
    return _compare_maps(symbol, connection_mode, category, mysql, flight)


def _compare_hydration(
    symbol: str,
    connection_mode: str,
    mysql_reports: Any,
    flight_reports: Any,
) -> dict[str, Any]:
    mysql = {
        (item.get("strategy"), item.get("batch_size"), item.get("mode")): item
        for item in mysql_reports
    }
    flight = {
        (item.get("strategy"), item.get("batch_size"), item.get("mode")): item
        for item in flight_reports
    }
    return _compare_maps(symbol, connection_mode, "hydration", mysql, flight)


def _reports_by_query(reports: Any) -> dict[str, Mapping[str, Any]]:
    return {
        str(item["query"]): item
        for item in reports
        if item.get("mode") == "rows" and isinstance(item, Mapping)
    }


def _compare_maps(
    symbol: str,
    connection_mode: str,
    category: str,
    mysql: Mapping[Any, Mapping[str, Any]],
    flight: Mapping[Any, Mapping[str, Any]],
) -> dict[str, Any]:
    mismatches: list[dict[str, Any]] = []
    keys = sorted(set(mysql) & set(flight), key=str)
    for key in keys:
        mysql_report = mysql[key]
        flight_report = flight[key]
        if (
            mysql_report.get("result_digest") != flight_report.get("result_digest")
            or mysql_report.get("matches") != flight_report.get("matches")
            or mysql_report.get("schema") != flight_report.get("schema")
        ):
            mismatches.append(
                {
                    "key": str(key),
                    "mysql_digest": mysql_report.get("result_digest"),
                    "flight_digest": flight_report.get("result_digest"),
                    "mysql_matches": mysql_report.get("matches"),
                    "flight_matches": flight_report.get("matches"),
                    "schema_equal": mysql_report.get("schema") == flight_report.get("schema"),
                }
            )
    return {
        "symbol": symbol,
        "connection_mode": connection_mode,
        "category": category,
        "compared": len(keys),
        "matched": len(keys) - len(mismatches),
        "mismatched": len(mismatches),
        "missing_from_mysql": sorted(set(flight) - set(mysql), key=str),
        "missing_from_flight": sorted(set(mysql) - set(flight), key=str),
        "mismatches": mismatches,
    }
