"""Unit tests for Flight Compose preflight and benchmark boundaries."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.preflight import (
    run_doris_flight_preflight,
    write_doris_flight_preflight,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.runner import (
    _run_transport,
    run_doris_flight_benchmark,
)
from ddon_dwarf_reconstructor.infrastructure.analytical.doris import DorisConfig

pytestmark = [pytest.mark.unit, pytest.mark.functional]


def test_flight_preflight_records_hashes_endpoints_and_startup_markers(tmp_path: Path) -> None:
    compose_root = tmp_path / "ops" / "analytical-dwarf"
    compose_root.mkdir(parents=True)
    (compose_root / "compose.yaml").write_text("base", encoding="utf-8")
    (compose_root / "compose.flight.yaml").write_text("overlay", encoding="utf-8")
    compose_results = [
        SimpleNamespace(returncode=0, stdout="rendered compose", stderr=""),
        SimpleNamespace(
            returncode=0,
            stdout="doris-fe | Flight SQL started\ndoris-be | Flight SQL started",
            stderr="",
        ),
    ]
    socket_connection = MagicMock()
    config = DorisConfig(
        flight_sql_uri="grpc://fe.example:8070",
        flight_sql_fe_public_host="fe.example",
        flight_sql_public_host="be.example",
        flight_sql_public_port=8050,
    )

    with (
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.preflight.subprocess.run",
            side_effect=compose_results,
        ),
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.preflight.socket.create_connection",
            return_value=socket_connection,
        ) as create_connection,
    ):
        report = run_doris_flight_preflight(config, repository_root=tmp_path)

    assert report["status"] == "observed"
    assert report["compose"]["rendered"]["status"] == "observed"
    assert report["compose"]["rendered"]["sha256"]
    assert all(item["status"] == "observed" for item in report["compose"]["files"])
    assert report["fe_public_endpoint"]["status"] == "observed"
    assert report["startup_logs"]["markers"] == {"doris-fe": True, "doris-be": True}
    assert create_connection.call_count == 3


def test_local_flight_preflight_checks_the_direct_be_mapping(tmp_path: Path) -> None:
    compose_root = tmp_path / "ops" / "analytical-dwarf"
    compose_root.mkdir(parents=True)
    (compose_root / "compose.yaml").write_text("base", encoding="utf-8")
    (compose_root / "compose.flight.yaml").write_text("overlay", encoding="utf-8")
    compose_results = [
        SimpleNamespace(returncode=0, stdout="rendered compose", stderr=""),
        SimpleNamespace(
            returncode=0,
            stdout="doris-fe | Arrow Flight SQL service is started\n"
            "doris-be | Arrow Flight Service bind to host",
            stderr="",
        ),
    ]

    with (
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.preflight.subprocess.run",
            side_effect=compose_results,
        ),
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.preflight.socket.create_connection",
            return_value=MagicMock(),
        ) as create_connection,
    ):
        report = run_doris_flight_preflight(
            DorisConfig(flight_sql_fe_public_host="127.0.0.1"), repository_root=tmp_path
        )

    assert report["be_public_endpoint"]["status"] == "observed"
    assert report["fe_public_endpoint"]["status"] == "observed"
    assert report["be_public_endpoint"]["host"] == "127.0.0.1"
    assert report["be_public_endpoint"]["source"] == "local direct Compose mapping"
    assert create_connection.call_count == 3


def test_flight_preflight_reports_missing_remote_route_and_docker(tmp_path: Path) -> None:
    config = DorisConfig(flight_sql_host="remote.example")
    with (
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.preflight.subprocess.run",
            side_effect=FileNotFoundError,
        ),
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.preflight.socket.create_connection",
            side_effect=OSError("unreachable"),
        ),
    ):
        report = run_doris_flight_preflight(config, repository_root=tmp_path)

    assert report["status"] == "blocked"
    assert report["compose"]["rendered"]["status"] == "blocked"
    assert report["fe_endpoint"]["status"] == "blocked"
    assert report["be_public_endpoint"]["status"] == "blocked"
    assert report["startup_logs"]["status"] == "blocked"


def test_flight_preflight_handles_invalid_uri_and_unreachable_endpoints(tmp_path: Path) -> None:
    compose_root = tmp_path / "ops" / "analytical-dwarf"
    compose_root.mkdir(parents=True)
    (compose_root / "compose.yaml").write_text("base", encoding="utf-8")
    (compose_root / "compose.flight.yaml").write_text("overlay", encoding="utf-8")
    compose_result = SimpleNamespace(returncode=0, stdout="", stderr="")
    config = DorisConfig(flight_sql_uri="grpc://", flight_sql_public_host="be.example")

    with (
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.preflight.subprocess.run",
            return_value=compose_result,
        ),
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.preflight.socket.create_connection",
            side_effect=OSError("connection refused"),
        ),
    ):
        report = run_doris_flight_preflight(config, repository_root=tmp_path)

    assert report["status"] == "blocked"
    assert report["fe_endpoint"]["status"] == "blocked"
    assert report["be_public_endpoint"]["status"] == "blocked"
    assert report["startup_logs"]["status"] == "not_observed"


def test_flight_preflight_report_writer_is_atomic(tmp_path: Path) -> None:
    target = tmp_path / "evidence" / "preflight.json"
    report = {"status": "not_observed"}

    written = write_doris_flight_preflight(target, report)

    assert written == target.resolve()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["report_path"] == str(target.resolve())
    assert not target.with_suffix(".json.partial").exists()


def test_flight_preflight_timeout_is_structured() -> None:
    from ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.preflight import (
        _run_compose,
    )

    with patch(
        "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.preflight.subprocess.run",
        side_effect=subprocess.TimeoutExpired("docker", 1),
    ):
        result = _run_compose(Path("."), (Path("compose.yaml"),), ("config",), 1.0)

    assert result == (None, "", "docker compose command timed out")


def test_flight_benchmark_blocks_incomplete_manifest_and_publishes_report(tmp_path: Path) -> None:
    manifest = SimpleNamespace(status="partial", source_identity=SimpleNamespace(sha256="a" * 64))
    with patch(
        "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.runner.load_manifest",
        return_value=manifest,
    ):
        report = run_doris_flight_benchmark(
            tmp_path / "manifest.json",
            tmp_path / "report",
            config=DorisConfig(),
            symbols=("rLayout",),
            iterations=1,
        )

    assert report["status"] == "blocked"
    assert report["manifest_status"] == "partial"
    assert Path(report["report_path"]).is_file()


def test_flight_benchmark_records_unavailable_transport_without_fallback(tmp_path: Path) -> None:
    manifest = SimpleNamespace(status="complete", source_identity=SimpleNamespace(sha256="a" * 64))
    with (
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.runner.load_manifest",
            return_value=manifest,
        ),
        patch(
            "ddon_dwarf_reconstructor.infrastructure.analytical.benchmark.flight_sql.runner.DorisFlightSqlClient",
            side_effect=RuntimeError("listener unavailable"),
        ),
    ):
        report = run_doris_flight_benchmark(
            tmp_path / "manifest.json",
            tmp_path / "report",
            config=DorisConfig(),
            symbols=("rLayout",),
            iterations=1,
            include_mysql=False,
        )

    assert report["status"] == "blocked"
    assert report["flight_sql"]["status"] == "blocked"
    assert "%s" not in report["flight_sql"].get("reason", "")


def test_transport_boundary_returns_blocked_for_external_connection_errors() -> None:
    manifest = SimpleNamespace(source_identity=SimpleNamespace(sha256="a" * 64))

    class _BrokenClient:
        def __enter__(self) -> _BrokenClient:
            raise ConnectionError("offline")

        def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
            return None

        def open(self) -> _BrokenClient:
            return self

        def close(self) -> None:
            return None

        def cursor(self) -> object:
            raise AssertionError("cursor must not be reached")

    report = _run_transport(
        _BrokenClient(),
        DorisConfig(),
        manifest,
        ("rLayout",),
        1,
        "?",
        ("rows",),
    )

    assert report["status"] == "blocked"
    assert "ConnectionError" in report["reason"]
