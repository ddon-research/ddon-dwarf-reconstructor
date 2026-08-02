"""Command-line parser for the canonical reconstructor entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

_EPILOG = """
Examples:
  # Generate header (quiet mode - default)
  python main.py resources/DDOORBIS.elf --generate MtObject

  # Generate multiple headers
  python main.py resources/DDOORBIS.elf --generate MtObject,MtVector4,rTbl2Base

  # Generate with full hierarchy
  python main.py resources/DDOORBIS.elf --generate MtPropertyList --full-hierarchy

  # Generate header (verbose mode with debug logs)
  python main.py resources/DDOORBIS.elf --generate MtObject --verbose

  # Custom output directory
  python main.py resources/DDOORBIS.elf --generate MtObject -o headers/

  # Generate from file (289 symbols)
  python main.py resources/DDOORBIS.elf --symbols-file resources/season2-resources.txt

  # Generate from file with full hierarchy
  python main.py resources/DDOORBIS.elf --symbols-file my-symbols.txt --full-hierarchy

  # Exhaustive search for most complete definition (slower first run)
  python main.py resources/DDOORBIS.elf --generate rLayout --exhaustive

  # Exhaustive search with compressed DWARF dump (requires Python 3.14)
  python main.py resources/DDOORBIS.elf --generate rLayout --exhaustive --dwarf-dump dump.zst

  # Using .env file for configuration
  echo 'ELF_FILE_PATH=resources/DDOORBIS.elf' > .env
  python main.py --generate MtObject
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconstruct C++ headers from DWARF debug symbols in ELF files using pyelftools",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_input_options(parser)
    _add_generation_options(parser)
    _add_evidence_options(parser)
    return parser


def _add_input_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("elf_file", type=Path, nargs="?", help="Path to the ELF file to analyze")
    parser.add_argument("-o", "--output", type=Path, help="Output directory (default: ./output)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logs")
    parser.add_argument("--generate", type=str, metavar="SYMBOL", help="Comma-separated symbols")
    parser.add_argument("--symbols-file", type=Path, metavar="FILE", help="One symbol per line")


def _add_generation_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--full-hierarchy", action="store_true", help="Generate the full hierarchy")
    parser.add_argument(
        "--single-file", action="store_true", help="Use legacy single-file hierarchy mode"
    )
    parser.add_argument(
        "--exhaustive", action="store_true", help="Search all CUs for the best definition"
    )
    parser.add_argument(
        "--dwarf-dump", type=Path, metavar="PATH", help="Compressed DWARF dump path"
    )
    parser.add_argument(
        "--dwarf-index", type=Path, metavar="PATH", help="Explicit DWARF SQLite sidecar"
    )


def _add_evidence_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--export-knowledge", type=Path, metavar="DIR", help="Export a knowledge bundle"
    )
    parser.add_argument("--build-id", type=str, help="Stable build identifier")
    parser.add_argument(
        "--orbis-objdump", type=Path, metavar="PATH", help="Pinned Orbis objdump executable"
    )
    parser.add_argument(
        "--resolve-param-names",
        action="store_true",
        help="Search method implementations for parameter names",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    return build_parser().parse_args(argv)
