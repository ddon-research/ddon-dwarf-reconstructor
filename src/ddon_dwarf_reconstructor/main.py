"""Main entry point for the DDON DWARF Reconstructor."""

import argparse
import sys
from pathlib import Path
from typing import NoReturn, Optional

from .config import Config
from .core import DIEExtractor, DWARFParser
from .generators import (
    HeaderGenerator,
    GenerationMode,
    GenerationOptions,
    generate_header_with_logging,
    generate_fast_header,
    generate_ultra_fast_header
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Reconstruct C/C++ structures from DWARF debug symbols in PS4 ELF files"
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
        help="Enable verbose output",
    )
    parser.add_argument(
        "--search",
        type=str,
        help="Search for a specific symbol name in DWARF info",
    )
    parser.add_argument(
        "--generate-header",
        type=str,
        metavar="SYMBOL",
        help="Generate C++ header file for the specified symbol (full dependency resolution)",
    )
    parser.add_argument(
        "--fast-header",
        type=str,
        metavar="SYMBOL",
        help="Generate C++ header with limited dependencies for fast execution",
    )
    parser.add_argument(
        "--ultra-fast-header",
        type=str,
        metavar="SYMBOL",
        help="Generate C++ header by scanning only first few CUs (maximum speed)",
    )
    parser.add_argument(
        "--max-classes",
        type=int,
        default=10,
        help="Maximum classes to include in fast header generation (default: 10)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=50,
        help="Maximum dependency depth for full header generation (default: 50)",
    )
    parser.add_argument(
        "--max-cu-scan",
        type=int,
        default=10,
        help="Maximum CUs to scan in ultra-fast mode (default: 10)",
    )
    parser.add_argument(
        "--no-dependencies",
        action="store_true",
        help="Don't include dependencies when generating headers",
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

    if config.verbose:
        print(f"ELF file: {config.elf_file_path}")
        print(f"Output directory: {config.output_dir}")
        print()

    # Parse DWARF information
    try:
        with DWARFParser(config.elf_file_path, config.verbose) as parser:

            # Handle ultra-fast header generation
            if args.ultra_fast_header:
                symbol_name = args.ultra_fast_header
                print(f"⚡ Ultra-fast header generation for: {symbol_name}")
                print(f"Max CUs to scan: {args.max_cu_scan}")

                output_file = config.output_dir / f"{symbol_name}_ultra_fast.h"

                try:
                    header_content = generate_ultra_fast_header(
                        parser=parser,
                        symbol_name=symbol_name,
                        output_path=output_file,
                        max_cu_scan=args.max_cu_scan
                    )

                    print(f"\n✅ Generated ultra-fast header: {output_file}")
                    print(f"Size: {len(header_content)} bytes")

                    if config.verbose:
                        print("\nPreview (first 20 lines):")
                        print("=" * 50)
                        for line in header_content.split('\n')[:20]:
                            print(line)
                        print("=" * 50)

                except ValueError as e:
                    print(f"❌ Error: {e}", file=sys.stderr)
                    sys.exit(1)

                sys.exit(0)

            # Handle fast header generation
            if args.fast_header:
                symbol_name = args.fast_header
                print(f"🚀 Fast header generation for: {symbol_name}")
                print(f"Max classes: {args.max_classes}")

                output_file = config.output_dir / f"{symbol_name}_fast.h"

                try:
                    header_content = generate_fast_header(
                        parser=parser,
                        symbol_name=symbol_name,
                        output_path=output_file,
                        max_classes=args.max_classes
                    )

                    print(f"\n✅ Generated fast header: {output_file}")
                    print(f"Size: {len(header_content)} bytes")

                    if config.verbose:
                        print("\nPreview (first 20 lines):")
                        print("=" * 50)
                        for line in header_content.split('\n')[:20]:
                            print(line)
                        print("=" * 50)

                except ValueError as e:
                    print(f"❌ Error: {e}", file=sys.stderr)
                    sys.exit(1)

                sys.exit(0)

            # Handle full header generation
            if args.generate_header:
                symbol_name = args.generate_header
                print(f"🏗️ Full header generation for: {symbol_name}")
                print(f"Max dependency depth: {args.max_depth}")

                # Determine output path
                output_file = config.output_dir / f"{symbol_name}.h"

                try:
                    header_content = generate_header_with_logging(
                        parser=parser,
                        symbol_name=symbol_name,
                        output_path=output_file,
                        add_metadata=not args.no_metadata,
                        max_dependency_depth=args.max_depth
                    )

                    print(f"\n✅ Generated header: {output_file}")
                    print(f"Size: {len(header_content)} bytes")

                    if config.verbose:
                        print("\nPreview (first 30 lines):")
                        print("=" * 60)
                        # Print first 30 lines
                        lines = header_content.split('\n')
                        for line in lines[:30]:
                            print(line)
                        if len(lines) > 30:
                            print(f"... and {len(lines) - 30} more lines")
                        print("=" * 60)

                except ValueError as e:
                    print(f"❌ Error: {e}", file=sys.stderr)
                    sys.exit(1)

                sys.exit(0)

            # Parse all compilation units for search functionality
            compilation_units = parser.parse_all_compilation_units()

            if not compilation_units:
                print("Warning: No compilation units found in DWARF info", file=sys.stderr)
                sys.exit(1)

            # Create DIE extractor
            extractor = DIEExtractor(compilation_units)

            # If a search term was provided, search for it
            if args.search:
                print(f"\n🔍 Searching for symbol: {args.search}")
                results = extractor.find_dies_by_name(args.search)

                if results:
                    print(f"✅ Found {len(results)} result(s):\n")
                    for cu, die in results:
                        print(f"Compilation Unit at offset 0x{cu.offset:08x}:")
                        extractor.print_die_summary(die, indent=1)

                        # Print children summary
                        if die.children:
                            print(f"  Children ({len(die.children)}):")
                            for child in die.children[:10]:  # Limit to first 10
                                extractor.print_die_summary(child, indent=2)
                            if len(die.children) > 10:
                                print(f"    ... and {len(die.children) - 10} more")
                        print()
                else:
                    print(f"❌ No results found for '{args.search}'")

                sys.exit(0)

            # Default behavior: print summary
            print("\n📊 DWARF Analysis Summary:")
            print(f"Compilation Units: {len(compilation_units)}")

            total_dies = sum(len(cu.dies) for cu in compilation_units)
            print(f"Total DIEs: {total_dies:,}")

            # Quick class/struct count
            all_classes = extractor.get_all_classes()
            all_structs = extractor.get_all_structs()
            print(f"Classes: {len(all_classes)}")
            print(f"Structs: {len(all_structs)}")

            print(f"\n💡 Usage examples:")
            print(f"  Search: --search MtObject")
            print(f"  Fast header: --fast-header cItemParam --max-classes 20")
            print(f"  Full header: --generate-header MtObject --max-depth 10")
            print(f"  Ultra-fast header: --ultra-fast-header cItemParam --max-classes 5 --max-cu-scan 10")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if config.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
