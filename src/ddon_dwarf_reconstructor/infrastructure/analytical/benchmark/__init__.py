"""Explicit analytical-store benchmark adapters.

Benchmark implementations live below this package so the normal analytical
store adapters remain independent of measurement and comparison workloads.
Optional Flight SQL imports stay lazy until a benchmark command requests them.
"""

from importlib import import_module
from typing import Any

__all__ = [
    "run_store_benchmark",
    "run_current_doris_benchmark",
    "run_doris_flight_benchmark",
    "run_doris_flight_preflight",
    "write_doris_flight_preflight",
]


_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "run_store_benchmark": (".common.runner", "run_store_benchmark"),
    "run_current_doris_benchmark": (".doris.current", "run_current_doris_benchmark"),
    "run_doris_flight_benchmark": (".flight_sql.runner", "run_doris_flight_benchmark"),
    "run_doris_flight_preflight": (".flight_sql.preflight", "run_doris_flight_preflight"),
    "write_doris_flight_preflight": (
        ".flight_sql.preflight",
        "write_doris_flight_preflight",
    ),
}


def __getattr__(name: str) -> Any:
    """Load benchmark implementations only when their entry point is requested."""
    try:
        module_name, attribute_name = _LAZY_IMPORTS[name]
    except KeyError:
        raise AttributeError(name) from None
    module = import_module(module_name, __name__)
    return getattr(module, attribute_name)
