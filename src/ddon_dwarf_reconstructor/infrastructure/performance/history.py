"""Versioned SQLite storage for historical performance summaries."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ...domain.models.performance import EvidenceStatus, RunSummary

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class HistoryRow:
    """Flattened run record used by comparison and static exporters."""

    run_id: str
    workload: str
    state: str
    status: str
    started_at: str
    duration_seconds: float | None
    return_code: int | None
    git_revision: str
    git_dirty: bool | None
    python_version: str
    platform_name: str
    machine_profile: str
    source_identity: str | None
    configuration_fingerprint: str
    profiler_mode: str
    manifest_path: str | None
    metrics: dict[str, dict[str, object]]
    method_metrics: tuple[dict[str, object], ...]
    artifacts: tuple[dict[str, object], ...]

    def to_dict(self) -> dict[str, object]:
        """Return an export-ready row with stable keys."""
        return {
            "run_id": self.run_id,
            "workload": self.workload,
            "state": self.state,
            "status": self.status,
            "started_at": self.started_at,
            "duration_seconds": self.duration_seconds,
            "return_code": self.return_code,
            "git_revision": self.git_revision,
            "git_dirty": self.git_dirty,
            "python_version": self.python_version,
            "platform": self.platform_name,
            "machine_profile": self.machine_profile,
            "source_identity": self.source_identity,
            "configuration_fingerprint": self.configuration_fingerprint,
            "profiler_mode": self.profiler_mode,
            "manifest_path": self.manifest_path,
            "metrics": self.metrics,
            "method_metrics": list(self.method_metrics),
            "artifacts": list(self.artifacts),
        }


class HistoryStore:
    """Create, validate, and update the tracked benchmark ledger."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        """Create the v1 schema or reject an unsupported existing schema."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            self._create_schema(connection)
            version = connection.execute(
                "SELECT value FROM schema_meta WHERE key = 'schema_version'"
            ).fetchone()
            if version is None or int(version[0]) != SCHEMA_VERSION:
                raise ValueError(f"unsupported performance history schema: {version}")

    def integrity_check(self) -> str:
        """Run SQLite's bounded integrity check and return its result."""
        self.initialize()
        with self._connect() as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
        return str(result[0]) if result else "unavailable"

    def record(self, summary: RunSummary) -> None:
        """Insert or replace one summary and all of its child evidence rows."""
        self.initialize()
        with self._connect() as connection:
            connection.execute("BEGIN")
            self._delete_children(connection, summary.run_id)
            self._insert_run(connection, summary)
            self._insert_metrics(connection, summary)
            self._insert_methods(connection, summary)
            self._insert_artifacts(connection, summary)
            connection.commit()

    def rows(self, workload: str | None = None) -> tuple[HistoryRow, ...]:
        """Load deterministic rows, optionally restricted to one workload."""
        self.initialize()
        with self._connect() as connection:
            query = "SELECT * FROM runs"
            parameters: tuple[object, ...] = ()
            if workload:
                query += " WHERE workload = ?"
                parameters = (workload,)
            query += " ORDER BY started_at, run_id"
            runs = connection.execute(query, parameters).fetchall()
            return tuple(self._row(connection, run) for run in runs)

    def compare(
        self, *, workload: str | None = None, run_id: str | None = None
    ) -> dict[str, object]:
        """Compare the latest compatible pair without mixing evidence conditions."""
        candidates = list(self.rows(workload))
        candidate = _select_candidate(candidates, run_id)
        if candidate is None:
            return {"status": EvidenceStatus.NOT_OBSERVED.value, "reason": "no runs recorded"}
        comparable = [row for row in candidates if _comparable(row, candidate)]
        baseline = comparable[-2] if len(comparable) >= 2 else None
        return _comparison_payload(baseline, candidate)

    def export_payload(self, workload: str | None = None) -> dict[str, object]:
        """Return the stable JSON payload used by all static exports."""
        rows = self.rows(workload)
        latest = _latest_baselines(rows)
        return {
            "schema_version": str(SCHEMA_VERSION),
            "runs": [row.to_dict() for row in rows],
            "latest_baselines": [row.to_dict() for row in latest],
        }

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        HistoryStore._create_tables(connection)
        _ensure_method_cpu_percent(connection)
        _record_schema_meta(connection)

    @staticmethod
    def _create_tables(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                workload TEXT NOT NULL,
                cold_warm TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                duration_seconds REAL,
                return_code INTEGER,
                git_revision TEXT NOT NULL,
                git_dirty INTEGER,
                python_version TEXT NOT NULL,
                platform_name TEXT NOT NULL,
                machine_profile TEXT NOT NULL,
                source_identity TEXT,
                configuration_fingerprint TEXT NOT NULL,
                profiler_mode TEXT NOT NULL,
                manifest_path TEXT,
                diagnostics_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS metrics (
                run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                value_type TEXT NOT NULL,
                value_integer INTEGER,
                value_real REAL,
                value_text TEXT,
                unit TEXT NOT NULL,
                status TEXT NOT NULL,
                detail TEXT NOT NULL,
                PRIMARY KEY (run_id, name)
            );
            CREATE TABLE IF NOT EXISTS method_metrics (
                run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
                profiler TEXT NOT NULL,
                rank INTEGER NOT NULL,
                name TEXT NOT NULL,
                file TEXT,
                line INTEGER,
                total_seconds REAL,
                self_seconds REAL,
                call_count INTEGER,
                memory_bytes INTEGER,
                cpu_percent REAL,
                PRIMARY KEY (run_id, profiler, rank)
            );
            CREATE TABLE IF NOT EXISTS artifacts (
                run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
                profiler TEXT NOT NULL,
                format TEXT NOT NULL,
                path TEXT,
                size INTEGER,
                sha256 TEXT,
                tool_version TEXT NOT NULL,
                status TEXT NOT NULL,
                detail TEXT NOT NULL,
                PRIMARY KEY (run_id, profiler, format)
            );
            CREATE INDEX IF NOT EXISTS idx_runs_comparison
                ON runs(workload, cold_warm, source_identity, python_version,
                        platform_name, machine_profile, configuration_fingerprint, profiler_mode);
            CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(name);
            """
        )

    @staticmethod
    def _delete_children(connection: sqlite3.Connection, run_id: str) -> None:
        for table in ("metrics", "method_metrics", "artifacts"):
            connection.execute(f"DELETE FROM {table} WHERE run_id = ?", (run_id,))

    @staticmethod
    def _insert_run(connection: sqlite3.Connection, summary: RunSummary) -> None:
        connection.execute(
            """
            INSERT OR REPLACE INTO runs(
                run_id, workload, cold_warm, status, started_at, duration_seconds,
                return_code, git_revision, git_dirty, python_version, platform_name,
                machine_profile, source_identity, configuration_fingerprint,
                profiler_mode, manifest_path, diagnostics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                summary.run_id,
                summary.workload.name,
                summary.workload.state.value,
                summary.status.value,
                summary.started_at,
                summary.duration_seconds,
                summary.return_code,
                summary.git_revision,
                _bool_int(summary.git_dirty),
                summary.python_version,
                summary.platform_name,
                summary.machine_profile,
                summary.source_identity,
                summary.workload.configuration_fingerprint,
                summary.profiler_mode,
                _path_text(summary.manifest_path),
                json.dumps(list(summary.diagnostics), sort_keys=True),
            ),
        )

    @staticmethod
    def _insert_metrics(connection: sqlite3.Connection, summary: RunSummary) -> None:
        for metric in summary.metrics:
            value_type, value_integer, value_real, value_text = _typed_value(metric.value)
            connection.execute(
                "INSERT INTO metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    summary.run_id,
                    metric.name,
                    value_type,
                    value_integer,
                    value_real,
                    value_text,
                    metric.unit,
                    metric.status.value,
                    metric.detail,
                ),
            )

    @staticmethod
    def _insert_methods(connection: sqlite3.Connection, summary: RunSummary) -> None:
        for item in summary.method_summaries:
            connection.execute(
                "INSERT INTO method_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    summary.run_id,
                    item.profiler,
                    item.rank,
                    item.name,
                    item.file,
                    item.line,
                    item.total_seconds,
                    item.self_seconds,
                    item.call_count,
                    item.memory_bytes,
                    item.cpu_percent,
                ),
            )

    @staticmethod
    def _insert_artifacts(connection: sqlite3.Connection, summary: RunSummary) -> None:
        for item in summary.artifacts:
            connection.execute(
                "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    summary.run_id,
                    item.profiler,
                    item.format,
                    _path_text(item.path),
                    item.size,
                    item.sha256,
                    item.tool_version,
                    item.status.value,
                    item.detail,
                ),
            )

    @classmethod
    def _row(cls, connection: sqlite3.Connection, run: sqlite3.Row) -> HistoryRow:
        run_id = str(run["run_id"])
        metrics = {
            str(item["name"]): {
                "value": _restore_value(item),
                "unit": item["unit"],
                "status": item["status"],
                "detail": item["detail"],
            }
            for item in connection.execute(
                "SELECT * FROM metrics WHERE run_id = ? ORDER BY name", (run_id,)
            )
        }
        methods = tuple(
            dict(item)
            for item in connection.execute(
                "SELECT profiler, rank, name, file, line, total_seconds, self_seconds, call_count, memory_bytes, cpu_percent "
                "FROM method_metrics WHERE run_id = ? ORDER BY profiler, rank",
                (run_id,),
            )
        )
        artifacts = tuple(
            dict(item)
            for item in connection.execute(
                "SELECT profiler, format, path, size, sha256, tool_version, status, detail "
                "FROM artifacts WHERE run_id = ? ORDER BY profiler, format",
                (run_id,),
            )
        )
        return HistoryRow(
            run_id=run_id,
            workload=str(run["workload"]),
            state=str(run["cold_warm"]),
            status=str(run["status"]),
            started_at=str(run["started_at"]),
            duration_seconds=run["duration_seconds"],
            return_code=run["return_code"],
            git_revision=str(run["git_revision"]),
            git_dirty=_restore_bool(run["git_dirty"]),
            python_version=str(run["python_version"]),
            platform_name=str(run["platform_name"]),
            machine_profile=str(run["machine_profile"]),
            source_identity=run["source_identity"],
            configuration_fingerprint=str(run["configuration_fingerprint"]),
            profiler_mode=str(run["profiler_mode"]),
            manifest_path=run["manifest_path"],
            metrics=metrics,
            method_metrics=methods,
            artifacts=artifacts,
        )


def _ensure_method_cpu_percent(connection: sqlite3.Connection) -> None:
    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(method_metrics)")}
    if "cpu_percent" in columns:
        return
    connection.execute("ALTER TABLE method_metrics ADD COLUMN cpu_percent REAL")
    connection.execute(
        "UPDATE method_metrics SET cpu_percent = total_seconds, total_seconds = NULL "
        "WHERE profiler = 'scalene'"
    )


def _record_schema_meta(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    connection.execute(
        "INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('migration', ?)",
        ("initial-v1",),
    )
    connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _select_candidate(rows: list[HistoryRow], run_id: str | None) -> HistoryRow | None:
    if run_id:
        return next((row for row in rows if row.run_id == run_id), None)
    return rows[-1] if rows else None


def _comparison_payload(baseline: HistoryRow | None, candidate: HistoryRow) -> dict[str, object]:
    return {
        "status": EvidenceStatus.OBSERVED.value if baseline else EvidenceStatus.NOT_OBSERVED.value,
        "baseline": None if baseline is None else baseline.to_dict(),
        "candidate": candidate.to_dict(),
        "deltas": _deltas(baseline, candidate),
        "comparison_key": _comparison_key(candidate),
    }


def _typed_value(value: object) -> tuple[str, int | None, float | None, str | None]:
    if value is None:
        return "null", None, None, None
    if isinstance(value, bool):
        return "int", int(value), None, None
    if isinstance(value, int):
        return "int", value, None, None
    if isinstance(value, float):
        return "float", None, value, None
    return "text", None, None, str(value)


def _restore_value(row: sqlite3.Row) -> object:
    value_type = row["value_type"]
    if value_type == "int":
        return row["value_integer"]
    if value_type == "float":
        return row["value_real"]
    return row["value_text"]


def _bool_int(value: bool | None) -> int | None:
    return None if value is None else int(value)


def _restore_bool(value: object) -> bool | None:
    return None if value is None else bool(value)


def _path_text(value: Path | None) -> str | None:
    return None if value is None else str(value)


def _comparison_key(row: HistoryRow) -> dict[str, str | None]:
    return {
        "workload": row.workload,
        "state": row.state,
        "source_identity": row.source_identity,
        "python_version": row.python_version,
        "platform": row.platform_name,
        "machine_profile": row.machine_profile,
        "configuration_fingerprint": row.configuration_fingerprint,
        "profiler_mode": row.profiler_mode,
    }


def _comparable(left: HistoryRow, right: HistoryRow) -> bool:
    return _comparison_key(left) == _comparison_key(right)


def _deltas(baseline: HistoryRow | None, candidate: HistoryRow) -> dict[str, float | int]:
    if baseline is None:
        return {}
    result: dict[str, float | int] = {}
    for name, metric in candidate.metrics.items():
        old = baseline.metrics.get(name, {}).get("value")
        new = metric.get("value")
        if isinstance(old, (int, float)) and isinstance(new, (int, float)):
            result[name] = new - old
    return result


def _latest_baselines(rows: tuple[HistoryRow, ...]) -> tuple[HistoryRow, ...]:
    latest: dict[tuple[str, ...], HistoryRow] = {}
    for row in rows:
        key = tuple(str(value) for value in _comparison_key(row).values())
        latest[key] = row
    return tuple(
        sorted(latest.values(), key=lambda item: (item.workload, item.state, item.profiler_mode))
    )


__all__ = ["HistoryRow", "HistoryStore", "SCHEMA_VERSION"]
