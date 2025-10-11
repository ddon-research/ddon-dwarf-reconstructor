# Testing

Professional testing infrastructure with xUnit reporting, code coverage, and CI/CD automation.

## Quick Start

```bash
# Fast unit tests (recommended)
uv run pytest -m unit

# All tests
uv run pytest

# With HTML coverage
uv run pytest -m unit --cov-report=html
# Open htmlcov/index.html

# Integration tests
uv run pytest -m integration

# Makefile shortcuts
make test          # Unit tests only
make coverage      # HTML coverage report
make ci            # Full CI suite (lint + typecheck + test)
```

## Test Categories

**Markers:**
- @pytest.mark.unit - Fast mocked tests (<1s, preferred)
- @pytest.mark.integration - Real ELF file tests (~3s)
- @pytest.mark.slow - Long-running tests
- @pytest.mark.performance - Performance benchmarks

**Usage:**
```bash
uv run pytest -m "unit"              # Unit tests only
uv run pytest -m "not slow"          # Skip slow tests
uv run pytest -m "unit or integration" # Both categories
```

## Test Structure

```
tests/
 application/
    generators/
        test_dwarf_generator.py        # Main orchestrator tests
        test_dwarf_integration.py      # End-to-end tests

 domain/
    models/
       dwarf/
           test_class_info.py         # Model tests
   
    services/
        parsing/
           test_class_parser.py       # DWARF parsing tests
           test_array_parser.py       # Array type tests
           test_type_resolver.py      # Type resolution tests
       
        generation/
            test_header_generator.py   # C++ generation tests
            test_hierarchy_builder.py  # Inheritance tests
            test_packing_analyzer.py   # Memory layout tests

 infrastructure/
     config/
         test_application_config.py     # Config tests
```

## Configuration

**pyproject.toml:**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = [
    "-v",
    "--tb=short",
    "--strict-markers",
    "--cov=src/ddon_dwarf_reconstructor",
    "--cov-report=term-missing",
    "--cov-report=xml:coverage.xml",
    "--cov-report=html:htmlcov",
    "--junit-xml=test-results.xml",
    "--cov-branch",
]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
    "performance: marks tests as performance benchmarks",
]
```

## Writing Tests

### Unit Tests (Preferred)

**Use mocks for external dependencies:**

```python
@pytest.mark.unit
def test_find_class_success(mocker):
    """Test finding a class with realistic mocks."""
    # Mock DWARF structure based on actual dumps
    mock_die = Mock()
    mock_die.tag = "DW_TAG_class_type"
    mock_die.attributes = {'DW_AT_name': Mock(value=b'MtObject')}
    
    mock_cu = Mock()
    mock_cu.iter_DIEs.return_value = [mock_die]
    
    mock_elf = Mock()
    mock_elf.get_dwarf_info.return_value.iter_CUs.return_value = [mock_cu]
    
    mocker.patch("builtins.open")
    mocker.patch("pyelftools.elf.elffile.ELFFile", return_value=mock_elf)
    
    with DwarfGenerator("test.elf") as generator:
        result = generator.find_class("MtObject")
        assert result == (mock_cu, mock_die)
```

**Best Practices:**
- Base mocks on actual DWARF dump structures
- Mock at module boundaries (ELFFile, not internal functions)
- Test one component at a time
- Include edge cases and error conditions

### Integration Tests

**Use real ELF files when needed:**

```python
@pytest.mark.integration
def test_mtpropertylist_full_hierarchy():
    """Integration test with real ELF file."""
    with DwarfGenerator(ELF_PATH) as generator:
        header = generator.generate_complete_hierarchy_header("MtPropertyList")
        
        # Verify typedef resolution
        assert "typedef unsigned short u16;" in header
        assert "typedef unsigned int u32;" in header
        
        # Verify inheritance chain
        assert "class MtObject" in header
        assert "class MtPropertyList : public MtObject" in header
        
        # Verify member parsing
        assert "u16 mPropCount;" in header
```

**When to use:**
- End-to-end workflow validation
- Complex DWARF structures
- Real-world header generation
- Regression testing

## Coverage

**Current Status:**
- Unit tests: 48% coverage
- Integration tests: +40% coverage
- Total: 88% coverage
- Branch coverage: Enabled

**Coverage Reports:**
1. **Terminal** - Quick summary during test run
2. **HTML** - Detailed line-by-line (htmlcov/index.html)
3. **XML** - Machine-readable (coverage.xml)
4. **JUnit** - CI integration (test-results.xml)

**Viewing Coverage:**
```bash
# Generate HTML report
uv run pytest -m unit --cov-report=html

# Open in browser (Windows)
start htmlcov/index.html

# Show missing lines in terminal
uv run pytest -m unit --cov-report=term-missing
```

## CI/CD Pipeline

### GitHub Actions Workflows

**1. Unit Tests and Coverage** (.github/workflows/test.yml)

```yaml
Trigger: Push to main, Pull Requests
Matrix: Python 3.13, ubuntu-latest
Steps:
  1. Checkout code
  2. Setup Python and uv
  3. Install dependencies (uv sync)
  4. Run unit tests (pytest -m unit --cov)
  5. Upload coverage to Codecov
  6. Upload test artifacts (30 days)
  7. Publish test results
```

**Coverage Requirements:**
- Minimum: 30% (enforced)
- Target: 80%+
- Scope: src/ddon_dwarf_reconstructor/ only

**2. Code Quality** (.github/workflows/quality.yml)

```yaml
Trigger: Push to main, Pull Requests
Steps:
  1. Ruff linter (uv run ruff check)
  2. Ruff formatter (uv run ruff format --check)
  3. MyPy type checker (uv run mypy src/)
```

### CI Artifacts

**Generated and uploaded:**
- test-results.xml (JUnit XML)
- coverage.xml (Cobertura XML)
- htmlcov/ (HTML coverage report)

**Retention:** 30 days

## Development Workflow

**Recommended cycle:**

```bash
# 1. Make changes
vim src/domain/services/parsing/class_parser.py

# 2. Run fast unit tests
uv run pytest -m unit

# 3. Check coverage
uv run pytest -m unit --cov-report=html
start htmlcov/index.html

# 4. Fix uncovered code
# Add tests for new functionality

# 5. Run integration tests before commit
uv run pytest -m integration

# 6. Full CI locally
make ci
```

## Performance

| Test Category | Count | Execution Time | Coverage |
|---------------|-------|----------------|----------|
| Unit tests | 92 | <1s | 48% |
| Integration tests | 2 | ~3s | +40% |
| Total | 94 | ~4s | 88% |

**Optimization:**
- Unit tests use mocks (no file I/O)
- Integration tests cached with pytest-cache
- Parallel execution possible with pytest-xdist

## Troubleshooting

**Common Issues:**

1. **Marker warnings:**
   ```bash
   # Check markers are defined
   uv run pytest --markers
   ```

2. **Coverage not generated:**
   ```bash
   # Verify coverage source path
   uv run pytest --cov=src/ddon_dwarf_reconstructor --cov-report=term
   ```

3. **Import errors:**
   ```bash
   # Install in editable mode
   uv sync
   ```

4. **CI failures:**
   ```bash
   # Run exactly what CI runs
   uv run pytest -m unit --cov --cov-fail-under=30
   ```

**Debugging:**

```bash
# Verbose test discovery
uv run pytest --collect-only -v

# Run specific test
uv run pytest tests/domain/services/parsing/test_class_parser.py::test_find_class_success -v

# Show print statements
uv run pytest -s

# Stop on first failure
uv run pytest -x

# Show local variables on failure
uv run pytest -l
```

## Dependencies

**Required:**
- pytest - Testing framework
- pytest-cov - Coverage measurement
- pytest-mock - Mocking utilities

**Optional:**
- pytest-timeout - Test timeouts
- pytest-xdist - Parallel execution
- pytest-html - HTML reports

**Installation:**
```bash
uv sync  # Installs all dev dependencies
```

## Quality Gates

**Pre-commit checks:**
- All unit tests pass
- Coverage >30%
- Ruff linting passes
- MyPy type checking passes
- Ruff formatting correct

**Pre-merge checks:**
- All tests pass (including integration)
- Coverage >80%
- No regression in performance tests
- Documentation updated

## References

- [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [GitHub Actions workflows](../.github/workflows/)
