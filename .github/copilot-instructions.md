---
description: 'Python coding conventions for DWARF-to-C++ header reconstruction'
applyTo: '**/*.py'
---

# Python Coding Conventions

## Type Safety

- All functions must have type hints for parameters and return values
- Use `typing` module imports: `List[str]`, `Dict[str, int]`, `Optional[T]`
- Prefer `| None` over `Optional` for Python 3.13+
- Use `NoReturn` for functions that always exit

## Documentation

- PEP 257 docstring format
- Document all parameters and return values
- Include algorithm explanations for complex functions
- Mention external dependencies and their purpose

## Code Structure

- Function names: descriptive, verb-based
- Break complex functions into smaller components
- Handle edge cases explicitly (empty inputs, invalid types)
- Use specific exception types, avoid bare `except`

## Performance Considerations

- Lazy loading for expensive operations
- Cache frequently accessed data
- Document performance characteristics (O(n), memory usage)
- Include performance assertions in tests

## Style Guide

- Line limit: 100 characters
- Indentation: 4 spaces
- Blank lines: separate functions/classes appropriately
- Import order: standard library, third-party, local modules

## Testing Requirements

### Professional Testing Infrastructure

The project uses comprehensive testing with xUnit reporting, code coverage, and automated CI/CD:

- **Test Execution**: ALWAYS use `uv run pytest` (never bare `pytest`)
- **Test Categories**: Use appropriate pytest markers
  - `@pytest.mark.unit`: Fast mocked tests (preferred for development)
  - `@pytest.mark.integration`: Real ELF file tests (slower)
  - `@pytest.mark.slow`: Long-running tests
  - `@pytest.mark.performance`: Performance benchmarks

### Development Testing Commands

```bash
# Unit tests (fast, mocked - recommended)
uv run pytest -m "unit"

# All tests
uv run pytest

# With coverage
uv run pytest -m "unit" --cov-report=html

# Makefile shortcuts
make test          # Unit tests
make coverage      # HTML coverage report
```

### Test Writing Guidelines

- **Prefer Unit Tests**: Use mocks for external dependencies (files, ELF parsing)
- **Realistic Mocks**: Base mocks on actual DWARF dump structures
- **Test Edge Cases**: Include error conditions and boundary cases
- **Performance Awareness**: Mark slow tests with `@pytest.mark.slow`
- **Descriptive Names**: Clear test function names indicating what is tested

### CI/CD Integration

- **GitHub Actions**: Runs unit tests on Python 3.13, ubuntu-latest
- **Coverage Threshold**: 30% minimum (38% achieved with unit tests)
- **Quality Gates**: Ruff linting, MyPy type checking, test coverage
- **Artifacts**: JUnit XML, coverage reports, HTML coverage visualization

## Code Examples

### Production Code
```python
def extract_die_by_offset(offset: int) -> DIE | None:
    """
    Retrieve DIE by its DWARF offset using cached index.
    
    Uses lazy-loaded offset index for O(1) lookup after initial build.
    Returns None if offset not found in any compilation unit.
    
    Args:
        offset: DWARF offset of the target DIE
        
    Returns:
        DIE object if found, None otherwise
        
    Raises:
        ValueError: If offset is negative
    """
    if offset < 0:
        raise ValueError(f"Invalid offset: {offset}")
    
    # Build index on first access
    if not self._offset_index:
        self._build_offset_index()
    
    return self._offset_index.get(offset)
```

### Unit Test (Preferred)
```python
@pytest.mark.unit
def test_find_class_success(mocker):
    """Test finding a class with realistic mocks."""
    # Create realistic mocks based on actual DWARF structure
    mock_die = Mock()
    mock_die.tag = "DW_TAG_class_type"
    mock_die.attributes = {'DW_AT_name': Mock(value=b'MtObject')}
    
    mock_cu = Mock()
    mock_cu.iter_DIEs.return_value = [mock_die]
    
    mock_elf = Mock()
    mock_elf.get_dwarf_info.return_value.iter_CUs.return_value = [mock_cu]
    
    mocker.patch("builtins.open")
    mocker.patch("...ELFFile", return_value=mock_elf)
    
    with DwarfGenerator("test.elf") as generator:
        result = generator.find_class("MtObject")
        assert result == (mock_cu, mock_die)
```

### Integration Test (When Needed)
```python
@pytest.mark.integration
def test_real_elf_processing(elf_file_path):
    """Integration test with real ELF file."""
    with DwarfGenerator(elf_file_path) as generator:
        header = generator.generate_header("MtObject")
        assert "#ifndef MTOBJECT_H" in header
        assert "class MtObject" in header
```
