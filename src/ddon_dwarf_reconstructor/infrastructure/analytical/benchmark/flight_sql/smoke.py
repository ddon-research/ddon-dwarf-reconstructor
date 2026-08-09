"""Compatibility probes for the opt-in Doris Flight SQL benchmark."""

from __future__ import annotations

from typing import Any

from .results import FetchMode, QueryClient, run_query_once, run_query_with_metrics
from .specs import ParameterizedQuery


def probe_parameter_binding(client: QueryClient) -> dict[str, Any]:
    """Check the required qmark query protocol without permitting a fallback."""
    spec = ParameterizedQuery(
        "flight_parameter_binding_probe",
        "SELECT ? AS value",
        (1,),
        {"probe": "qmark", "fallback": "none"},
    )
    try:
        result = run_query_once(client, spec, "rows")
    except Exception as error:
        return {
            "status": "blocked",
            "query": spec.name,
            "placeholder": "?",
            "reason": f"{type(error).__name__}: {error}",
            "fallback": "none",
        }
    return {
        "status": "observed",
        "query": spec.name,
        "placeholder": "?",
        "result": result.report,
        "fallback": "none",
    }


def run_transport_smoke(client: QueryClient, iterations: int) -> dict[str, Any]:
    """Measure no-parameter transport modes after a binding incompatibility.

    Connection establishment is deliberately sampled once here.  ADBC opens
    a fresh Flight connection for every ``cold`` query, so applying the full
    benchmark's cold/reused matrix to this diagnostic would spend most of the
    smoke run reconnecting after the known protocol failure.
    """
    client.close()
    client.open()
    spec = ParameterizedQuery(
        "flight_transport_smoke",
        "SELECT 1 AS value",
        (),
        {"probe": "unparameterized_transport_only", "fallback": "none"},
    )
    reports: list[dict[str, Any]] = []
    modes: tuple[FetchMode, ...] = ("rows", "arrow_table", "record_batches", "reduce")
    reports.extend(
        run_query_with_metrics(client, spec, mode, iterations, "reused").report for mode in modes
    )
    reports.append(run_query_once(client, spec, "rows", "cold").report)
    return {
        "status": "observed",
        "query": spec.name,
        "fallback": "none",
        "reused_modes": modes,
        "cold_connection_modes": ("rows",),
        "modes": reports,
    }
