"""Main entry point for the DDON DWARF Reconstructor."""

import argparse
import sys
from pathlib import Path
from typing import NoReturn

from .application.generators import DwarfGenerator
from .infrastructure.config import Config
from .infrastructure.logging import LoggerSetup, get_logger, log_timing
from .utils.path_utils import create_header_filename


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Reconstruct C++ headers from DWARF debug symbols in ELF files "
        "using pyelftools",
        epilog="""
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
        help="Generate C++ header file for the specified symbol(s). "
        "Supports comma-separated list: 'MtObject,MtVector4,rTbl2Base'",
    )
    parser.add_argument(
        "--symbols-file",
        type=Path,
        metavar="FILE",
        help="Read symbols from file (one symbol per line). "
        "Alternative to --generate for processing large lists",
    )
    parser.add_argument(
        "--full-hierarchy",
        action="store_true",
        help="Generate complete inheritance hierarchy (includes all base classes)",
    )
    parser.add_argument(
        "--single-file",
        action="store_true",
        help="With --full-hierarchy: generate single file with all classes and forward declarations (legacy mode). "
        "Without --full-hierarchy: has no effect",
    )
    return parser.parse_args()


@log_timing
def main() -> NoReturn:
    """Main entry point for DWARF-to-C++ header generation using pyelftools."""
    logger = get_logger(__name__)
    logger.debug("Starting DDON DWARF Reconstructor main program")

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

    # Parse symbol list (support both --generate and --symbols-file)
    symbols = []
    
    if args.generate and args.symbols_file:
        logger.error("Cannot use both --generate and --symbols-file options")
        sys.exit(1)
    elif args.generate:
        # Parse comma-separated symbols
        symbols = [s.strip() for s in args.generate.split(",") if s.strip()]
    elif args.symbols_file:
        # Read symbols from file
        try:
            with open(args.symbols_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):  # Skip empty lines and comments
                        symbols.append(line)
            logger.info(f"Read {len(symbols)} symbols from {args.symbols_file}")
        except FileNotFoundError:
            logger.error(f"Symbols file not found: {args.symbols_file}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error reading symbols file: {e}")
            sys.exit(1)
    else:
        logger.error("Must provide either --generate or --symbols-file option")
        sys.exit(1)

    if not symbols:
        logger.error("No symbols provided")
        sys.exit(1)

    logger.info(f"Generating headers for {len(symbols)} symbol(s)")
    generation_mode = "full-hierarchy"
    if args.full_hierarchy:
        if args.single_file:
            generation_mode = "full-hierarchy (single-file, legacy)"
        else:
            generation_mode = "full-hierarchy (multi-file)"
    logger.debug(f"Generation mode: {generation_mode}")

    # Track results
    success_count = 0
    failed_symbols = []

    # Process each symbol
    try:
        with DwarfGenerator(config.elf_file_path) as generator:
            for i, symbol_name in enumerate(symbols, 1):
                logger.info(f"[{i}/{len(symbols)}] Processing: {symbol_name}")

                try:
                    # Generate header(s)
                    is_multi_file = False
                    headers_to_write: dict[str, str] = {}
                    
                    if args.full_hierarchy:
                        if args.single_file:
                            # Legacy single-file mode
                            header_content = generator.generate_complete_hierarchy_header(symbol_name)
                            filename = create_header_filename(symbol_name)
                            headers_to_write[filename] = header_content
                        else:
                            # New multi-file mode
                            is_multi_file = True
                            headers_to_write = generator.generate_multi_file_hierarchy(symbol_name)
                    else:
                        header_content = generator.generate_header(symbol_name)
                        filename = create_header_filename(symbol_name)
                        headers_to_write[filename] = header_content

                    # Determine output path - use platform-specific subdirectory
                    platform_str = generator.platform.value if generator.platform else "unknown"
                    platform_dir = config.output_dir / platform_str
                    platform_dir.mkdir(parents=True, exist_ok=True)

                    # Write header(s)
                    total_bytes = 0
                    for header_filename, header_content in headers_to_write.items():
                        output_file = platform_dir / header_filename
                        output_file.write_text(header_content, encoding="utf-8")
                        total_bytes += len(header_content)

                        logger.info(f"[SUCCESS] Generated: {output_file}")
                        logger.info(f"Size: {len(header_content)} bytes")

                    success_count += 1

                    # Save cache after each successful generation
                    if generator.lazy_index is not None:
                        generator.lazy_index.save_cache()
                        logger.debug("Cache saved after successful generation")

                    # Calculate lines and provide summary statistics
                    if not is_multi_file:
                        # Single file mode - show preview
                        single_filename = list(headers_to_write.keys())[0] if headers_to_write else ""
                        lines = headers_to_write[single_filename].split("\n") if single_filename in headers_to_write else []
                        logger.debug(f"Generated header contains {len(lines)} lines")

                        if config.verbose and len(symbols) == 1:
                            # Only show preview for single symbol in verbose mode
                            logger.debug("\nPreview (first 30 lines):")
                            logger.debug("=" * 60)
                            for line in lines[:30]:
                                logger.debug(line)
                            if len(lines) > 30:
                                logger.debug(f"... and {len(lines) - 30} more lines")
                            logger.debug("=" * 60)
                    else:
                        # Multi-file mode - show summary
                        logger.debug(f"Generated {len(headers_to_write)} headers, {total_bytes} total bytes")
                        if config.verbose:
                            logger.debug("Generated files:")
                            for fname in sorted(headers_to_write.keys()):
                                logger.debug(f"  - {fname}")

                except ValueError as e:
                    logger.error(f"[FAILED] {symbol_name}: {e}")
                    failed_symbols.append((symbol_name, str(e)))
                except Exception as e:
                    logger.error(f"[FAILED] {symbol_name}: {e}")
                    failed_symbols.append((symbol_name, str(e)))
                    if config.verbose:
                        import traceback

                        traceback.print_exc()

    except Exception as e:
        logger.error(f"Fatal error during generation: {e}")
        if config.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)

    # Print summary
    logger.info("=" * 70)
    logger.info("GENERATION SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total symbols: {len(symbols)}")
    logger.info(f"Successfully generated: {success_count}")
    logger.info(f"Failed: {len(failed_symbols)}")

    if failed_symbols:
        logger.info("\nFailed symbols:")
        for symbol_name, error in failed_symbols:
            logger.info(f"  - {symbol_name}: {error}")

    logger.debug("Main program completed successfully")

    # Exit with error code if any symbols failed
    sys.exit(0 if len(failed_symbols) == 0 else 1)


if __name__ == "__main__":
    main()
