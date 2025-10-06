---
description: 'Python coding conventions for DWARF-to-C++ header reconstruction'
applyTo: '**/*.py'
---

# Python Coding Conventions

## Type Safety

- All functions must have type hints for parameters and return values
- Use `typing` module imports: `List[str]`, `Dict[str, int]`, `Optional[T]`
- Prefer `| None` over `Optional` for Python 3.10+
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

- Test critical paths and edge cases
- Include performance benchmarks for core functionality
- Document test cases in docstrings
- Use descriptive test function names

## Example

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
