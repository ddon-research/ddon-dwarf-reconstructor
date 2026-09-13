"""Run the pinned document converters used by the Docker build."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .source_manifest import SourceSpec

_CONVERTER_TIMEOUT_SECONDS = 120.0
_MAX_DIAGNOSTIC_BYTES = 8 * 1024


class ConversionError(RuntimeError):
    """Raised when an external source converter is unavailable or fails."""


def _tool_path(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise ConversionError(
            f"Required converter {name!r} was not found. "
            "Run the Docker Compose build or install the converter in the active environment."
        )
    return path


def _diagnostic(path: Path) -> str:
    """Read only the bounded prefix used in an external-tool error."""
    content = path.read_bytes()[: _MAX_DIAGNOSTIC_BYTES + 1]
    text = content.decode("utf-8", errors="replace").strip()
    if len(content) > _MAX_DIAGNOSTIC_BYTES:
        return f"{text[:_MAX_DIAGNOSTIC_BYTES]}... [truncated]"
    return text


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    output_path: Path | None = None,
    timeout: float = _CONVERTER_TIMEOUT_SECONDS,
) -> None:
    """Run one converter with bounded diagnostics and a finite lifetime.

    Converter stdout is streamed to a temporary file. When ``output_path`` is
    supplied, it is atomically moved into place only after the process succeeds.
    This keeps a previous intermediate available when a converter fails.
    """
    if timeout <= 0:
        raise ConversionError(f"Converter timeout must be positive, got {timeout}")
    run_dir = cwd if cwd is not None else Path.cwd()
    run_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".converter-run-", dir=run_dir) as temporary_dir:
        temporary_root = Path(temporary_dir)
        stdout_path = temporary_root / "stdout"
        stderr_path = temporary_root / "stderr"
        try:
            with (
                stdout_path.open("wb") as stdout,
                stderr_path.open("wb") as stderr,
            ):
                process = subprocess.Popen(
                    command,
                    cwd=cwd,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                )
                try:
                    returncode = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired as exc:
                    process.kill()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired as cleanup_error:
                        raise ConversionError(
                            f"Converter {' '.join(command)!r} did not terminate after timeout"
                        ) from cleanup_error
                    raise ConversionError(
                        f"Converter {' '.join(command)!r} timed out after {timeout:g}s"
                    ) from exc
        except OSError as exc:
            raise ConversionError(f"Unable to start converter {command[0]!r}: {exc}") from exc
        if returncode != 0:
            detail = _diagnostic(stderr_path) or _diagnostic(stdout_path)
            raise ConversionError(
                f"Converter {' '.join(command)!r} failed with exit code {returncode}: {detail}"
            )
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.replace(stdout_path, output_path)
            except OSError as exc:
                raise ConversionError(
                    f"Unable to publish converter output {output_path}: {exc}"
                ) from exc


def convert_source(source: SourceSpec, source_path: Path, work_dir: Path) -> Path:
    """Convert a locked source to the logical intermediate format consumed by Python."""

    output_dir = work_dir / source.source_id
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{source.source_id}-", dir=output_dir) as stage_name:
        stage_dir = Path(stage_name)
        if source.format == "mm":
            output_path = output_dir / f"{source.source_id}.html"
            staged_path = stage_dir / output_path.name
            command = [
                _tool_path("groff"),
                "-m",
                "mm",
                "-t",
                "-T",
                "html",
                "-p",
                str(source_path.resolve()),
            ]
            _run(command, cwd=stage_dir, output_path=staged_path)
        elif source.format == "doc":
            libreoffice = _tool_path("libreoffice")
            output_path = output_dir / f"{source_path.stem}.docx"
            command = [
                libreoffice,
                "--headless",
                "--convert-to",
                "docx",
                "--outdir",
                str(stage_dir),
                str(source_path.resolve()),
            ]
            _run(command, cwd=stage_dir)
            staged_path = stage_dir / output_path.name
            if not staged_path.exists():
                raise ConversionError(f"LibreOffice did not produce expected output {output_path}")
        else:
            raise ConversionError(f"Unsupported source format {source.format!r}")

        if not staged_path.exists():
            raise ConversionError(f"Converter did not produce expected output {staged_path}")
        try:
            os.replace(staged_path, output_path)
        except OSError as exc:
            raise ConversionError(
                f"Unable to publish converted source {output_path}: {exc}"
            ) from exc
    return output_path
