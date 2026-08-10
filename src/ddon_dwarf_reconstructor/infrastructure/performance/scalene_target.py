"""Module wrapper allowing Scalene to profile a canonical ``python -m`` target."""

from __future__ import annotations

import argparse
import runpy
import sys


def main(argv: list[str] | None = None) -> int:
    """Run the requested module under Scalene's child process."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", required=True)
    parser.add_argument("module_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    sys.argv = [args.module, *args.module_args]
    try:
        runpy.run_module(args.module, run_name="__main__")
    except SystemExit as error:
        return error.code if isinstance(error.code, int) else 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
