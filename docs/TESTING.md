# Testing

Professional testing infrastructure with xUnit reporting, code coverage, and CI/CD automation.

Real DDON inputs are immutable and expensive derived artifacts are intentionally
durable. Tests must distinguish cold construction from fresh-process warm reuse.
Routine test cleanup must not delete the real dump SQLite sidecar or OS-local
symbol cache. Tests that exercise invalidation should use isolated fixture
copies or explicit temporary artifact paths.

## Quick Start

```bash
# Fast unit tests (recommended)
uv run just test-unit

# All non-performance tests
uv run just test

# With HTML coverage
uv run just coverage

# Integration tests
uv run just test-integration

# Opt-in real warm export, including the pinned Orbis producer
$env:DDON_REAL_PERFORMANCE='1'
$env:DDON_REAL_ELF='D:\research\DDON-binaries\IDA9.3\PS4_DDON_02020005_2016_12_21\DDOORBIS.elf'
$env:DDON_REAL_DWARF_DUMP="$env:DDON_REAL_ELF.llvmdwarfdump.zst"
$env:DDON_REAL_DWARF_INDEX='D:\ddon-dwarf-reconstructor\output\real-dump-index\DDOORBIS.elf.llvmdwarfdump.index.sqlite3'
$env:DDON_ORBIS_OBJDUMP='D:\SCE\ORBIS SDKs\8.000\host_tools\bin\orbis-objdump.exe'
uv run just test-performance

# just shortcuts
uv run just test-unit
uv run just coverage
uv run just ci

# Distribution acceptance
uv run just package-smoke
```

The `packaging` marker installs the project into temporary uv tool directories and verifies the
standalone console entry point from outside the checkout. It is excluded from the normal test and
coverage recipes and is run explicitly by `just package-smoke` and CI.

## Test Categories

**Markers:**
- @pytest.mark.unit - Fast mocked tests (<1s, preferred)
- @pytest.mark.integration - Integration tests, including opt-in real files
- @pytest.mark.slow - Long-running tests
- @pytest.mark.performance - Performance benchmarks

**Usage:**
```bash
uv run just test-unit                 # Unit tests only
uv run just test-integration          # Integration tests
uv run just test-performance          # Explicit performance tier
```

## DWARF specification pipeline

The specification tool has its own lockfile, test markers, and quality
commands. Run these from the repository root:

```bash
uv run --directory tools/dwarf_spec_pipeline just test
uv run --directory tools/dwarf_spec_pipeline just check
uv run --directory tools/dwarf_spec_pipeline just docker-config
```

The official-source integration assertion is opt-in after a Docker build:

```powershell
$env:DWARF_SPEC_OFFICIAL = '1'
uv run --directory tools/dwarf_spec_pipeline pytest -m integration
Remove-Item Env:DWARF_SPEC_OFFICIAL
```

It checks the generated DWARF 2/3/4 JSON against the schema, verifies known
tags/attributes/forms/operations/languages, checks section coverage, and
rejects legacy Groff/media/table-of-contents garbage. Source downloads and
conversion intermediates remain in the ignored cache and are never test
fixtures or committed artifacts.

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
- Batch processing validation
- Pinned-tool parsing and real instruction-range validation

**Example - Batch Processing:**

```python
@pytest.mark.integration
def test_batch_processing():
    """Test batch symbol processing from file."""
    # Create temporary symbol file
    symbols = ["MtObject", "MtVector4", "MtPropertyList"]
    symbol_file = tmp_path / "test_symbols.txt"
    symbol_file.write_text("\n".join(symbols))
    
    # Process all symbols
    with DwarfGenerator(ELF_PATH) as gen:
        for symbol in symbols:
            header = gen.generate_complete_hierarchy_header(symbol)
            assert symbol in header
            assert len(header) > 0
```

**Integration Test Results (289 symbols):**

- Success rate: 289/289 (100%)
- Source: resources/season2-resources.txt
- Command: `uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf --symbols-file resources/season2-resources.txt --full-hierarchy`
- Duration: ~15-30 minutes (full hierarchy mode)
- Cache hits: 1519 symbols cached

## Coverage

**Current Status:**
- Full non-performance suite: 412 passed, 1 deselected
- Total line coverage: 85.65% (80% gate passed)
- Branch coverage: Enabled, with focused group thresholds enforced

**Coverage Reports:**
1. **Terminal** - Quick summary during test run
2. **HTML** - Detailed line-by-line (htmlcov/index.html)
3. **XML** - Machine-readable (coverage.xml)
4. **JUnit** - CI integration (test-results.xml)

**Viewing Coverage:**
```bash
# Generate HTML report and enforce coverage thresholds
uv run just coverage

# Open in browser (Windows)
start htmlcov/index.html

# Generate CI-compatible XML/JUnit reports
uv run just coverage-ci
```

## CI/CD Pipeline

### GitHub Actions Workflows

**1. Unit Tests and Coverage** (.github/workflows/test.yml)

```yaml
Trigger: Push to main, Pull Requests
Matrix: Python 3.14.6, ubuntu-latest
Steps:
  1. Checkout code
  2. Setup Python and uv
  3. Install dependencies (`uv sync --python 3.14.6 --frozen`)
  4. Run `uv run just coverage-ci`
  5. Upload coverage to Codecov
  6. Upload test artifacts (30 days)
  7. Publish test results
```

**Coverage Requirements:**
- Minimum: 80% total line coverage (enforced)
- High-risk groups: 80% line and 70% branch coverage (enforced)
- Scope: src/ddon_dwarf_reconstructor/ only

**2. Code Quality** (.github/workflows/quality.yml)

```yaml
Trigger: Push to main, Pull Requests
Steps:
    1. `uv run just check` (Ruff, Pyrefly, deptry, structure, boundaries)
    2. Focused Prospector audit (non-blocking)
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
uv run just test-unit

# 3. Check coverage
uv run just coverage

# 4. Fix uncovered code
# Add tests for new functionality

# 5. Run integration tests before commit
uv run just test-integration

# 6. Full CI locally
uv run just ci
```

## Performance

| Test Category | Count | Execution Time | Coverage |
|---------------|-------|----------------|----------|
| Fast/non-performance suite | 412 passed, 1 deselected | ~6s local | Default local gate |
| Real warm `rLayout` budget | opt-in | ~3.5s measured | 15s regression budget |
| Real cold dump-index build | opt-in | 295.6s measured | One-time bootstrap behavior |

**Optimization:**
- Unit tests use mocks (no file I/O)
- Fresh-process warm tests reuse validated durable artifacts
- Parallel execution possible with pytest-xdist
- The 2026-07-26 real acceptance run exported 116 types as 3,350 nodes and
  3,735 relationships; two fresh processes produced byte-identical files.
- Use `ddon-dwarf-reconstructor artifacts verify-source` for an explicit full-hash audit and
  `inspect` before any targeted repair or rebuild.

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
   uv run just coverage
   ```

3. **Import errors:**
   ```bash
   # Install in editable mode
   uv sync --python 3.14.6
   ```

4. **CI failures:**
   ```bash
   # Run exactly what CI runs
   uv run just coverage-ci
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
uv sync --python 3.14.6  # Installs all development groups
```

### Real rLayout performance budget

The real-asset regression budget is opt-in because the PS4 ELF is not part of a
normal checkout:

```powershell
$env:DDON_REAL_PERFORMANCE='1'
uv run just test-performance
```

The warm dependency-closure budget is 15 seconds. Current local measurements
are approximately 2.4 seconds after indexed pyelftools reference lookup. The
real compressed-dump index takes 295.6 seconds to build once and then serves a
fresh-process class/method lookup pair in about 1.52 ms. Preserve that sidecar
between runs.

The T059 authority regression deliberately runs real `rLayout` knowledge export
without `--exhaustive`. On 2026-07-29 it completed in 2.2 seconds, selected DIE
`0x117ec452`, recorded rejected candidate `0x76133`, and produced graph-file
hashes identical to the exhaustive authority probe. Unit tests separately
reject the cached duplicate and verify the manifest authority projection.

## Quality Gates

**Pre-commit checks:**
- All unit tests pass
- Coverage >=80% with high-risk group thresholds
- Ruff linting passes
- Pyrefly type checking passes
- deptry finds no missing or misplaced dependencies
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

## Maintainability and regression acceptance

The authoritative local sequence is:

```powershell
uv run just test-unit
uv run just check
uv run just coverage
```

The enforced thresholds are 80% total line coverage, 80% line coverage for
parsing/generation/orchestration/artifact groups, and 70% branch coverage for
those groups. High-risk tests explicitly cover incomplete, conflicting,
duplicate, unavailable, cyclic, and timeout evidence. Hypothesis is used for
pure declarator/array/type properties; `pytest-regressions` is reserved for
small deterministic metadata and ordering records, never generated headers.

Output acceptance is separate from coverage. Run
`uv run python -m tests.support.regression.output_manifest` against the external fixture and real
baselines. It compares sorted relative paths, byte counts, and SHA-256 values;
manifest metadata records source identity, producer, configuration, and cache
state but is not substituted for byte comparison. Use a fresh output directory
for every run and preserve durable source-bound caches.

The cold real-dump index rebuild is an explicit bootstrap, not a normal CI
step. The validated sidecar supports a warm `rLayout` run in roughly 3.5
seconds and two fresh-process runs were byte-identical. The explicit cold
rebuild completed in 295.6 seconds, published atomically, and its generated
header matched the warm manifest.
