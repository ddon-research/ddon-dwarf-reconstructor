"""Explicit serving preflight used by the local warehouse operations script."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from ...core.observability import log_exception
from .doris_config import DorisConfig
from .doris_connection import connect_sql
from .doris_index import DorisDwarfIndex
from .doris_store import DorisDwarfStore
from .optional import import_optional

logger = logging.getLogger(__name__)
_FAILURES = (
    ConnectionError,
    OSError,
    ValueError,
    RuntimeError,
    import_optional("pymysql", "analytical").MySQLError,
)


@dataclass(frozen=True)
class ReadinessCheck:
    """One observed readiness dimension; skipped dimensions never imply success."""

    status: str
    details: object = None


def backend_readiness(rows: list[dict[str, Any]]) -> ReadinessCheck:
    """Require live, enabled backends with reported tablets, not just FE SQL."""
    ready = bool(rows) and all(
        str(row.get("Alive", "")).lower() == "true"
        and str(row.get("SystemDecommissioned", "")).lower() == "false"
        and int(row.get("TabletNum", 0)) > 0
        and not row.get("ErrMsg")
        and _backend_enabled(row)
        for row in rows
    )
    return ReadinessCheck("pass" if ready else "fail", rows)


def _backend_enabled(row: dict[str, Any]) -> bool:
    status = json.loads(row.get("Status", "{}"))
    return (
        status.get("isActive") is True
        and status.get("isShutdown") is False
        and status.get("isQueryDisabled") is False
    )


def _backends(connection: Any) -> list[dict[str, Any]]:
    return _rows(connection, "SHOW BACKENDS")


def _rows(connection: Any, statement: str) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(statement)
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def tablet_readiness(rows: list[dict[str, Any]]) -> bool:
    """Require every catalogued tablet healthy; missing totals are unavailable."""
    totals = [row for row in rows if row.get("DbId") == "Total"]
    return (
        len(totals) == 1
        and int(totals[0]["TabletNum"]) > 0
        and all(int(row["TabletNum"]) == int(row["HealthyNum"]) for row in rows)
    )


def _source_check(manifest: Path, config: DorisConfig) -> ReadinessCheck:
    store = DorisDwarfStore.load(manifest, config=config)
    try:
        index = DorisDwarfIndex(store)
        results = {}
        for name in ("cArcLoader01", "rCharacterEditCameraParam", "rGrassWind"):
            result = index.targeted_symbol_search(name)
            results[name] = {
                "status": result.status.value,
                "candidate_found": result.candidate is not None,
                "diagnostics": result.diagnostics,
            }
        ready = all(r["status"] == "complete" and r["candidate_found"] for r in results.values())
        return ReadinessCheck("pass" if ready else "fail", results)
    finally:
        store.close()


def check_serving(manifest: Path, config: DorisConfig) -> dict[str, ReadinessCheck]:
    """Check connection, backend reports, then complete source-bound lookups."""
    checks = dict.fromkeys(
        ("fe_connectivity", "backend_tablet_readiness", "source_bound_queries"),
        ReadinessCheck("not_observed"),
    )
    stage = "fe_connectivity"
    try:
        with connect_sql(config) as connection:
            checks[stage] = ReadinessCheck("pass", config.sql_endpoint)
            stage = "backend_tablet_readiness"
            checks[stage] = backend_readiness(_backends(connection))
            if checks[stage].status == "pass":
                tablets = _rows(connection, "SHOW PROC '/cluster_health/tablet_health'")
                checks[stage] = ReadinessCheck(
                    "pass" if tablet_readiness(tablets) else "fail",
                    {"backends": checks[stage].details, "tablet_health": tablets},
                )
        if checks[stage].status == "pass":
            stage = "source_bound_queries"
            checks[stage] = _source_check(manifest, config)
    except _FAILURES as error:
        log_exception(logger, "doris_readiness_failed", error, stage=stage)
        checks[stage] = ReadinessCheck("fail", {"error_type": type(error).__name__})
    return checks


def main() -> int:
    """Operations adapter; generation continues to use the canonical CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sql-port", type=int, required=True)
    args = parser.parse_args()
    config = replace(
        DorisConfig.from_environment(),
        sql_port=args.sql_port,
        sql_connect_timeout_seconds=5,
        sql_read_timeout_seconds=30,
    )
    checks = check_serving(args.manifest, config)
    print(json.dumps({key: asdict(value) for key, value in checks.items()}, default=str))
    return 0 if all(check.status == "pass" for check in checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
