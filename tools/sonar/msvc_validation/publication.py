"""Atomic publication of validation reports."""

from __future__ import annotations

import json
import os
from contextlib import suppress
from pathlib import Path
from typing import Any
from uuid import uuid4


def write_json_atomic(path: Path, payload: Any) -> Path:
    """Write a JSON artifact beside its target and publish it with replace."""
    target = path.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.partial")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=True, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        with suppress(OSError):
            temporary.unlink(missing_ok=True)
        raise
    return target
