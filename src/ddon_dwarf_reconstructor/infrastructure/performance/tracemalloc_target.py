"""Small opt-in child wrapper for Python allocation snapshots."""

from __future__ import annotations

import argparse
import json
import runpy
import tracemalloc
from pathlib import Path

from .paths import atomic_write_text


def main(argv: list[str] | None = None) -> int:
    """Run one module with tracemalloc enabled and publish bounded allocation data."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--module", required=True)
    parser.add_argument("module_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    tracemalloc.start(25)
    status = 0
    try:
        import sys

        sys.argv = [args.module, *args.module_args]
        runpy.run_module(args.module, run_name="__main__")
    except SystemExit as error:
        status = error.code if isinstance(error.code, int) else 1
    finally:
        current, peak = tracemalloc.get_traced_memory()
        snapshot = tracemalloc.take_snapshot()
        top = snapshot.statistics("lineno")[:20]
        payload = {
            "current_bytes": current,
            "peak_bytes": peak,
            "top": [
                {"traceback": str(item.traceback), "size_bytes": item.size, "count": item.count}
                for item in top
            ],
        }
        atomic_write_text(args.output, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        tracemalloc.stop()
    return status


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
