"""Command-line interface for the DWARF specification pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import PipelineError, build
from .source_manifest import SourceError, load_manifest, verify_source
from .validation import ArtifactValidationError, validate_output_directory


def _default_schema() -> Path:
    return Path("tools/dwarf_spec_pipeline/schema/dwarf-specification.schema.json")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser(
        "build", help="build canonical JSON and Markdown artifacts"
    )
    build_parser.add_argument(
        "--manifest", type=Path, default=Path("tools/dwarf_spec_pipeline/config/sources.json")
    )
    build_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/knowledge-base/dwarf-specification/generated"),
    )
    build_parser.add_argument("--work-dir", type=Path, default=Path(".cache/dwarf_spec_pipeline"))
    build_parser.add_argument("--schema", type=Path, default=_default_schema())
    build_parser.add_argument("--version", type=int, action="append", choices=(2, 3, 4))
    build_parser.add_argument("--offline", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="validate generated artifacts")
    validate_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/knowledge-base/dwarf-specification/generated"),
    )
    validate_parser.add_argument("--schema", type=Path, default=_default_schema())

    sources_parser = subparsers.add_parser("sources", help="verify cached source documents")
    sources_parser.add_argument(
        "--manifest", type=Path, default=Path("tools/dwarf_spec_pipeline/config/sources.json")
    )
    sources_parser.add_argument(
        "--cache-dir", type=Path, default=Path(".cache/dwarf_spec_pipeline/sources")
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "build":
            build(
                args.manifest,
                args.output_dir,
                args.work_dir,
                args.schema,
                versions=set(args.version) if args.version else None,
                offline=args.offline,
            )
            print(f"Built DWARF artifacts in {args.output_dir}")
        elif args.command == "validate":
            validate_output_directory(args.output_dir, args.schema)
            print(f"Validated DWARF artifacts in {args.output_dir}")
        elif args.command == "sources":
            manifest = load_manifest(args.manifest)
            for source in manifest.sources:
                path = args.cache_dir / source.source_id / source.filename
                verify_source(path, source)
            print(f"Verified {len(manifest.sources)} cached DWARF sources")
        return 0
    except (ArtifactValidationError, PipelineError, SourceError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
