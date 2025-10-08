# pyelftools API Reference and Usage Patterns

Source: pyelftools (https://github.com/eliben/pyelftools)
**Policy**: We use pyelftools directly without reinventing DWARF parsing

## Overview

pyelftools is a pure-Python library for parsing ELF and DWARF. We commit to using their API directly:
- **Established API**: Use their proven `DWARFInfo`, `CompilationUnit`, `DIE` classes 
- **No reinvention**: Avoid custom abstractions over pyelftools
- **Direct usage**: Leverage their methods like `iter_CUs()`, `get_DIE_from_attribute()`
- **Upstream benefits**: Automatically get bug fixes and improvements

## Core API Structure

### Entry Point - ELFFile
```python
from elftools.elf.elffile import ELFFile

with open(filename, 'rb') as f:
    elffile = ELFFile(f)
    
    # Check for DWARF info
    if elffile.has_dwarf_info():
        dwarfinfo = elffile.get_dwarf_info()
```

### DWARF Information - DWARFInfo
```python
# Main DWARF context object
DWARFInfo
  ├── iter_CUs() → CompilationUnit[]        # Iterate compilation units
  ├── get_DIE_from_offset(offset) → DIE    # Direct offset lookup  
  └── line_program_for_CU(cu) → LineProgram # Line number info
```

### Compilation Units - CompilationUnit
```python
CompilationUnit
  ├── get_top_DIE() → DIE                  # Root DIE (typically DW_TAG_compile_unit)
  ├── iter_DIEs() → DIE[]                  # All DIEs in this CU
  ├── cu_offset: int                       # CU offset in .debug_info
  └── header: dict                         # DWARF header info
```

### Debug Information Entries - DIE
```python
DIE
  ├── tag: str                             # e.g., "DW_TAG_class_type"
  ├── attributes: dict[str, Attribute]     # DWARF attributes
  ├── offset: int                          # DIE offset
  ├── iter_children() → DIE[]              # Child DIEs
  ├── get_parent() → DIE                   # Parent DIE
  └── cu: CompilationUnit                  # Owning compilation unit
```

## Essential Usage Patterns

### Basic DWARF Processing
```python
# Standard pattern from pyelftools examples
def process_file(filename):
    with open(filename, 'rb') as f:
        elffile = ELFFile(f)
        
        if not elffile.has_dwarf_info():
            return
            
        dwarfinfo = elffile.get_dwarf_info()
        
        for cu in dwarfinfo.iter_CUs():
            top_die = cu.get_top_DIE()
            print(f"CU: {top_die.get_full_path()}")
```

### DIE Attribute Access
```python
# Access attributes using DWARF attribute names
die = some_die
name = die.attributes.get('DW_AT_name')
type_die = die.attributes.get('DW_AT_type')

# Use built-in reference resolution
if type_die:
    resolved_die = cu.get_DIE_from_attribute(type_die)
```

### Type Following Pattern
```python
def resolve_type(cu: CompilationUnit, die: DIE) -> Optional[DIE]:
    """Follow DW_AT_type references - standard pyelftools pattern."""
    type_attr = die.attributes.get('DW_AT_type')
    if type_attr:
        return cu.get_DIE_from_attribute(type_attr)  # Built-in method
    return None
```

### Tree Traversal
```python
def find_class_by_name(cu: CompilationUnit, class_name: str) -> Optional[DIE]:
    """Find class DIE by name - use pyelftools iteration."""
    for die in cu.iter_DIEs():
        if (die.tag == 'DW_TAG_class_type' and 
            'DW_AT_name' in die.attributes and
            die.attributes['DW_AT_name'].value.decode() == class_name):
            return die
    return None
```

## Key Characteristics

### Eager Loading
- All attributes parsed when DIE is read
- Simpler API, higher memory usage for large files
- **Use as-is**: Don't try to optimize with custom lazy loading

### Reference Resolution  
- Built-in `get_DIE_from_attribute()` method handles offsets
- **Use built-in**: Avoid reimplementing reference following
- Handles cross-CU references automatically

### Stream-Based Architecture
- Uses file streams with seeking
- **Reuse streams**: Don't create custom file handling

## Our Implementation Strategy

### What We Add (Minimal Layers)

1. **PS4 ELF Compatibility** 
   - Minimal patches for PS4-specific ELF variations
   - **Principle**: Patch only what's needed, use pyelftools for everything else

2. **C++ Header Generation**
   - Business logic for C++ syntax generation  
   - **Principle**: Use pyelftools DIEs as-is, don't wrap them

3. **Type Resolution Helpers**
   - Convenience methods for common DWARF patterns
   - **Principle**: Build on pyelftools methods, don't replace them

4. **Configuration & Logging**
   - Project-specific configuration and logging
   - **Principle**: Infrastructure only, no DWARF parsing

### What We Don't Reinvent

1. **DWARF Parsing**: Use pyelftools `DWARFInfo`, `CompilationUnit`, `DIE` directly
2. **Attribute Access**: Use their `attributes` dict and `get_DIE_from_attribute()`  
3. **Tree Navigation**: Use their `iter_children()`, `iter_DIEs()`, `get_parent()`
4. **Stream Handling**: Use their file stream management

## Strengths of pyelftools

1. **Well-Tested**: Mature, stable library
2. **Standards-Compliant**: Follows DWARF spec closely
3. **Easy to Use**: Pythonic API
4. **No Dependencies**: Pure Python

## Limitations

1. **Memory Usage**: Eager loading can be expensive
2. **Performance**: Slower than native parsers (like libdwarf)
3. **PS4 Support**: Requires patching for non-standard ELFs
4. **Large Files**: Can be slow on multi-GB ELFs

## Integration Strategy

Our implementation wraps pyelftools with:

```
User Code
    ↓
DWARFParser (our wrapper)
    ↓
elf_patches (PS4 compatibility)
    ↓
pyelftools (core parsing)
```

Benefits:
- Leverage pyelftools' robust parsing
- Add PS4-specific handling
- Provide higher-level abstractions
- Type-safe interface

## Future Optimization Opportunities

Based on Ghidra's approach, could add:

1. **Lazy Attribute Loading**
   ```python
   class LazyDIE:
       def __init__(self, offset, abbrev_code):
           self._offset = offset
           self._abbrev_code = abbrev_code
           self._attributes = None  # Load on demand

       def get_attribute(self, name):
           if self._attributes is None:
               self._load_attributes()
           return self._attributes.get(name)
   ```

2. **Index-Based Relationships**
   ```python
   class DWARFProgram:
       def __init__(self):
           self.dies = []  # Flat list
           self.parent_map = {}  # index -> parent_index
           self.children_map = {}  # index -> [child_indices]
   ```

3. **Streaming Parse with Checkpoints**
   - Save parse state at CU boundaries
   - Resume from checkpoint
   - Process incrementally

4. **Abbreviation Pool**
   - Share abbreviation objects across CUs
   - Reduce memory duplication
   - Cache commonly-used patterns

## Current Performance

For our DDOORBIS.elf file (with DWARF):
- **CUs**: 2,305 compilation units
- **Search time**: ~1-2 minutes to find symbol
- **Memory**: Moderate (Python overhead)

Acceptable for:
- One-time analysis
- Development/research
- Moderate-sized binaries

May need optimization for:
- Real-time analysis
- Very large binaries (>1GB)
- Batch processing

## Recommendations

1. **Keep pyelftools** for core parsing (proven, reliable)
2. **Layer optimizations** as needed (lazy loading, indexing)
3. **Profile first** before optimizing (measure bottlenecks)
4. **Consider hybrid approach** (pyelftools + custom index)
