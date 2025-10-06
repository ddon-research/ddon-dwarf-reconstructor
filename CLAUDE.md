# CLAUDE.md

Technical guidance for Claude when working with this DWARF-to-C++ header reconstruction tool.

## Project Overview

**Purpose**: Reconstruct C++ headers from DWARF debug symbols in PS4 ELF files  
**Language**: Python 3.10+ with strict type hints (mypy)  
**Architecture**: Modular design with lazy-loaded indexing optimization  

## Core Components

### `models.py` - Type System
- `DIE`: Debug Information Entry with attributes/children
- `DWARFAttribute`: Name/value pairs from DWARF data
- `CompilationUnit`: Container for DIE collections
- Enums: `DWTag`, `DWAccessibility`, `DWVirtuality`

### `dwarf_parser.py` - ELF/DWARF Interface  
- `DWARFParser`: Context manager for ELF file access
- PS4-specific lenient parsing (`stream_loader=None`)
- Iterator over compilation units
- Converts pyelftools DIEs to typed model objects

### `die_extractor.py` - Optimized Search
- `DIEExtractor`: Lazy-loaded indexes for O(1) repeated searches
- Methods: `find_dies_by_name()`, `find_dies_by_tag()`, `get_die_by_offset()`
- 60,000x performance improvement over linear search
- Inspired by Ghidra's indexing architecture

### `header_generator.py` - C++ Output
- `HeaderGenerator`: Unified generator with mode selection
- `GenerationMode`: ULTRA_FAST, FAST, SIMPLE
- `GenerationOptions`: Configuration for output customization
- Backward-compatible standalone functions

## Development Commands

```bash
# Installation
uv sync

# Run tool
ddon-dwarf-reconstructor resources/DDOORBIS.elf --search MtObject

# Testing
python tests/run_tests.py                    # All tests
python tests/run_tests.py --simple          # Essential only
python tests/run_tests.py -m performance    # Benchmarks

# Code quality
mypy src/
ruff check src/
```

## Architecture Notes

### Package Structure
- **Name**: `ddon_dwarf_reconstructor` (underscores)
- **Entry**: `src/ddon_dwarf_reconstructor/main.py:main()`
- **Config**: `.env` → environment → CLI args (priority order)

### PS4 ELF Handling
- Non-standard sections require lenient parsing
- Try-except blocks around DWARF operations
- Graceful degradation for parsing failures

### Performance Constraints
- ULTRA_FAST: <10s for most symbols
- Memory: <500MB peak usage
- Lazy indexing: Build on first access, cache thereafter

## Code Style Requirements

- **Type Safety**: All functions must have type hints
- **Line Length**: 100 characters (ruff config)  
- **Python Version**: 3.10+ (for union syntax)
- **Docstrings**: PEP 257 format with parameter/return documentation
- **Error Handling**: Explicit exception types, no bare `except`

## Knowledge Base

Reference materials in `docs/knowledge-base/`:
- **PS4 ELF**: Sony constants, IDA loader insights
- **DWARF**: Ghidra lazy loading, optimization strategies  
- **pyelftools**: Current API patterns and limitations

Local repository paths maintained in `references/references.md`.
