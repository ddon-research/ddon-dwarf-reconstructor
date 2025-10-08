# PyElfTools API Reference

Comprehensive reference for working with `pyelftools` in DWARF parsing applications.

## Overview

**pyelftools** is a pure-Python library for parsing ELF files and extracting DWARF debug information. It provides a robust, well-tested API that eliminates the need for custom DWARF parsing logic.

**Key Philosophy**: Reuse proven data structures and methods instead of reinventing DWARF parsing.

## Core Classes

### ELFFile

**Location**: `elftools.elf.elffile.ELFFile`

The primary entry point for ELF file analysis.

#### Constructor

```python
from elftools.elf.elffile import ELFFile

with open("binary.elf", "rb") as f:
    elf = ELFFile(f)
```

#### Key Methods

| Method | Return Type | Description |
|--------|-------------|-------------|
| `has_dwarf_info()` | `bool` | Check if DWARF debug info exists |
| `get_dwarf_info()` | `DWARFInfo` | Access DWARF information structure |
| `get_section_by_name(name)` | `Section \| None` | Retrieve specific ELF section |
| `iter_sections()` | `Iterator[Section]` | Iterate all ELF sections |

#### Example Usage

```python
with open("game.elf", "rb") as f:
    elf = ELFFile(f)

    if not elf.has_dwarf_info():
        raise ValueError("No DWARF information found")

    dwarf_info = elf.get_dwarf_info()
```

---

### DWARFInfo

**Location**: `elftools.dwarf.dwarfinfo.DWARFInfo`

Provides access to the complete DWARF debug information structure.

#### Key Methods

| Method | Return Type | Description | Performance |
|--------|-------------|-------------|-------------|
| `iter_CUs()` | `Iterator[CompileUnit]` | Iterate all compilation units | O(n) - sequential scan |
| `get_DIE_from_lut_entry(entry)` | `DIE` | Lookup DIE via .debug_pub* tables | O(1) with LUT |
| `line_program_for_CU(cu)` | `LineProgram` | Get line number program for CU | O(1) cached |

#### Memory Characteristics

- **Lazy Loading**: DWARF sections loaded on-demand
- **No Global Cache**: DIEs are not cached by default
- **Iteration Cost**: Full CU iteration parses all debug info

#### Example Usage

```python
dwarf_info = elf.get_dwarf_info()

# Iterate compilation units (expensive for large binaries)
for cu in dwarf_info.iter_CUs():
    print(f"CU at offset: 0x{cu.cu_offset:x}")

# Get line program for source location mapping
line_program = dwarf_info.line_program_for_CU(cu)
if line_program:
    for entry in line_program.header.file_entry:
        print(f"Source file: {entry.name}")
```

---

### CompileUnit

**Location**: `elftools.dwarf.compileunit.CompileUnit`

Represents a single compilation unit (typically one source file and its includes).

#### Key Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `cu_offset` | `int` | Offset in .debug_info section |
| `cu_die_offset` | `int` | Offset of root DIE |
| `header` | `CompileUnitHeader` | CU header with version, address size |

#### Key Methods

| Method | Return Type | Description | Performance |
|--------|-------------|-------------|-------------|
| `iter_DIEs()` | `Iterator[DIE]` | Iterate all DIEs in this CU | O(n) depth-first traversal |
| `get_top_DIE()` | `DIE` | Get root DIE of this CU | O(1) |
| `get_full_path()` | `str \| None` | Get compilation directory path | O(1) |

#### Performance Notes

- **`iter_DIEs()`**: Fully parses the CU's DIE tree
- **Early Exit Strategy**: Stop iteration as soon as target is found
- **No Random Access**: Cannot jump to arbitrary DIE without iteration

#### Example Usage

```python
for cu in dwarf_info.iter_CUs():
    # Get root DIE (typically DW_TAG_compile_unit)
    root_die = cu.get_top_DIE()

    # Iterate all DIEs in this CU
    for die in cu.iter_DIEs():
        if die.tag == "DW_TAG_class_type":
            name = die.attributes.get("DW_AT_name")
            if name and name.value == b"MtObject":
                return cu, die  # Early exit
```

---

### DIE (Debugging Information Entry)

**Location**: `elftools.dwarf.die.DIE`

The fundamental unit of DWARF information representing types, variables, functions, etc.

#### Key Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `tag` | `str` | DWARF tag (e.g., "DW_TAG_class_type") |
| `offset` | `int` | Absolute offset in .debug_info |
| `attributes` | `OrderedDict[str, AttributeValue]` | DIE attributes |
| `size` | `int` | Size of this DIE in bytes |
| `cu` | `CompileUnit` | Parent compilation unit |

#### Key Methods

| Method | Return Type | Description | Performance |
|--------|-------------|-------------|-------------|
| `iter_children()` | `Iterator[DIE]` | Iterate immediate children | O(n) children count |
| `get_parent()` | `DIE \| None` | Get parent DIE | O(1) |
| `get_DIE_from_attribute(attr_name)` | `DIE \| None` | Resolve reference attribute | O(1) with offset lookup |
| `has_children` | `bool` | Check if DIE has children | O(1) |

#### Critical Method: `get_DIE_from_attribute()`

This is the **most important method** for type resolution. It follows DWARF references (DW_AT_type, etc.) to resolve type information.

```python
# Resolve member type
member_die = class_die.iter_children()[0]
type_attr = member_die.attributes.get("DW_AT_type")

if type_attr:
    # Incorrect manual approach:
    # type_offset = type_attr.value
    # type_die = find_die_at_offset(type_offset)  # DON'T DO THIS

    # Correct pyelftools approach:
    type_die = member_die.get_DIE_from_attribute("DW_AT_type")
    if type_die:
        type_name = type_die.attributes.get("DW_AT_name")
```

#### Common Attributes

| Attribute | Type Tags | Value Type | Description |
|-----------|-----------|------------|-------------|
| `DW_AT_name` | Most types | `bytes` | Name of the entity |
| `DW_AT_byte_size` | Types, structs | `int` | Size in bytes |
| `DW_AT_type` | Members, params | `int` (offset) | Type reference |
| `DW_AT_data_member_location` | Members | `int` | Offset within parent |
| `DW_AT_accessibility` | Members, methods | `int` | public/private/protected |
| `DW_AT_virtuality` | Methods | `int` | Virtual method indicator |
| `DW_AT_decl_file` | Most | `int` | Declaration file index |
| `DW_AT_decl_line` | Most | `int` | Declaration line number |

#### Example Usage

```python
# Parse class members
for child_die in class_die.iter_children():
    if child_die.tag == "DW_TAG_member":
        # Get member name
        name_attr = child_die.attributes.get("DW_AT_name")
        member_name = name_attr.value.decode("utf-8") if name_attr else "unnamed"

        # Resolve member type using pyelftools
        type_die = child_die.get_DIE_from_attribute("DW_AT_type")
        if type_die:
            type_name_attr = type_die.attributes.get("DW_AT_name")
            type_name = type_name_attr.value.decode("utf-8") if type_name_attr else "unknown"

        # Get member offset
        offset_attr = child_die.attributes.get("DW_AT_data_member_location")
        offset = offset_attr.value if offset_attr else None

        print(f"{type_name} {member_name};  // offset: 0x{offset:x}")
```

---

## Common DWARF Tags

| Tag | Purpose | Common Attributes |
|-----|---------|-------------------|
| `DW_TAG_compile_unit` | Root of compilation unit | `DW_AT_name`, `DW_AT_language`, `DW_AT_comp_dir` |
| `DW_TAG_class_type` | C++ class | `DW_AT_name`, `DW_AT_byte_size`, `DW_AT_decl_file` |
| `DW_TAG_structure_type` | C struct | `DW_AT_name`, `DW_AT_byte_size` |
| `DW_TAG_union_type` | Union | `DW_AT_name`, `DW_AT_byte_size` |
| `DW_TAG_enumeration_type` | Enum | `DW_AT_name`, `DW_AT_byte_size` |
| `DW_TAG_member` | Class/struct member | `DW_AT_name`, `DW_AT_type`, `DW_AT_data_member_location` |
| `DW_TAG_subprogram` | Method/function | `DW_AT_name`, `DW_AT_type`, `DW_AT_virtuality` |
| `DW_TAG_formal_parameter` | Function parameter | `DW_AT_name`, `DW_AT_type`, `DW_AT_artificial` |
| `DW_TAG_inheritance` | Base class | `DW_AT_type`, `DW_AT_data_member_location` |
| `DW_TAG_typedef` | Type alias | `DW_AT_name`, `DW_AT_type` |
| `DW_TAG_pointer_type` | Pointer | `DW_AT_type` |
| `DW_TAG_const_type` | Const qualifier | `DW_AT_type` |
| `DW_TAG_reference_type` | Reference | `DW_AT_type` |
| `DW_TAG_array_type` | Array | `DW_AT_type` |
| `DW_TAG_subrange_type` | Array dimension | `DW_AT_upper_bound`, `DW_AT_count` |
| `DW_TAG_enumerator` | Enum value | `DW_AT_name`, `DW_AT_const_value` |

---

## Performance Best Practices

### 1. Early Exit Strategy

Stop iteration as soon as the target is found:

```python
def find_class(self, class_name: str) -> tuple[CompileUnit, DIE] | None:
    target_name = class_name.encode("utf-8")

    for cu in self.dwarf_info.iter_CUs():
        for die in cu.iter_DIEs():
            if die.tag == "DW_TAG_class_type":
                name_attr = die.attributes.get("DW_AT_name")
                if name_attr and name_attr.value == target_name:
                    return cu, die  # Exit immediately

    return None
```

### 2. Prefer Specific Tag Filtering

Filter early to avoid processing irrelevant DIEs:

```python
# Good: Filter by tag before processing
for die in cu.iter_DIEs():
    if die.tag not in ("DW_TAG_class_type", "DW_TAG_structure_type"):
        continue
    # Process only class/struct types
```

### 3. Cache Expensive Lookups

```python
class DwarfGenerator:
    def __init__(self, elf_path: Path):
        self.elf_path = elf_path
        self._typedef_cache: dict[str, str] = {}

    def resolve_typedef(self, name: str) -> str | None:
        if name in self._typedef_cache:
            return self._typedef_cache[name]

        # Expensive lookup
        result = self._search_typedef(name)
        self._typedef_cache[name] = result
        return result
```

### 4. Use `get_DIE_from_attribute()` for References

**Never manually resolve offsets**. Always use pyelftools' built-in resolution:

```python
# WRONG: Manual offset resolution
type_offset = die.attributes["DW_AT_type"].value
type_die = self._find_die_at_offset(type_offset)  # Expensive!

# CORRECT: Use pyelftools API
type_die = die.get_DIE_from_attribute("DW_AT_type")  # Efficient!
```

---

## Error Handling

### Common Issues

1. **Missing Attributes**: Not all DIEs have all attributes
2. **Byte String Values**: Names are typically `bytes`, not `str`
3. **Malformed DWARF**: Non-standard ELF files (e.g., PS4)

### Defensive Coding Patterns

```python
# Check for attribute existence
name_attr = die.attributes.get("DW_AT_name")
if name_attr:
    # Handle bytes vs string
    if isinstance(name_attr.value, bytes):
        name = name_attr.value.decode("utf-8", errors="ignore")
    else:
        name = str(name_attr.value)
else:
    name = "unnamed"

# Handle failed reference resolution
try:
    type_die = die.get_DIE_from_attribute("DW_AT_type")
    if not type_die:
        return "unknown_type"
except Exception as e:
    logger.warning(f"Failed to resolve type: {e}")
    return "unknown_type"
```

---

## References

- [pyelftools GitHub](https://github.com/eliben/pyelftools)
- [pyelftools Documentation](https://github.com/eliben/pyelftools/wiki)
- [DWARF 4 Specification](http://dwarfstd.org/doc/DWARF4.pdf)

---

**Next**: See [pyelftools-examples.md](pyelftools-examples.md) for practical usage patterns.
