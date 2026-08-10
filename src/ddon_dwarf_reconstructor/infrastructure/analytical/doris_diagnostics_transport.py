"""Doris CLI and FE HTTP transports for diagnostic evidence."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from .doris import DorisConfig


@dataclass(frozen=True, slots=True)
class DiagnosticTransportResult:
    """One CLI or HTTP retrieval attempt."""

    status: str
    source: str
    raw_text: str = ""
    payload: object | None = None
    error: str | None = None
    duration_seconds: float = 0.0
    attempts: tuple[dict[str, object], ...] = ()


class DorisDiagnosticTransport:
    """Prefer stateless ``doriscli`` and fall back to FE profile HTTP."""

    def __init__(
        self,
        config: DorisConfig,
        cli_path: Path | None = None,
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds
        self.cli_path = self._discover_cli(cli_path)
        self.cli_version = self._capture_cli_version()

    def descriptor(self) -> dict[str, object]:
        """Return non-secret transport identity and fallback details."""
        return {
            "preferred": "doriscli",
            "cli_path": None if self.cli_path is None else str(self.cli_path),
            "cli_version": self.cli_version,
            "fallback": "pymysql_explain_fe_http_profile",
            "http_url": self.config.http_url,
        }

    def explain(self, sql: str, *, verbose: bool) -> DiagnosticTransportResult:
        """Run one explain statement through the CLI when available."""
        if self.cli_path is None:
            return DiagnosticTransportResult(
                "unavailable", "doriscli", error="doriscli was not discovered"
            )
        statement = f"EXPLAIN VERBOSE {sql}" if verbose else f"EXPLAIN {sql}"
        return self._run_cli(("sql", statement), "explain_verbose" if verbose else "explain")

    def profile(self, query_id: str, *, full: bool) -> DiagnosticTransportResult:
        """Retrieve a profile with CLI-first and FE HTTP fallback behavior."""
        attempts: list[dict[str, object]] = []
        if self.cli_path is not None:
            option = "--full" if full else "--raw"
            result = self._run_cli(("profile", "get", query_id, option), "profile")
            attempts.extend(result.attempts)
            if result.status == "observed":
                return result
        http_result = self._fetch_http_profile(query_id)
        attempts.extend(http_result.attempts)
        return DiagnosticTransportResult(
            http_result.status,
            http_result.source,
            http_result.raw_text,
            http_result.payload,
            http_result.error,
            http_result.duration_seconds,
            tuple(attempts),
        )

    def _run_cli(self, arguments: tuple[str, ...], purpose: str) -> DiagnosticTransportResult:
        if self.cli_path is None:
            return DiagnosticTransportResult("unavailable", "doriscli")
        command = [str(self.cli_path), "--format", "json", *arguments]
        started = perf_counter()
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                env=self._cli_environment(),
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            return self._failed_cli(
                command,
                purpose,
                "blocked",
                f"doriscli timed out after {self.timeout_seconds:.3f}s: {error}",
                started,
            )
        except OSError as error:
            return self._failed_cli(command, purpose, "unavailable", str(error), started)
        attempts: tuple[dict[str, object], ...] = (
            {
                "source": "doriscli",
                "purpose": purpose,
                "command": _safe_command(command),
                "returncode": completed.returncode,
            },
        )
        if completed.returncode != 0:
            return DiagnosticTransportResult(
                "partial",
                "doriscli",
                completed.stdout,
                error=_cli_error(completed.stderr, completed.returncode),
                duration_seconds=perf_counter() - started,
                attempts=attempts,
            )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            return DiagnosticTransportResult(
                "partial",
                "doriscli",
                completed.stdout,
                error=f"doriscli returned malformed JSON: {error}",
                duration_seconds=perf_counter() - started,
                attempts=attempts,
            )
        return DiagnosticTransportResult(
            "observed",
            "doriscli",
            completed.stdout,
            payload,
            duration_seconds=perf_counter() - started,
            attempts=attempts,
        )

    def _fetch_http_profile(self, query_id: str) -> DiagnosticTransportResult:
        attempts: list[dict[str, object]] = []
        last_error = "FE profile endpoint did not return a profile"
        for endpoint in self._profile_endpoints(query_id):
            started = perf_counter()
            request = Request(endpoint, headers={"Authorization": self._basic_auth()})
            try:
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    raw_text = response.read().decode("utf-8", errors="replace")
                    status = int(getattr(response, "status", 200))
                attempts.append({"source": "fe_http", "url": endpoint, "status_code": status})
                if status < 300 and raw_text.strip():
                    return DiagnosticTransportResult(
                        "observed",
                        "fe_http",
                        raw_text,
                        _json_or_text(raw_text),
                        duration_seconds=perf_counter() - started,
                        attempts=tuple(attempts),
                    )
                last_error = f"FE profile endpoint returned HTTP {status}"
            except HTTPError as error:
                attempts.append({"source": "fe_http", "url": endpoint, "status_code": error.code})
                last_error = f"FE profile endpoint returned HTTP {error.code}"
            except (OSError, URLError) as error:
                attempts.append({"source": "fe_http", "url": endpoint, "error": str(error)})
                last_error = str(error)
        return DiagnosticTransportResult(
            "unavailable",
            "fe_http",
            error=last_error,
            attempts=tuple(attempts),
        )

    def _capture_cli_version(self) -> str | None:
        if self.cli_path is None:
            return None
        for command in ((str(self.cli_path), "--version"), (str(self.cli_path), "version")):
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=min(self.timeout_seconds, 10.0),
                    env=self._cli_environment(),
                    check=False,
                )
            except OSError, subprocess.TimeoutExpired:
                continue
            if completed.returncode == 0:
                value = (completed.stdout or completed.stderr).strip()
                if value:
                    return value[:500]
        return None

    def _discover_cli(self, explicit: Path | None) -> Path | None:
        if explicit is not None:
            candidate = explicit.expanduser().resolve()
            return candidate if candidate.is_file() else None
        discovered = shutil.which("doriscli")
        return None if discovered is None else Path(discovered).resolve()

    def _cli_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "DORIS_HOST": self.config.sql_host,
                "DORIS_PORT": str(self.config.sql_port),
                "DORIS_USER": self.config.user,
                "DORIS_PASSWORD": self.config.password,
                "DORIS_DATABASE": self.config.database,
                "DORIS_HTTP_PORT": str(_http_port(self.config.http_url)),
            }
        )
        return environment

    def _profile_endpoints(self, query_id: str) -> tuple[str, ...]:
        base = self.config.http_url.rstrip("/")
        encoded = quote(query_id, safe="")
        return (
            f"{base}/rest/v2/manager/query/profile/text/{encoded}?is_all_node=true",
            f"{base}/api/profile/text/{encoded}",
        )

    def _basic_auth(self) -> str:
        import base64

        token = base64.b64encode(f"{self.config.user}:{self.config.password}".encode()).decode()
        return f"Basic {token}"

    @staticmethod
    def _failed_cli(
        command: list[str],
        purpose: str,
        status: str,
        error: str,
        started: float,
    ) -> DiagnosticTransportResult:
        return DiagnosticTransportResult(
            status,
            "doriscli",
            error=error,
            duration_seconds=perf_counter() - started,
            attempts=(
                {"source": "doriscli", "purpose": purpose, "command": _safe_command(command)},
            ),
        )


def _http_port(url: str) -> int:
    parsed = urlsplit(url)
    if parsed.port is not None:
        return parsed.port
    return 443 if parsed.scheme == "https" else 80


def _json_or_text(raw_text: str) -> object:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return raw_text


def _cli_error(stderr: str, returncode: int) -> str:
    detail = stderr.strip()
    return f"doriscli exited with code {returncode}: {detail[:500]}"


def _safe_command(command: list[str]) -> list[str]:
    return list(command)


__all__ = ["DiagnosticTransportResult", "DorisDiagnosticTransport"]
