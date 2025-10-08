# Testing Setup and CI/CD Pipeline

This document describes the comprehensive testing setup for the DDON DWARF Reconstructor project, including xUnit-style reporting, code coverage, and automated CI/CD pipelines.

## Test Configuration

The project uses `pytest` with several plugins for comprehensive testing and reporting:

### Dependencies

- **pytest**: Main testing framework
- **pytest-cov**: Code coverage measurement
- **pytest-html**: HTML test reports
- **pytest-mock**: Mocking utilities
- **pytest-timeout**: Test timeout management

### Configuration

Test configuration is primarily located in `pyproject.toml` under `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = [
    "-v",                                    # Verbose output
    "--tb=short",                           # Short traceback format
    "--strict-markers",                     # Strict marker enforcement
    "--color=yes",                         # Colored output
    "--cov=src/ddon_dwarf_reconstructor",  # Coverage source
    "--cov-report=term-missing",           # Terminal coverage report
    "--cov-report=xml:coverage.xml",       # XML coverage for CI
    "--cov-report=html:htmlcov",           # HTML coverage report
    "--junit-xml=test-results.xml",        # JUnit XML for CI
    "--cov-branch",                        # Branch coverage
]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests", 
    "unit: marks tests as unit tests",
    "performance: marks tests as performance benchmarks",
]
```

## Test Categories

Tests are organized using pytest markers:

- **`@pytest.mark.unit`**: Fast unit tests with mocks (preferred for CI)
- **`@pytest.mark.integration`**: Integration tests using real files
- **`@pytest.mark.slow`**: Long-running tests
- **`@pytest.mark.performance`**: Performance benchmarks

## Running Tests

### Unit Tests Only (Recommended for Development)
```bash
uv run pytest -m "unit"
```

### All Tests
```bash
uv run pytest
```

### With Coverage Report
```bash
uv run pytest -m "unit" --cov-report=html
# Opens htmlcov/index.html for detailed coverage view
```

### Integration Tests Only
```bash
uv run pytest -m "integration"
```

## Generated Reports

The test suite generates several reports:

### 1. JUnit XML Report (`test-results.xml`)
- **Purpose**: xUnit-style test results for CI/CD systems
- **Format**: Standard JUnit XML format
- **Contains**: Test names, execution times, pass/fail status
- **Usage**: GitHub Actions, Azure DevOps, Jenkins integration

### 2. Coverage XML Report (`coverage.xml`)
- **Purpose**: Machine-readable coverage data
- **Format**: Cobertura XML format
- **Contains**: Line and branch coverage percentages
- **Usage**: Codecov, SonarQube, coverage badges

### 3. HTML Coverage Report (`htmlcov/`)
- **Purpose**: Human-readable coverage visualization
- **Format**: Interactive HTML pages
- **Contains**: Line-by-line coverage highlighting, missing lines
- **Usage**: Local development, detailed coverage analysis

### 4. Terminal Coverage Report
- **Purpose**: Quick coverage summary
- **Format**: Text table in terminal
- **Contains**: File-by-file coverage percentages
- **Usage**: Development feedback, CI logs

## GitHub Actions CI/CD Pipeline

The project includes two GitHub Actions workflows:

### 1. Unit Tests and Coverage (`.github/workflows/test.yml`)

**Triggers**: Push to `main`, Pull Requests
**Matrix**: Python 3.13
**Steps**:
1. Checkout code
2. Setup Python and uv
3. Install dependencies
4. Run unit tests with coverage (minimum 80%)
5. Upload coverage to Codecov
6. Upload test artifacts
7. Publish test results

**Artifacts**:
- Test results XML
- Coverage reports
- HTML coverage report

### 2. Code Quality (`.github/workflows/quality.yml`)

**Triggers**: Push to `main`, Pull Requests
**Steps**:
1. Checkout code
2. Setup Python and uv
3. Install dependencies
4. Run ruff linter
5. Run ruff formatter check
6. Run mypy type checker

## Coverage Requirements

- **Minimum Coverage**: 30% for unit tests (enforced in CI)
- **Target Coverage**: 80%+ when including integration tests
- **Branch Coverage**: Enabled
- **Coverage Scope**: `src/ddon_dwarf_reconstructor/` package only

Note: Unit tests alone provide ~38% coverage. The remaining coverage comes from integration tests that use real ELF files.

## Best Practices

### Writing Tests

1. **Prefer Unit Tests**: Use mocks for external dependencies
2. **Mark Tests Appropriately**: Use `@pytest.mark.unit` for fast tests
3. **Realistic Mocks**: Base mocks on actual DWARF dump structures
4. **Test Edge Cases**: Include error conditions and boundary cases

### Development Workflow

1. **Run Unit Tests Frequently**: `uv run pytest -m "unit"`
2. **Check Coverage**: Review `htmlcov/index.html` after test runs
3. **Fix Coverage Issues**: Aim for >90% coverage on new code
4. **Integration Tests**: Run before committing significant changes

### CI/CD Integration

1. **Unit Tests Only**: CI runs only unit tests for speed
2. **Coverage Enforcement**: CI fails if coverage drops below 80%
3. **Python 3.13 Only**: Tests run exclusively on Python 3.13
4. **Artifact Preservation**: Test results saved for 30 days

## Troubleshooting

### Common Issues

1. **Marker Warnings**: Ensure markers are defined in `pyproject.toml`
2. **Coverage Not Generated**: Check `--cov` paths match source structure
3. **JUnit XML Invalid**: Verify test names don't contain invalid XML characters
4. **CI Failures**: Check coverage minimum thresholds and Python version compatibility

### Debugging Commands

```bash
# Check pytest configuration
uv run pytest --help

# Verbose test discovery
uv run pytest --collect-only -v

# Run specific test file
uv run pytest tests/generators/test_dwarf_generator.py -v

# Coverage report with missing lines
uv run pytest -m "unit" --cov-report=term-missing
```

## File Structure

```
.github/workflows/
├── test.yml          # Unit tests and coverage pipeline
└── quality.yml       # Code quality checks

tests/
├── config/           # Configuration tests
├── generators/       # Core functionality tests
└── utils/           # Utility function tests

Generated Reports:
├── test-results.xml  # JUnit XML report
├── coverage.xml      # Coverage XML report
├── htmlcov/         # HTML coverage report
└── .coverage        # Coverage database
```

This setup provides comprehensive testing with proper CI/CD integration, ensuring code quality and reliability while maintaining fast feedback loops for developers.