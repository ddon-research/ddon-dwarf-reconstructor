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
- `parse_cus_until_target_found()`: Early stopping CU parsing (82x speedup)
- CU-level caching with pickle serialization (3.6x speedup)
- PS4-specific lenient parsing (`stream_loader=None`)
- Iterator over compilation units
- Converts pyelftools DIEs to typed model objects

### `die_extractor.py` - Optimized Search
- `DIEExtractor`: Lazy-loaded indexes for O(1) repeated searches
- Methods: `find_dies_by_name()`, `find_dies_by_tag()`, `get_die_by_offset()`
- 60,000x performance improvement over linear search
- Inspired by Ghidra's indexing architecture

### `header_generator.py` - C++ Output
- `HeaderGenerator`: Clean generator with single optimized strategy
- `GenerationMode.OPTIMIZED`: Single mode - no complexity
- `GenerationOptions`: Configuration for output customization
- `generate_header()`: Main standalone function

### `logger.py` - Centralized Logging
- `LoggerSetup`: Manages dual logging (console + file)
- Console: INFO (quiet) or DEBUG (verbose) based on --verbose flag
- File: Always DEBUG level with timestamps
- Log files: `logs/ddon_reconstructor_{timestamp}.log`
- `@log_timing` decorator for performance tracking

### `config.py` - Configuration Management
- `.env` → environment → CLI args (priority order)
- `Config.from_args()`: Load from CLI with env fallback
- `ensure_output_dir()`, `ensure_log_dir()`: Directory creation
- Validation for ELF file existence

## Development Commands

```bash
# Installation
uv sync

# Run tool (from project root)
python main.py resources/DDOORBIS.elf --search MtObject
python main.py resources/DDOORBIS.elf --generate MtObject
python main.py resources/DDOORBIS.elf --generate MtObject --verbose

# Using .env file
echo "ELF_FILE_PATH=resources/DDOORBIS.elf" > .env
python main.py --generate MtObject --verbose

# Testing - MANDATORY: ALL TESTS MUST USE PYTEST with uv run
uv run pytest                          # All tests
uv run pytest -m unit                  # Unit tests only
uv run pytest -m integration           # Integration tests only
uv run pytest -m "not slow"            # Fast tests (skip performance)
uv run pytest -m performance           # Performance benchmarks
uv run pytest -v --tb=short            # Verbose with short tracebacks

# Code quality
uv run mypy src/
uv run ruff check src/
```

## Performance Optimizations

- **Early Stopping**: Parse CUs until target found (82x speedup for cItemParam)
- **CU Caching**: Persistent disk cache with 3.6x speedup
- **Type Indexing**: O(1) type lookups with lazy loading
- **Single Strategy**: No mode confusion - one optimized path

## Architecture Notes

### Package Structure
- **Name**: `ddon_dwarf_reconstructor` (underscores)
- **Entry**: Root `main.py` → `src/ddon_dwarf_reconstructor/main.py:main()`
- **Config**: `.env` → environment → CLI args (priority order)

### CLI Arguments
- `--search SYMBOL`: Search for symbol in DWARF info
- `--generate SYMBOL`: Generate C++ header for symbol
- `--verbose` / `-v`: Enable debug logs in console + file
- `-o` / `--output`: Output directory (default: `./output`)
- `--max-depth N`: Max dependency depth (default: 50)
- `--no-metadata`: Skip metadata comments

### Output Structure
- **Headers**: `output/<symbol>.h` (always simple naming)
- **Logs**: `logs/ddon_reconstructor_YYYYMMDD_HHMMSS.log`

### PS4 ELF Handling
- Non-standard sections require lenient parsing
- Try-except blocks around DWARF operations
- Graceful degradation for parsing failures

### Performance Constraints
- <10s for most symbols with early stopping
- Memory: <500MB peak usage
- Lazy indexing: Build on first access, cache thereafter

## Code Style Requirements

- **Type Safety**: All functions must have type hints
- **Line Length**: 100 characters (ruff config)
- **Python Version**: 3.10+ (for union syntax)
- **Docstrings**: PEP 257 format with parameter/return documentation
- **Error Handling**: Explicit exception types, no bare `except`
- **Logging**: Use `get_logger(__name__)` instead of `print()`

## Testing Requirements

**MANDATORY**: All tests MUST be run via `uv run pytest`.

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

## Logging Best Practices

### In Application Code

```python
from ddon_dwarf_reconstructor.utils import get_logger, log_timing

logger = get_logger(__name__)

@log_timing
def expensive_operation() -> None:
    logger.debug("Starting expensive operation")
    # ... do work ...
    logger.info("Operation completed successfully")
```

### Log Levels
- `DEBUG`: Verbose implementation details, timing info
- `INFO`: Progress updates, successful operations
- `WARNING`: Recoverable issues, cache misses
- `ERROR`: Failures requiring user attention

### Console Output
- **Quiet mode** (default): INFO and above
- **Verbose mode** (`--verbose`): DEBUG and above

### File Output
- Always DEBUG and above
- Timestamped files in `logs/`
- Rotation not currently implemented (future enhancement)

## CLI Usage

### Command Line Arguments
- `--search SYMBOL`: Search for symbol in DWARF info
- `--generate SYMBOL`: Generate C++ header for symbol
- `--verbose` / `-v`: Enable debug logs
- `-o` / `--output`: Output directory (default: `./output`)
- `--max-depth N`: Max dependency depth (default: 50)
- `--no-metadata`: Skip metadata comments

### Output Format
- Headers: `output/<symbol>.h` (clean, simple naming)
- Logs: `logs/ddon_reconstructor_YYYYMMDD_HHMMSS.log`

## Common Operations

### Run Tool with Verbose Logging
```bash
python main.py resources/DDOORBIS.elf --generate MtObject --verbose
```

### Check Generated Logs
```bash
ls -lt logs/  # View recent logs
tail -f logs/ddon_reconstructor_*.log  # Monitor latest log
```

### Run Tests for Specific Module
```bash
uv run pytest tests/core/test_dwarf_parser.py -v
uv run pytest tests/generators/ -v
```

### Debug Type Issues
```bash
uv run mypy src/ --show-error-codes
uv run mypy src/ddon_dwarf_reconstructor/core/ -v
```

## Knowledge Base

Reference materials in `docs/knowledge-base/`:
- **PS4 ELF**: Sony constants, IDA loader insights
- **DWARF**: Ghidra lazy loading, optimization strategies
- **pyelftools**: Current API patterns and limitations

Local repository paths maintained in `references/references.md`.

## Important Notes

### Using uv
- **ALWAYS** prefix Python commands with `uv run` for consistency
- Example: `uv run pytest`, `uv run mypy src/`, `uv run python main.py`
- This ensures correct virtual environment and dependencies

### Test Execution
- Do NOT use `python -m pytest` or bare `pytest`
- Always use `uv run pytest`

### Code Modifications
- After significant changes, run the full test suite
- Check type safety with mypy before committing
- Verify linting with ruff

### Performance Validation
- For critical changes, run performance benchmarks
- Ensure MtObject generation stays <10s
- Check log files for timing breakdowns
