"""Command-line arguments and selected-failure dispatch for header validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .failure_probe import FailureProbeError, explain_failed_unit


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate generated C++ headers with MSVC")
    parser.add_argument(
        "--input-root",
        type=Path,
        action="append",
        help="Season batch root, symbol bundle, or ps4 header directory; repeatable.",
    )
    parser.add_argument("--validation-directory", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument(
        "--explain-report", type=Path, help="Existing manifest-bound validation report."
    )
    parser.add_argument("--explain-unit", help="Failed unit key in --explain-report.")
    parser.add_argument("--reference-root", type=Path, default=Path("D:/research/cppstdmd"))
    parser.add_argument("--requirement-witness", type=Path)
    return parser.parse_args(argv)


def explain_main(args: argparse.Namespace) -> int:
    """Run an optional selected-unit probe without rerunning bundle acceptance."""
    if not args.explain_unit or args.input_root:
        print("--explain-report requires --explain-unit and no --input-root", file=sys.stderr)
        return 2
    try:
        result = explain_failed_unit(
            args.explain_report,
            args.explain_unit,
            args.validation_directory,
            args.reference_root,
            args.timeout_seconds,
            args.requirement_witness,
        )
    except (FailureProbeError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Selected failure probe failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("status", "unit_key", "first_error", "declaration_requirement")
            },
            indent=2,
        )
    )
    return 0 if result["status"] == "observed" else 1
