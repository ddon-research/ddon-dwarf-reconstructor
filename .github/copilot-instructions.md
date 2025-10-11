---
description: 'Development conventions for DWARF-to-C++ header reconstruction project'
applyTo: '**/*'
---

# Project Development Guidelines

## Project Context

**Purpose:** Reconstructs C++ headers from DWARF debug info in ELF files for Dragon's Dogma Online modding.

**Architecture:** Domain-driven design with application/domain/infrastructure separation.

**Tech Stack:**
- Python 3.13+
- uv for dependency management
- pytest for testing
- pyelftools for DWARF parsing

## Running and Testing

### Execute Code

``````bash
# Single class
uv run python main.py resources/DDOORBIS.elf --generate MtObject

# Full hierarchy
uv run python main.py resources/DDOORBIS.elf --generate ClassName --full-hierarchy

# With options
uv run python main.py resources/DDOORBIS.elf --generate ClassName --output dir/ --verbose

# Quick execution with Makefile
make run CLASS=MtObject
make run-full CLASS=MtPropertyList

# Native executable (requires clang)
make build
build/main.exe --generate MtObject resources/DDOORBIS.elf
``````

### Testing (CRITICAL)

**ALWAYS use `uv run pytest` - never bare `pytest`**

``````bash
# Fast unit tests (preferred for development)
uv run pytest -m unit

# All tests
uv run pytest

# HTML coverage report
uv run pytest -m unit --cov-report=html

# Integration tests (slower, real ELF files)
uv run pytest -m integration

# Makefile shortcuts (recommended)
make test          # Unit tests only
make coverage      # HTML coverage report
make coverage-open # Coverage + open in browser
make ci            # Full CI suite (lint + typecheck + test)
``````

**Test Markers:**
- @pytest.mark.unit - Fast mocked tests (<1s, preferred)
- @pytest.mark.integration - Real ELF file tests (~3s)
- @pytest.mark.slow - Long-running tests
- @pytest.mark.performance - Performance benchmarks

### Code Quality

```bash
# Linting
uv run ruff check src/

# Formatting
uv run ruff format src/

# Type checking
uv run mypy src/

# All quality checks
make ci
```

## Python Code Conventions

### Type Safety (REQUIRED)

- **All functions** must have type hints for parameters and return values
- Use | None instead of Optional (Python 3.13+)
- Use NoReturn for functions that always exit
- Full mypy compliance required

```python
# Good
def resolve_type(die: DIE) -> str | None:
    """Resolve type name from DIE."""
    
# Bad - no type hints
def resolve_type(die):
    """Resolve type name from DIE."""
```

### Documentation (REQUIRED)

- **PEP 257** docstring format
- Document all parameters and return values
- Include algorithm explanations for complex functions
- Mention external dependencies

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
    
    return self._offset_index.get(offset)
```

### Code Style

- **Line limit:** 100 characters
- **Indentation:** 4 spaces
- **Import order:** standard library, third-party, local modules
- **Function names:** descriptive, verb-based (parse_class_info, not parse)
- **Exception handling:** Use specific exception types, avoid bare except

### Performance

- Use lazy loading for expensive operations
- Cache frequently accessed data (see TypeResolver cache example)
- Document performance characteristics (O(n), memory usage)
- Include performance assertions in tests

## Testing Guidelines

### Prefer Unit Tests

**Use mocks for external dependencies** (files, ELF parsing, DWARF structures):

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

### Integration Tests (When Needed)

**Use real ELF files** for end-to-end validation:

```python
@pytest.mark.integration
def test_mtpropertylist_full_hierarchy():
    """Integration test with real ELF file."""
    with DwarfGenerator(ELF_PATH) as generator:
        header = generator.generate_complete_hierarchy_header("MtPropertyList")
        assert "typedef unsigned short u16;" in header
        assert "class MtObject" in header
```

### Test Best Practices

- Base mocks on actual DWARF dump structures (resources/*.dwarfdump)
- Mock at module boundaries (ELFFile), not internal functions
- Test one component at a time
- Include edge cases and error conditions
- Use descriptive test names indicating what is tested
- Mark slow tests with @pytest.mark.slow

## Documentation Style

### Writing Style (CRITICAL)

**Technical, concise, professional - NO fluff:**
- No emojis
- No sales language or marketing speak
- No excessive enthusiasm or casual tone
- No redundant explanations
- Focus on facts, code, and concrete examples

**Good:**
> Reconstructs C++ class definitions from DWARF debug information in ELF files.

**Bad:**
>  The amazing DWARF reconstructor that will revolutionize your workflow! 

### Documentation Structure

**Location:**
- Technical docs: docs/ directory
- README.md: Project root
- Architecture: docs/ARCHITECTURE.md
- Testing: docs/TESTING.md
- History/Plans: Root directory (REFACTORING_PLAN.md, CLAUDE.md)

**README.md sections:**
1. Title and description (1-2 lines)
2. Features (bullet points)
3. Requirements
4. Installation (commands only)
5. Usage (with examples)
6. Architecture (brief overview + link to docs/)
7. Development (commands with comments)
8. Documentation (links to docs/)
9. Performance (table with metrics)
10. Limitations (honest list)
11. Comparison (table with alternatives)
12. License

**ARCHITECTURE.md sections:**
1. System overview (diagram)
2. Directory structure (tree)
3. Core components (with code signatures)
4. Data flow (step-by-step)
5. Performance optimizations (table)
6. Design principles
7. Extension points
8. Limitations
9. References

**TESTING.md sections:**
1. Quick start (commands first)
2. Test categories
3. Test structure (tree)
4. Configuration
5. Writing tests (with examples)
6. Coverage
7. CI/CD pipeline
8. Development workflow
9. Performance (table)
10. Troubleshooting
11. References

### Code Examples in Docs

**Always include:**
- Complete working examples
- Actual file paths from the project
- Real command output when relevant
- Type hints in Python examples

**Avoid:**
- Pseudocode
- Incomplete snippets (unless marked clearly)
- Made-up class/function names
- Vague "example" placeholders

## File Organization

### Project Structure

```
src/ddon_dwarf_reconstructor/
 application/generators/     # Orchestration layer
 domain/
    models/dwarf/          # Data structures
    repositories/cache/     # Caching
    services/
        parsing/           # DWARF parsing
        generation/        # C++ generation
 infrastructure/
     config/                # Configuration
     logging/               # Logging

tests/
 application/generators/    # Mirror src structure
 domain/services/parsing/
 infrastructure/config/

docs/
 ARCHITECTURE.md
 TESTING.md
 knowledge-base/            # Research notes

Root files:
 main.py                    # Entry point
 README.md
 pyproject.toml
 pytest.ini
 Makefile
```

### Where to Put New Code

- **Orchestration:** application/generators/
- **Business logic:** domain/services/
- **Data models:** domain/models/dwarf/
- **Config:** infrastructure/config/
- **Utils:** infrastructure/utils/
- **Tests:** Mirror the src/ structure in tests/

## Common Workflows

### Adding a New Feature

1. Identify the layer (application/domain/infrastructure)
2. Create the module in the appropriate location
3. Write unit tests with mocks first
4. Implement the feature
5. Run tests: uv run pytest -m unit
6. Check coverage: uv run pytest -m unit --cov-report=html
7. Add integration test if needed
8. Run quality checks: make ci
9. Update documentation if public API changed

### Fixing a Bug

1. Write a failing test that reproduces the bug
2. Fix the bug
3. Verify test passes: uv run pytest -m unit
4. Check no regressions: uv run pytest
5. Update documentation if behavior changed

### Updating Documentation

1. Use the established style (technical, concise, no fluff)
2. Include concrete examples with real code
3. Update all affected docs (README, ARCHITECTURE, TESTING)
4. Keep docs in sync with code
5. Put technical docs in docs/, not root

## AI Assistant Behavior

### When Asked to Run Tests

**Do this:**
```bash
uv run pytest -m unit
```

**Not this:**
```bash
pytest  # Wrong - missing uv run
python -m pytest  # Wrong - use uv run
```

### When Asked to Document

**Do this:**
- Update existing docs in docs/ directory
- Use technical, concise style
- Include code examples with type hints
- Add performance metrics when relevant

**Not this:**
- Create new ad-hoc documentation files
- Use emojis, sales language, or casual tone
- Generate verbose explanations without examples
- Skip code examples or use pseudocode

### When Writing Summaries

- Keep technical and concise
- No emojis or casual language
- Focus on what was done, not motivational language
- Include specific metrics when relevant

### When Making Changes

- Run tests after each change: uv run pytest -m unit
- Check for errors: uv run ruff check src/
- Verify type hints: uv run mypy src/
- Update docs if public API changed

## CI/CD Integration

**GitHub Actions:**
- Unit tests run on every push/PR (Python 3.13, ubuntu-latest)
- Coverage minimum: 30% (enforced)
- Quality gates: ruff, mypy, pytest

**Artifacts:**
- test-results.xml (JUnit XML)
- coverage.xml (Cobertura XML)
- htmlcov/ (HTML coverage)

**Retention:** 30 days

## License

GPLv3 - See LICENSE file.
