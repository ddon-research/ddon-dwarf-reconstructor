"""Explicit Compose, endpoint, and startup-log checks for Flight SQL evidence."""

from __future__ import annotations

import hashlib
import json
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlparse

from ...doris import DorisConfig


def run_doris_flight_preflight(
    config: DorisConfig,
    *,
    repository_root: Path | None = None,
    timeout_seconds: float = 3.0,
) -> dict[str, Any]:
    """Check the opt-in Compose overlay and both advertised Flight endpoints."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    root = repository_root or _repository_root()
    compose_files = _compose_files(root)
    report: dict[str, Any] = {
        "status": "not_observed",
        "generated_at": datetime.now().astimezone().isoformat(),
        "config": {
            "flight_sql_host": config.flight_sql_host,
            "flight_sql_port": config.flight_sql_port,
            "flight_sql_uri": config.flight_sql_uri,
            "flight_sql_fe_public_host": config.flight_sql_fe_public_host,
            "flight_sql_public_host": config.flight_sql_public_host,
            "flight_sql_public_port": config.flight_sql_public_port,
        },
        "compose": {
            "files": _file_hashes(compose_files),
            "rendered": _render_compose(root, compose_files, timeout_seconds),
        },
    }
    try:
        endpoint_host, endpoint_port = _flight_endpoint(config)
    except ValueError as error:
        report["fe_endpoint"] = {"status": "blocked", "reason": str(error)}
    else:
        report["fe_endpoint"] = _check_endpoint(endpoint_host, endpoint_port, timeout_seconds)
    report["fe_public_endpoint"] = _check_fe_public_endpoint(config, timeout_seconds)
    report["be_public_endpoint"] = _check_public_endpoint(config, timeout_seconds)
    report["startup_logs"] = _check_startup_logs(root, compose_files, timeout_seconds)
    report["status"] = _overall_status(report)
    return report


def write_doris_flight_preflight(path: Path, report: dict[str, Any]) -> Path:
    """Atomically write a bounded preflight report outside the source tree."""
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    report["report_path"] = str(path)
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=True, sort_keys=True, indent=2)
        stream.write("\n")
        stream.flush()
    temporary.replace(path)
    return path


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _compose_files(root: Path) -> tuple[Path, ...]:
    compose_root = root / "ops" / "analytical-dwarf"
    return (compose_root / "compose.yaml", compose_root / "compose.flight.yaml")


def _file_hashes(paths: tuple[Path, ...]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for path in paths:
        entry = {"path": str(path.resolve())}
        if path.is_file():
            entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            entry["status"] = "observed"
        else:
            entry["sha256"] = "unavailable"
            entry["status"] = "blocked"
        result.append(entry)
    return result


def _compose_command(files: tuple[Path, ...], arguments: tuple[str, ...]) -> list[str]:
    command = ["docker", "compose"]
    for path in files:
        command.extend(("--file", str(path)))
    command.extend(arguments)
    return command


def _run_compose(
    root: Path,
    files: tuple[Path, ...],
    arguments: tuple[str, ...],
    timeout_seconds: float,
) -> tuple[int | None, str, str]:
    try:
        completed = subprocess.run(
            _compose_command(files, arguments),
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return None, "", "docker executable is unavailable"
    except subprocess.TimeoutExpired:
        return None, "", "docker compose command timed out"
    return completed.returncode, completed.stdout, completed.stderr


def _render_compose(root: Path, files: tuple[Path, ...], timeout_seconds: float) -> dict[str, Any]:
    return_code, output, error = _run_compose(root, files, ("config",), timeout_seconds)
    if return_code != 0:
        return {"status": "blocked", "reason": _bounded_error(error or output)}
    return {
        "status": "observed",
        "sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
        "bytes": len(output.encode("utf-8")),
    }


def _check_startup_logs(
    root: Path,
    files: tuple[Path, ...],
    timeout_seconds: float,
) -> dict[str, Any]:
    return_code, output, error = _run_compose(
        root,
        files,
        ("logs", "--no-color", "--tail", "200", "doris-fe", "doris-be"),
        timeout_seconds,
    )
    if return_code != 0:
        return {"status": "blocked", "reason": _bounded_error(error or output)}
    lines = output.casefold().splitlines()
    markers = {
        service: any(
            "flight" in line or "arrow_flight_sql_port" in line
            for line in lines
            if service in line or f"{service.removeprefix('doris-')} |" in line
        )
        for service in ("doris-fe", "doris-be")
    }
    status = "observed" if all(markers.values()) else "not_observed"
    return {
        "status": status,
        "markers": markers,
        "sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
        "line_count": len(output.splitlines()),
        "reason": None
        if status == "observed"
        else "Flight startup marker was not found for both services.",
    }


def _flight_endpoint(config: DorisConfig) -> tuple[str, int]:
    if config.flight_sql_uri is None:
        return config.flight_sql_host, config.flight_sql_port
    parsed = urlparse(config.flight_sql_uri)
    if parsed.hostname is None:
        raise ValueError(f"Flight SQL URI has no hostname: {config.flight_sql_uri!r}")
    return parsed.hostname, parsed.port or config.flight_sql_port


def _check_public_endpoint(config: DorisConfig, timeout_seconds: float) -> dict[str, Any]:
    if config.flight_sql_public_host is None:
        try:
            endpoint_host, _ = _flight_endpoint(config)
        except ValueError as error:
            return {"status": "blocked", "reason": str(error)}
        if _is_local_host(endpoint_host):
            result = _check_endpoint("127.0.0.1", config.flight_sql_public_port, timeout_seconds)
            result["source"] = "local direct Compose mapping"
            return result
        return {
            "status": "blocked",
            "reason": "Set DDON_DORIS_FLIGHT_SQL_PUBLIC_HOST to validate the BE DoGet route.",
        }
    return _check_endpoint(
        config.flight_sql_public_host,
        config.flight_sql_public_port,
        timeout_seconds,
    )


def _check_fe_public_endpoint(config: DorisConfig, timeout_seconds: float) -> dict[str, Any]:
    if config.flight_sql_fe_public_host is None:
        return {
            "status": "not_observed",
            "reason": (
                "Set DDON_DORIS_FLIGHT_SQL_FE_PUBLIC_HOST to validate the FE address "
                "returned for local Flight results."
            ),
        }
    return _check_endpoint(
        config.flight_sql_fe_public_host,
        config.flight_sql_port,
        timeout_seconds,
    )


def _check_endpoint(host: str, port: int, timeout_seconds: float) -> dict[str, Any]:
    started = perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            pass
    except OSError as error:
        return {
            "status": "blocked",
            "host": host,
            "port": port,
            "latency_seconds": perf_counter() - started,
            "reason": f"{type(error).__name__}: {error}",
        }
    return {
        "status": "observed",
        "host": host,
        "port": port,
        "latency_seconds": perf_counter() - started,
    }


def _is_local_host(host: str) -> bool:
    return host.casefold() in {"localhost", "127.0.0.1", "::1"} or host.startswith("127.")


def _overall_status(report: dict[str, Any]) -> str:
    statuses = [
        report["compose"]["rendered"]["status"],
        report["fe_endpoint"]["status"],
        report["fe_public_endpoint"]["status"],
        report["be_public_endpoint"]["status"],
        report["startup_logs"]["status"],
    ]
    if "blocked" in statuses:
        return "blocked"
    if "not_observed" in statuses:
        return "not_observed"
    return "observed"


def _bounded_error(value: str) -> str:
    return " ".join(value.split())[:500] or "docker compose returned no diagnostic"
