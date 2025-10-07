# Running Tests

## Quick Start

```bash
# Install test dependencies
uv sync

# Run all tests
pytest

# Run tests with coverage
pytest --cov=src/ddon_dwarf_reconstructor --cov-report=html

# Run specific test categories
pytest -m unit              # Unit tests only
pytest -m integration       # Integration tests only
pytest -m performance       # Performance tests only
pytest -m "not slow"        # Skip slow tests
```

## Test Structure

```
tests/
├── conftest.py          # Pytest configuration and shared fixtures
├── test_utils.py        # Legacy utilities (deprecated - use conftest.py fixtures)
├── config/              # Configuration tests
│   └── test_config.py
├── core/                # Core DWARF parsing tests
│   └── test_dwarf_core.py
├── generators/          # Header generation tests
│   └── test_header_generation.py
├── performance/         # Performance benchmarks
│   ├── test_performance.py
│   ├── test_cu_caching.py
│   └── test_parallel_parsing.py
└── utils/               # Utility tests
    └── test_utilities.py
```

## Test Categories

Tests are marked using pytest markers for selective execution:

### Unit Tests (`-m unit`)
- Fast, isolated tests
- No external dependencies
- Test individual functions/methods
- Example: Configuration validation, error handling

### Integration Tests (`-m integration`)
- Test component interactions
- Require ELF file
- Test full workflows (parsing, extracting, generating)
- Slower than unit tests

### Performance Tests (`-m performance`)
- Benchmark performance metrics
- Test caching, indexing, optimization features
- May be very slow (marked with `@pytest.mark.slow`)
- Should validate performance constraints

### Slow Tests (`-m slow`)
- Tests that take significant time (>10s)
- Often overlap with performance tests
- Skip in fast CI runs with `-m "not slow"`

## Fixtures

Shared fixtures are defined in [conftest.py](conftest.py):

### Configuration Fixtures
- `config`: Loaded Config object from environment
- `elf_file_path`: Path to ELF file (skips if not available)
- `project_root`: Project root directory

### Parser Fixtures
- `elf_parser`: Fresh DWARFParser instance (function scope)

### Sample Symbol Fixtures
- `sample_symbols`: Dict of known symbols from [resources/sample-symbols.csv](../resources/sample-symbols.csv)
- `fast_symbol`: Returns "MtObject" (found in first CU, fast for testing)
- `known_symbol`: Parametrized fixture for testing multiple symbols

## Environment Setup

Tests require an ELF file to be configured:

```bash
# Create .env file
echo "ELF_FILE_PATH=resources/DDOORBIS.elf" > .env
```

Or set environment variable:
```bash
export ELF_FILE_PATH=resources/DDOORBIS.elf
```

## Common Test Commands

```bash
# Run all tests with verbose output
pytest -v

# Run tests and stop on first failure
pytest -x

# Run tests matching a pattern
pytest -k "cache"

# Run a specific test file
pytest tests/performance/test_cu_caching.py

# Run a specific test function
pytest tests/performance/test_cu_caching.py::test_cu_cache_speedup

# Show print statements
pytest -s

# Generate HTML coverage report
pytest --cov=src/ddon_dwarf_reconstructor --cov-report=html
# Open htmlcov/index.html in browser

# Run fast tests only (skip slow performance tests)
pytest -m "not slow"

# Run integration tests only
pytest -m integration

# Very verbose output with local variables on failure
pytest -vv -l
```

## Using Sample Symbols

Tests should use known symbols from [resources/sample-symbols.csv](../resources/sample-symbols.csv):

**MtObject**: Base class, in first CU (fast to find, <10s)
**rLandInfo, cSetInfoOm, etc.**: May be in later CUs (much slower, potentially minutes)

### Example: Using the fast_symbol fixture
```python
@pytest.mark.integration
def test_header_generation(elf_parser: DWARFParser, fast_symbol: str) -> None:
    """Test with MtObject (fast symbol)."""
    header = generate_header(elf_parser, fast_symbol)
    assert len(header) > 0
```

### Example: Testing with multiple symbols
```python
@pytest.mark.slow
@pytest.mark.parametrize("symbol", ["MtObject", "rLandInfo"])
def test_multiple_symbols(elf_parser: DWARFParser, symbol: str, sample_symbols: dict) -> None:
    """Test with various symbols (may be slow)."""
    if symbol not in sample_symbols:
        pytest.skip(f"{symbol} not in CSV")

    header = generate_header(elf_parser, symbol)
    assert len(header) > 0
```

## Writing New Tests

### Test File Naming
- File: `test_<feature>.py`
- Function: `test_<what_it_tests>()`
- Class: `Test<Feature>` (optional)

### Using Markers
```python
import pytest

@pytest.mark.unit
def test_something_fast():
    """Fast unit test."""
    assert True

@pytest.mark.integration
def test_with_elf(elf_parser):
    """Integration test requiring ELF file."""
    pass

@pytest.mark.slow
@pytest.mark.performance
def test_performance_benchmark(elf_parser):
    """Long-running performance test."""
    pass
```

### Using Fixtures
```python
import pytest
from pathlib import Path
from ddon_dwarf_reconstructor.core import DWARFParser

@pytest.mark.integration
def test_with_fixtures(
    elf_parser: DWARFParser,
    fast_symbol: str,
    sample_symbols: dict[str, str | None]
) -> None:
    """Test using shared fixtures from conftest.py."""
    # elf_parser is ready to use
    # fast_symbol is "MtObject"
    # sample_symbols contains all known symbols

    if fast_symbol not in sample_symbols:
        pytest.skip(f"{fast_symbol} not in sample CSV")

    # Your test code here
    pass
```

## Debugging Tests

```bash
# Run with pdb on failure
pytest --pdb

# Run with pdb at test start
pytest --trace

# Show local variables on failure
pytest -l

# Very verbose output
pytest -vv

# Run with full stdout/stderr
pytest -s --tb=long
```

## Continuous Integration

The test suite is designed for CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run tests
  run: |
    uv sync
    pytest -v -m "not slow" --cov=src/ddon_dwarf_reconstructor --cov-report=xml
```

## Migration Notes

**DEPRECATED**: The legacy `run_tests.py` custom test runner has been removed.
**All tests MUST use pytest.**

If you find old test code patterns:
- `from test_utils import TestRunner` → Use pytest fixtures
- `runner.run_test(test_func)` → Use `def test_func()` with markers
- `handle_test_skip(reason)` → Use `pytest.skip(reason)`
- `if __name__ == "__main__"` blocks → Remove (use pytest)
