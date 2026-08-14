"""Typed native Doris Stream Load client with bounded network evidence."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, replace
from enum import StrEnum
from http.client import HTTPConnection, HTTPResponse, HTTPSConnection
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import urljoin, urlparse

if TYPE_CHECKING:
    from .doris import DorisConfig

MAX_DIAGNOSTIC_BYTES = 64 * 1024
CHUNK_BYTES = 1024 * 1024


class StreamLoadState(StrEnum):
    """Explicit outcome states for one labeled Parquet upload."""

    LOADED = "loaded"
    PUBLISH_PENDING = "publish_pending"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class StreamLoadOutcome:
    """Per-file Stream Load evidence, including bounded failure diagnostics."""

    path: Path
    state: StreamLoadState
    label: str | None = None
    http_status: int | None = None
    response: dict[str, object] | None = None
    diagnostics: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "status": self.state.value,
            "label": self.label,
            "http_status": self.http_status,
            "response": self.response or {},
            "diagnostics": self.diagnostics,
        }


class _Connection(Protocol):
    sock: Any

    def putrequest(self, method: str, url: str, *args: Any, **kwargs: Any) -> None: ...

    def putheader(self, header: str | bytes, *values: Any) -> None: ...

    def endheaders(self) -> None: ...

    def send(self, data: bytes) -> None: ...

    def getresponse(self) -> HTTPResponse: ...

    def close(self) -> None: ...


class DorisStreamLoadClient:
    """Upload Parquet files with separate connection, write, and read bounds."""

    def __init__(self, config: DorisConfig) -> None:
        self._config = config

    def load(self, path: Path, table: str, label: str) -> StreamLoadOutcome:
        """Upload one file and classify Doris's publish response explicitly."""
        try:
            return replace(self._load(path, table, label), label=label)
        except Exception as error:
            return StreamLoadOutcome(
                path,
                StreamLoadState.FAILED,
                label=label,
                diagnostics=_bounded_text(error),
            )

    def _load(self, path: Path, table: str, label: str) -> StreamLoadOutcome:
        endpoint = f"{self._config.stream_load_url.rstrip('/')}/api/"
        endpoint += f"{self._config.database}/{table}/_stream_load"
        connection, response = self._send(path, table, endpoint, label)
        try:
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                _read_bounded(response)
                if not location:
                    return StreamLoadOutcome(
                        path,
                        StreamLoadState.FAILED,
                        http_status=response.status,
                        diagnostics="Doris Stream Load redirect did not include a Location header",
                    )
                _close_connection(connection)
                connection, response = self._send(
                    path,
                    table,
                    urljoin(self._config.http_url, location),
                    label,
                )
            body = _read_bounded(response)
            if response.status >= 300:
                return StreamLoadOutcome(
                    path,
                    StreamLoadState.FAILED,
                    http_status=response.status,
                    diagnostics=_bounded_text(f"HTTP {response.status}: {body}"),
                )
            try:
                payload = json.loads(body)
            except json.JSONDecodeError as error:
                return StreamLoadOutcome(
                    path,
                    StreamLoadState.FAILED,
                    http_status=response.status,
                    diagnostics=f"Doris Stream Load returned malformed JSON: {error}",
                )
            if not isinstance(payload, dict):
                return StreamLoadOutcome(
                    path,
                    StreamLoadState.FAILED,
                    http_status=response.status,
                    diagnostics="Doris Stream Load response must be a JSON object",
                )
            status = payload.get("Status")
            if status == "Success":
                state = StreamLoadState.LOADED
            elif status == "Publish Timeout":
                state = StreamLoadState.PUBLISH_PENDING
            else:
                state = StreamLoadState.FAILED
            return StreamLoadOutcome(
                path,
                state,
                http_status=response.status,
                response={str(key): value for key, value in payload.items()},
                diagnostics=(
                    None
                    if state is not StreamLoadState.FAILED
                    else _bounded_text(payload.get("Message", "Doris rejected the upload"))
                ),
            )
        finally:
            _close_connection(connection)

    def _send(
        self,
        path: Path,
        table: str,
        endpoint: str,
        label: str,
    ) -> tuple[_Connection, HTTPResponse]:
        del table
        parsed = urlparse(endpoint)
        connection_type = HTTPSConnection if parsed.scheme == "https" else HTTPConnection
        connection = connection_type(
            parsed.hostname or "127.0.0.1",
            parsed.port,
            timeout=self._config.stream_load_connect_timeout_seconds,
        )
        request_path = parsed.path or "/_stream_load"
        if parsed.query:
            request_path = f"{request_path}?{parsed.query}"
        credentials = base64.b64encode(
            f"{self._config.user}:{self._config.password}".encode()
        ).decode()
        try:
            connection.putrequest("PUT", request_path)
            connection.putheader("Authorization", f"Basic {credentials}")
            connection.putheader("format", "parquet")
            connection.putheader("label", label)
            connection.putheader("strict_mode", "true")
            connection.putheader("max_filter_ratio", "0")
            connection.putheader("Content-Length", str(path.stat().st_size))
            connection.putheader("Expect", "100-continue")
            connection.endheaders()
            _set_socket_timeout(connection, self._config.stream_load_write_timeout_seconds)
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(CHUNK_BYTES), b""):
                    connection.send(chunk)
            _set_socket_timeout(connection, self._config.stream_load_read_timeout_seconds)
            return connection, connection.getresponse()
        except BaseException:
            _close_connection(connection)
            raise


def _set_socket_timeout(connection: _Connection, timeout_seconds: float) -> None:
    socket = connection.sock
    if socket is not None:
        socket.settimeout(timeout_seconds)


def _close_connection(connection: _Connection) -> None:
    try:
        connection.close()
    except Exception:
        return


def _read_bounded(response: HTTPResponse) -> str:
    raw = response.read(MAX_DIAGNOSTIC_BYTES + 1)
    truncated = len(raw) > MAX_DIAGNOSTIC_BYTES
    text = raw[:MAX_DIAGNOSTIC_BYTES].decode("utf-8", errors="replace")
    return _bounded_text(text, truncated=truncated)


def _bounded_text(value: object, *, truncated: bool = False) -> str:
    text = str(value)
    suffix = "...[truncated]"
    if truncated or len(text) > MAX_DIAGNOSTIC_BYTES:
        return text[: MAX_DIAGNOSTIC_BYTES - len(suffix)] + suffix
    return text


__all__ = ["DorisStreamLoadClient", "StreamLoadOutcome", "StreamLoadState"]
