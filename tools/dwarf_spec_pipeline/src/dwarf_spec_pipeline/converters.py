"""Run the pinned document converters used by the Docker build."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .source_manifest import SourceSpec


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


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise ConversionError(f"Unable to start converter {command[0]!r}: {exc}") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise ConversionError(
            f"Converter {' '.join(command)!r} failed with exit code "
            f"{completed.returncode}: {detail}"
        )


def convert_source(source: SourceSpec, source_path: Path, work_dir: Path) -> Path:
    """Convert a locked source to the logical intermediate format consumed by Python."""

    output_dir = work_dir / source.source_id
    output_dir.mkdir(parents=True, exist_ok=True)
    if source.format == "mm":
        output_path = output_dir / f"{source.source_id}.html"
        output_path.unlink(missing_ok=True)
        command = [_tool_path("groff"), "-m", "mm", "-t", "-T", "html", "-p", str(source_path)]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise ConversionError(f"Unable to start Groff: {exc}") from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise ConversionError(f"Groff failed with exit code {completed.returncode}: {detail}")
        output_path.write_text(completed.stdout, encoding="utf-8", newline="\n")
        return output_path

    if source.format == "doc":
        libreoffice = _tool_path("libreoffice")
        output_path = output_dir / f"{source_path.stem}.docx"
        output_path.unlink(missing_ok=True)
        _run(
            [
                libreoffice,
                "--headless",
                "--convert-to",
                "docx",
                "--outdir",
                str(output_dir),
                str(source_path),
            ]
        )
        if not output_path.exists():
            raise ConversionError(f"LibreOffice did not produce expected output {output_path}")
        return output_path

    raise ConversionError(f"Unsupported source format {source.format!r}")
