# CLAUDE.md

Technical guidance for Claude when working with this DWARF-to-C++ header reconstruction tool.

## Important instructions

- Do not run tools in parallel. There is currently a bug in Claude Code that causes concurrency issues of this form "API Error: 400 due to tool use concurrency issues".

## Project Overview

**Purpose**: Reconstruct C++ headers from DWARF debug symbols in ELF files
**Language**: Python 3.13+ with strict type hints (mypy)
**Architecture**: Direct pyelftools integration without reinventing DWARF parsing

## Core Components

### `models.py` - DWARF Constants
- Enums: `DWTag`, `DWAccessibility`, `DWVirtuality` for reference

### `dwarf_generator.py` - pyelftools Integration
- `DwarfGenerator`: Context manager using pyelftools directly
- Methods: `find_class()`, `parse_class_info()`, `generate_header()`
- Uses pyelftools DIE structures exclusively (`DWARFInfo`, `CompilationUnit`, `DIE`)
- Built-in type resolution with `get_DIE_from_attribute()`
- No custom DWARF parsing - leverages proven pyelftools API
- Reuses established data structures without reinventing them

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
uv run pytest -m "unit"               # Unit tests (preferred - fast ~0.1s)
uv run pytest                         # All tests (~3s)
uv run pytest -m "integration"        # Integration tests only
uv run pytest --cov-report=html       # With HTML coverage report

# Shortcuts via Makefile
make test                             # Unit tests
make coverage                        # HTML coverage report
make ci                              # Full CI simulation

# Code quality
uv run mypy src/
uv run ruff check src/
```

## Architecture Notes

### Package Structure
- **Name**: `ddon_dwarf_reconstructor` (underscores)
- **Entry**: Root `main.py` → `src/ddon_dwarf_reconstructor/main.py:main()`
- **Config**: `.env` → environment → CLI args (priority order)

### CLI Arguments
- `--generate SYMBOL`: Generate C++ header for symbol
- `--verbose` / `-v`: Enable debug logs in console + file
- `-o` / `--output`: Output directory (default: `./output`)
- `--no-metadata`: Skip metadata comments

### Output Structure
- **Headers**: `output/<symbol>.h` (always simple naming)
- **Logs**: `logs/ddon_reconstructor_YYYYMMDD_HHMMSS.log`

### PS4 ELF Handling
- Non-standard sections require lenient parsing
- Try-except blocks around DWARF operations
- Graceful degradation for parsing failures

## Code Style Requirements

- **Type Safety**: All functions must have type hints
- **Python Version**: 3.13+
- **Docstrings**: PEP 257 format with parameter/return documentation
- **Error Handling**: Explicit exception types, no bare `except`
- **Logging**: Use `get_logger(__name__)` instead of `print()`

## Testing Requirements

**MANDATORY**: All tests MUST be run via `uv run pytest`.

### Professional Testing Setup
The project has a comprehensive testing infrastructure with:

- **xUnit Reporting**: JUnit XML output for CI/CD integration
- **Code Coverage**: Multiple formats (XML, HTML, terminal)
- **GitHub Actions**: Automated CI/CD for unit tests and code quality
- **Test Categories**: Unit (fast), integration (real files), slow, performance

### Test Commands
```bash
# Unit tests (preferred for development - fast)
uv run pytest -m "unit"

# All tests
uv run pytest

# With coverage report
uv run pytest -m "unit" --cov-report=html
# Then open: htmlcov/index.html

# Integration tests only
uv run pytest -m "integration"

# Using Makefile shortcuts
make test          # Unit tests
make coverage      # HTML coverage report  
make ci           # Full CI simulation
```

### Test Structure & Markers
- **`@pytest.mark.unit`**: Fast mocked tests (22 tests, ~0.1s) - **PREFERRED FOR DEVELOPMENT**
- **`@pytest.mark.integration`**: Real ELF file tests (2 tests, ~3s)
- **`@pytest.mark.slow`**: Long-running tests (skip with `-m "not slow"`)
- **`@pytest.mark.performance`**: Performance benchmarks

### Coverage Metrics
- **Unit Tests**: ~38% coverage (realistic for mocked tests)
- **Integration Tests**: Higher coverage but slower execution
- **CI Threshold**: 30% minimum (enforced)
- **Target**: 80%+ with both unit and integration tests

### CI/CD Pipeline
- **Triggers**: Push to `main`, all PRs  
- **Python Version**: 3.13 (Ubuntu latest)
- **Test Workflow** (`.github/workflows/test.yml`):
  - Unit tests only (fast feedback ~30s)
  - Code coverage with 30% minimum threshold
  - Codecov integration for coverage tracking
  - JUnit XML and coverage artifacts (30-day retention)
- **Quality Workflow** (`.github/workflows/quality.yml`):
  - Ruff linting with GitHub format output
  - Ruff formatter check  
  - MyPy type checking
- **Artifacts**: Test results XML, coverage reports, HTML coverage

### Generated Reports
- **`test-results.xml`**: JUnit format for CI systems
- **`coverage.xml`**: Machine-readable coverage for Codecov
- **`htmlcov/`**: Interactive coverage visualization
- **Terminal**: Live coverage summary with missing lines

### Writing Tests
```python
import pytest
from unittest.mock import Mock
from ddon_dwarf_reconstructor.generators.dwarf_generator import DwarfGenerator

@pytest.mark.unit
def test_find_class_success(mocker):
    """Unit test with mocks (preferred)."""
    mock_elf = Mock()
    # ... setup realistic mocks ...
    mocker.patch("builtins.open")
    mocker.patch("...ELFFile", return_value=mock_elf)
    
    with DwarfGenerator("test.elf") as generator:
        result = generator.find_class("MtObject")
        assert result is not None

@pytest.mark.integration  
def test_real_elf_processing(elf_file_path):
    """Integration test with real files (slower)."""
    with DwarfGenerator(elf_file_path) as generator:
        header = generator.generate_header("MtObject")
        assert len(header) > 0
```

### Testing Philosophy
1. **Unit First**: Write comprehensive mocked unit tests
2. **Integration Validation**: Use real files for critical path validation
3. **Performance Awareness**: Mark slow tests appropriately
4. **CI Friendly**: Focus on fast unit tests in CI pipeline

### Key Testing Changes (October 2025)
- **Professional CI/CD**: GitHub Actions with Python 3.13, xUnit reporting, Codecov integration
- **Comprehensive Coverage**: XML/HTML/terminal reports with 30% minimum threshold
- **Fast Development**: Unit tests preferred (~0.1s vs 3s for integration tests)  
- **Quality Automation**: Separate workflows for testing and code quality
- **Developer Tools**: Makefile shortcuts, detailed documentation in `docs/TESTING.md`

See [docs/TESTING.md](docs/TESTING.md) for complete testing documentation.

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


## Common Operations

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
- Ensure MtObject generation stays <10s
- Check log files for timing breakdowns
