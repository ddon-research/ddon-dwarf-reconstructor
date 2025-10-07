# CLAUDE.md

Technical guidance for Claude when working with this DWARF-to-C++ header reconstruction tool.

## Important instructions

- Do not run tools in parallel. There is currently a bug in Claude Code that causes concurrency issues of this form "API Error: 400 due to tool use concurrency issues".

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
- `parse_cus_until_target_found()`: Early stopping CU parsing
- CU-level caching with pickle serialization

## Performance Optimizations

- **Early Stopping**: Parse CUs until target found (82x speedup for cItemParam)
- **CU Caching**: Persistent disk cache with 3.6x speedup
- **Type Indexing**: O(1) type lookups with lazy loading
- **Memory Limiting**: Configurable CU parsing limits

## Test Structure

Run tests with `pytest` from project root:
- `tests/core/` - DWARF parsing functionality
- `tests/generators/` - Header generation modes  
- `tests/performance/` - Optimization benchmarks
- `tests/config/` - Configuration management
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

# Testing - MANDATORY: ALL TESTS MUST USE PYTEST
pytest                          # All tests
pytest -m unit                  # Unit tests only
pytest -m integration           # Integration tests only
pytest -m "not slow"            # Fast tests (skip performance)
pytest -m performance           # Performance benchmarks
pytest -v --tb=short            # Verbose with short tracebacks

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

## Testing Requirements

**MANDATORY**: All tests MUST be run via pytest. The legacy `run_tests.py` has been removed.

### Test Structure
- **Markers**: Use `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.performance`, `@pytest.mark.slow`
- **Fixtures**: Use shared fixtures from `tests/conftest.py` (elf_parser, config, sample_symbols, etc.)
- **Sample Symbols**: Use `fast_symbol` fixture for "MtObject" (fast, <10s) or test with other symbols from `sample_symbols` (may be slow)
- **Performance**: Mark slow tests with `@pytest.mark.slow` so they can be skipped in fast CI runs

### Writing Tests
```python
import pytest
from ddon_dwarf_reconstructor.core import DWARFParser

@pytest.mark.integration
def test_example(elf_parser: DWARFParser, fast_symbol: str) -> None:
    """Test with MtObject (fast symbol in first CU)."""
    # Use elf_parser fixture (auto-setup/teardown)
    # Use fast_symbol for quick tests
    pass
```

See [tests/README.md](tests/README.md) for comprehensive testing documentation.

## Knowledge Base

Reference materials in `docs/knowledge-base/`:
- **PS4 ELF**: Sony constants, IDA loader insights
- **DWARF**: Ghidra lazy loading, optimization strategies  
- **pyelftools**: Current API patterns and limitations

Local repository paths maintained in `references/references.md`.
