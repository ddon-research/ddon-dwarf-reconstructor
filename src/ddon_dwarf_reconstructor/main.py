"""Main entry point for the DDON DWARF Reconstructor."""

import argparse
import sys
from pathlib import Path
from typing import NoReturn

from .config import Config
from .generators.native_generator import NativeDwarfGenerator
from .utils import LoggerSetup, get_logger


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Reconstruct C++ headers from DWARF debug symbols using native pyelftools",
        epilog="""
Examples:
  # Generate header (quiet mode - default)
  python main.py resources/DDOORBIS.elf --generate MtObject

  # Generate header (verbose mode with debug logs)  
  python main.py resources/DDOORBIS.elf --generate MtObject --verbose

  # Custom output directory
  python main.py resources/DDOORBIS.elf --generate MtObject -o headers/

  # Using .env file for configuration
  echo 'ELF_FILE_PATH=resources/DDOORBIS.elf' > .env
  python main.py --generate MtObject
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "elf_file",
        type=Path,
        nargs="?",
        help="Path to the ELF file to analyze (optional if using .env)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output directory for reconstructed headers (default: ./output)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output with debug logs",
    )
    parser.add_argument(
        "--generate",
        type=str,
        metavar="SYMBOL",
        required=True,
        help="Generate C++ header file for the specified symbol",
    )
    parser.add_argument(
        "--full-hierarchy",
        action="store_true",
        help="Generate complete inheritance hierarchy (includes all base classes)",
    )
    return parser.parse_args()


def main() -> NoReturn:
    """Main entry point for native pyelftools-based header generation."""
    args = parse_args()

    # Load configuration
    try:
        config = Config.from_args(
            elf_file_path=args.elf_file,
            output_dir=args.output,
            verbose=args.verbose,
        )
        config.validate()
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize logging
    log_dir = Path("logs")
    LoggerSetup.initialize(log_dir, verbose=config.verbose)
    logger = get_logger(__name__)

    logger.debug(f"ELF file: {config.elf_file_path}")
    logger.debug(f"Output directory: {config.output_dir}")

    # Ensure output directory exists
    config.ensure_output_dir()

    # Generate header using native pyelftools
    symbol_name = args.generate
    logger.info(f"Generating header for: {symbol_name}")

    # Determine output path - always use <symbol>.h format
    output_file = config.output_dir / f"{symbol_name}.h"

    try:
        with NativeDwarfGenerator(config.elf_file_path) as generator:
            if args.full_hierarchy:
                header_content = generator.generate_complete_hierarchy_header(symbol_name)
            else:
                header_content = generator.generate_header(symbol_name)
            
            # Write to output file
            output_file.write_text(header_content, encoding='utf-8')

            logger.info(f"[SUCCESS] Generated: {output_file}")
            logger.info(f"Size: {len(header_content)} bytes")

            if config.verbose:
                logger.debug("\nPreview (first 30 lines):")
                logger.debug("=" * 60)
                lines = header_content.split("\n")
                for line in lines[:30]:
                    logger.debug(line)
                if len(lines) > 30:
                    logger.debug(f"... and {len(lines) - 30} more lines")
                logger.debug("=" * 60)

    except ValueError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        if config.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
