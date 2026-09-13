"""Neutral canonical-assembly assembler used by artifact publication."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .implementation_assembly_source import safe_name
from .toolchain_process import ToolchainExportError, run_bounded_capture


def assemble_canonical_source(
    method_id: str,
    source: str,
    assembler: Path | None,
    *,
    timeout_seconds: float | None = None,
) -> tuple[bytes | None, tuple[str, ...]]:
    """Assemble canonical source and return only the accepted object bytes."""
    if assembler is None:
        return None, ("Orbis assembler was not supplied; object was not emitted",)
    if not assembler.is_file():
        return None, ("Orbis assembler path does not exist; object was not emitted",)
    safe_id = safe_name(method_id)
    with tempfile.TemporaryDirectory(prefix="ddon-canonical-assembly-") as temporary:
        root = Path(temporary)
        assembly_path = root / f"{safe_id}.s"
        object_path = root / f"{safe_id}.o"
        assembly_path.write_text(source, encoding="utf-8", newline="\n")
        try:
            completed = run_bounded_capture(
                assembler,
                ("-o", str(object_path), str(assembly_path)),
                timeout_seconds,
            )
        except TimeoutError:
            return None, ("Orbis assembler execution timed out",)
        except OSError, ToolchainExportError:
            return None, ("Orbis assembler could not be executed",)
        if completed.stdout_truncated or completed.stderr_truncated:
            return None, ("Orbis assembler output exceeded the bounded cap",)
        if completed.returncode != 0 or not object_path.is_file():
            return None, ("Orbis assembler rejected canonical assembly",)
        return object_path.read_bytes(), ()


__all__ = ["assemble_canonical_source"]
