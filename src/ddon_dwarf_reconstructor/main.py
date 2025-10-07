"""Main entry point for the DDON DWARF Reconstructor."""

import argparse
import sys
from pathlib import Path
from typing import NoReturn

from .config import Config
from .core import DIEExtractor, DWARFParser
from .generators import generate_header
from .utils import LoggerSetup, get_logger


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Reconstruct C++ headers from DWARF debug symbols in PS4 ELF files",
        epilog="""
Examples:
  # Search for a symbol
  python main.py resources/DDOORBIS.elf --search MtObject

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
        "--search",
        type=str,
        help="Search for a specific symbol name in DWARF info",
    )
    parser.add_argument(
        "--generate",
        type=str,
        metavar="SYMBOL",
        help="Generate C++ header file for the specified symbol",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=50,
        help="Maximum dependency depth for header generation (default: 50)",
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Don't include metadata comments in generated headers",
    )
    return parser.parse_args()


def main() -> NoReturn:
    """Main entry point."""
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
    logger.debug(f"Log directory: {log_dir}")

    # Ensure output directory exists
    config.ensure_output_dir()

    # Parse DWARF information
    try:
        with DWARFParser(config.elf_file_path, config.verbose) as parser:

            # Handle header generation
            if args.generate:
                symbol_name = args.generate
                logger.info(f"Generating header for: {symbol_name}")

                # Determine output path - always use <symbol>.h format
                output_file = config.output_dir / f"{symbol_name}.h"

                try:
                    header_content = generate_header(
                        parser=parser,
                        symbol_name=symbol_name,
                        output_path=output_file,
                        add_metadata=not args.no_metadata,
                        max_dependency_depth=args.max_depth,
                    )

                    logger.info(f"✅ Generated: {output_file}")
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

                sys.exit(0)

            # Handle search functionality
            if args.search:
                logger.info(f"Searching for symbol: {args.search}")

                # Parse compilation units
                compilation_units = parser.parse_all_compilation_units()

                if not compilation_units:
                    logger.warning("No compilation units found in DWARF info")
                    sys.exit(1)

                # Create DIE extractor
                extractor = DIEExtractor(compilation_units)

                # Search for symbol
                results = extractor.find_dies_by_name(args.search)

                if results:
                    logger.info(f"✅ Found {len(results)} result(s):")
                    for cu, die in results:
                        logger.info(f"\nCompilation Unit at offset 0x{cu.offset:08x}:")
                        extractor.print_die_summary(die, indent=1)

                        # Print children summary
                        if die.children:
                            logger.info(f"  Children ({len(die.children)}):")
                            for child in die.children[:10]:  # Limit to first 10
                                extractor.print_die_summary(child, indent=2)
                            if len(die.children) > 10:
                                logger.info(f"    ... and {len(die.children) - 10} more")
                else:
                    logger.info(f"❌ No results found for '{args.search}'")

                sys.exit(0)

            # Default behavior: print summary
            logger.info("Parsing DWARF information...")
            compilation_units = parser.parse_all_compilation_units()

            logger.info("\n📊 DWARF Analysis Summary:")
            logger.info(f"Compilation Units: {len(compilation_units)}")

            total_dies = sum(len(cu.dies) for cu in compilation_units)
            logger.info(f"Total DIEs: {total_dies:,}")

            # Quick class/struct count
            extractor = DIEExtractor(compilation_units)
            all_classes = extractor.get_all_classes()
            all_structs = extractor.get_all_structs()
            logger.info(f"Classes: {len(all_classes)}")
            logger.info(f"Structs: {len(all_structs)}")

            logger.info("\n💡 Usage examples:")
            logger.info(f"  Search: python main.py {config.elf_file_path} --search MtObject")
            logger.info(
                f"  Generate: python main.py {config.elf_file_path} --generate MtObject"
            )
            logger.info(
                f"  Verbose: python main.py {config.elf_file_path} --generate MtObject --verbose"
            )

    except Exception as e:
        logger.error(f"Error: {e}")
        if config.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
