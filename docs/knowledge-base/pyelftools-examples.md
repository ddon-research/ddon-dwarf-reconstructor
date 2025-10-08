# PyElfTools Examples

Practical examples and patterns for common DWARF parsing tasks using pyelftools.

## Table of Contents

1. [Basic Setup and Initialization](#basic-setup-and-initialization)
2. [Finding Types by Name](#finding-types-by-name)
3. [Type Resolution Patterns](#type-resolution-patterns)
4. [Traversing Class Hierarchies](#traversing-class-hierarchies)
5. [Parsing Members and Methods](#parsing-members-and-methods)
6. [Handling Arrays and Complex Types](#handling-arrays-and-complex-types)
7. [Working with Enums](#working-with-enums)
8. [Anonymous Types (Unions, Structs)](#anonymous-types-unions-structs)
9. [Progress Tracking](#progress-tracking)

---

## Basic Setup and Initialization

### Context Manager Pattern

**Always use context managers** to ensure proper resource cleanup:

```python
from pathlib import Path
from elftools.elf.elffile import ELFFile

class DwarfGenerator:
    def __init__(self, elf_path: Path):
        self.elf_path = elf_path
        self.elf_file: ELFFile | None = None
        self.dwarf_info = None

    def __enter__(self) -> "DwarfGenerator":
        self.file_handle = open(self.elf_path, "rb")
        self.elf_file = ELFFile(self.file_handle)

        if not self.elf_file.has_dwarf_info():
            raise ValueError(f"No DWARF info found in {self.elf_path}")

        self.dwarf_info = self.elf_file.get_dwarf_info()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, "file_handle"):
            self.file_handle.close()

# Usage
with DwarfGenerator(Path("game.elf")) as gen:
    result = gen.find_class("MtObject")
```

---

## Finding Types by Name

### Basic Type Search with Early Exit

```python
def find_class(self, class_name: str) -> tuple[CompileUnit, DIE] | None:
    """Find type by name with early exit optimization."""
    target_name = class_name.encode("utf-8")
    fallback_candidate = None

    # Iterate compilation units
    for cu in self.dwarf_info.iter_CUs():
        for die in cu.iter_DIEs():
            # Filter by relevant tags
            if die.tag in (
                "DW_TAG_class_type",
                "DW_TAG_structure_type",
                "DW_TAG_union_type",
            ):
                name_attr = die.attributes.get("DW_AT_name")
                if name_attr and name_attr.value == target_name:
                    # Prefer complete definitions (with size)
                    size_attr = die.attributes.get("DW_AT_byte_size")
                    if size_attr and size_attr.value > 0:
                        logger.info(f"Found {class_name} (size: {size_attr.value} bytes)")
                        return cu, die  # Early exit

                    # Or definitions with children
                    if die.has_children:
                        logger.info(f"Found {class_name} (has members)")
                        return cu, die

                    # Save forward declaration as fallback
                    if fallback_candidate is None:
                        fallback_candidate = (cu, die)

    return fallback_candidate
```

### Finding Typedefs with Caching

```python
def find_typedef(self, typedef_name: str) -> tuple[str, str] | None:
    """Find typedef with caching for performance."""
    # Check cache first
    if typedef_name in self._typedef_cache:
        return self._typedef_cache[typedef_name]

    target_name = typedef_name.encode("utf-8")

    for cu in self.dwarf_info.iter_CUs():
        for die in cu.iter_DIEs():
            if die.tag == "DW_TAG_typedef":
                name_attr = die.attributes.get("DW_AT_name")
                if name_attr and name_attr.value == target_name:
                    # Resolve underlying type
                    underlying_type = self.resolve_type_name(die)

                    # Cache result
                    result = (typedef_name, underlying_type)
                    self._typedef_cache[typedef_name] = result
                    return result

    return None
```

---

## Type Resolution Patterns

### Recursive Type Resolution

The core pattern for resolving DWARF type references:

```python
def resolve_type_name(self, die: DIE, type_attr_name: str = "DW_AT_type") -> str:
    """Recursively resolve type names through DWARF references."""
    try:
        # Check if type attribute exists
        if type_attr_name not in die.attributes:
            return "void"  # Methods without return type

        # Use pyelftools' built-in resolution
        type_die = die.get_DIE_from_attribute(type_attr_name)
        if not type_die:
            return "unknown_type"

        # Get direct type name
        name_attr = type_die.attributes.get("DW_AT_name")
        if name_attr:
            return name_attr.value.decode("utf-8")

        # Handle type modifiers (pointer, const, reference)
        if type_die.tag == "DW_TAG_pointer_type":
            pointed_type = self.resolve_type_name(type_die)
            return f"{pointed_type}*"

        if type_die.tag == "DW_TAG_const_type":
            base_type = self.resolve_type_name(type_die)
            return f"const {base_type}"

        if type_die.tag == "DW_TAG_reference_type":
            base_type = self.resolve_type_name(type_die)
            return f"{base_type}&"

        if type_die.tag == "DW_TAG_array_type":
            return self.resolve_array_type(type_die)

        # Unknown type
        return str(type_die.tag).replace("DW_TAG_", "")

    except Exception as e:
        logger.warning(f"Failed to resolve type: {e}")
        return "unknown_type"
```

### Handling Pointer Chains

```python
def resolve_full_type(self, die: DIE) -> str:
    """Resolve complete type including multiple levels of indirection."""
    qualifiers = []
    current_die = die

    # Traverse type chain
    while current_die:
        type_die = current_die.get_DIE_from_attribute("DW_AT_type")
        if not type_die:
            break

        # Collect qualifiers
        if type_die.tag == "DW_TAG_pointer_type":
            qualifiers.append("*")
        elif type_die.tag == "DW_TAG_const_type":
            qualifiers.append("const")
        elif type_die.tag == "DW_TAG_reference_type":
            qualifiers.append("&")
        else:
            # Found base type
            name_attr = type_die.attributes.get("DW_AT_name")
            if name_attr:
                base_type = name_attr.value.decode("utf-8")
                # Apply qualifiers in reverse order
                result = base_type
                for qual in reversed(qualifiers):
                    if qual == "const":
                        result = f"const {result}"
                    else:
                        result = f"{result}{qual}"
                return result
            break

        current_die = type_die

    return "unknown_type"
```

---

## Traversing Class Hierarchies

### Building Inheritance Chain

```python
def build_inheritance_hierarchy(self, class_name: str) -> list[str]:
    """Build complete inheritance hierarchy from derived to base."""
    hierarchy = []
    current_class = class_name
    visited = set()  # Prevent cycles

    while current_class and current_class not in visited:
        visited.add(current_class)

        # Find class definition
        result = self.find_class(current_class)
        if not result:
            break

        cu, class_die = result

        # Look for base class
        for child in class_die.iter_children():
            if child.tag == "DW_TAG_inheritance":
                base_type = self.resolve_type_name(child)
                if base_type != "unknown_type":
                    hierarchy.append(base_type)
                    current_class = base_type
                    break
        else:
            # No inheritance found
            break

    return list(reversed(hierarchy))  # Base to derived
```

### Collecting Full Hierarchy Information

```python
def collect_hierarchy_classes(self, class_name: str) -> dict[str, ClassInfo]:
    """Collect ClassInfo for entire inheritance hierarchy."""
    all_classes = {}
    hierarchy_order = []

    current_class = class_name
    visited = set()

    while current_class and current_class not in visited:
        visited.add(current_class)

        result = self.find_class(current_class)
        if not result:
            break

        cu, class_die = result
        class_info = self.parse_class_info(cu, class_die)

        all_classes[current_class] = class_info
        hierarchy_order.insert(0, current_class)  # Base first

        # Find next base class
        next_class = None
        for child in class_die.iter_children():
            if child.tag == "DW_TAG_inheritance":
                next_class = self.resolve_type_name(child)
                break

        current_class = next_class

    return all_classes, hierarchy_order
```

---

## Parsing Members and Methods

### Parsing Class Members

```python
def parse_member(self, member_die: DIE) -> MemberInfo | None:
    """Parse class member with type resolution."""
    # Get member type
    type_name = self.resolve_type_name(member_die)

    # Get member name (handle anonymous members)
    name_attr = member_die.attributes.get("DW_AT_name")
    if name_attr:
        member_name = name_attr.value.decode("utf-8")
    elif "union" in type_name.lower() or "struct" in type_name.lower():
        member_name = ""  # Anonymous union/struct
    else:
        return None  # Skip unnamed non-aggregate members

    # Get member offset
    offset = None
    offset_attr = member_die.attributes.get("DW_AT_data_member_location")
    if offset_attr:
        offset = offset_attr.value

    # Check static/const flags
    is_static = (
        member_die.attributes.get("DW_AT_external") is not None
        and member_die.attributes.get("DW_AT_declaration") is not None
    )

    const_value = None
    const_attr = member_die.attributes.get("DW_AT_const_value")
    if const_attr:
        const_value = const_attr.value

    return MemberInfo(
        name=member_name,
        type_name=type_name,
        offset=offset,
        is_static=is_static,
        is_const=const_value is not None,
        const_value=const_value,
    )
```

### Parsing Methods with Parameters

```python
def parse_method(self, method_die: DIE) -> MethodInfo | None:
    """Parse class method including parameters."""
    # Get method name
    name_attr = method_die.attributes.get("DW_AT_name")
    if not name_attr:
        return None
    method_name = name_attr.value.decode("utf-8")

    # Get return type
    return_type = self.resolve_type_name(method_die)

    # Check virtual/constructor/destructor flags
    is_virtual = method_die.attributes.get("DW_AT_virtuality") is not None

    # Determine constructor/destructor
    parent_die = method_die.get_parent()
    parent_name = ""
    if parent_die:
        parent_name_attr = parent_die.attributes.get("DW_AT_name")
        if parent_name_attr:
            parent_name = parent_name_attr.value.decode("utf-8")

    is_constructor = method_name == parent_name
    is_destructor = method_name.startswith("~")

    # Parse parameters
    parameters = []
    for child in method_die.iter_children():
        if child.tag == "DW_TAG_formal_parameter":
            param = self.parse_parameter(child)
            if param:
                parameters.append(param)

    return MethodInfo(
        name=method_name,
        return_type=return_type,
        parameters=parameters,
        is_virtual=is_virtual,
        is_constructor=is_constructor,
        is_destructor=is_destructor,
    )
```

### Parsing Parameters (Filtering Artificial)

```python
def parse_parameter(self, param_die: DIE) -> ParameterInfo | None:
    """Parse function parameter, marking artificial params."""
    # Check if artificial (like 'this' pointer)
    is_artificial = param_die.attributes.get("DW_AT_artificial") is not None

    # Get parameter name
    name_attr = param_die.attributes.get("DW_AT_name")
    param_name = name_attr.value.decode("utf-8") if name_attr else "param"

    # Get parameter type
    param_type = self.resolve_type_name(param_die)

    # Mark artificial parameters for filtering
    if is_artificial:
        param_name = "__artificial__"

    return ParameterInfo(name=param_name, type_name=param_type)
```

---

## Handling Arrays and Complex Types

### Parsing Array Dimensions

```python
def parse_array_type(self, array_die: DIE) -> dict | None:
    """Parse array type with dimension calculation."""
    # Get element type
    element_type = self.resolve_type_name(array_die)

    # Calculate dimensions from subrange children
    dimensions = []
    total_elements = 1

    for child in array_die.iter_children():
        if child.tag == "DW_TAG_subrange_type":
            # Get array size
            count_attr = child.attributes.get("DW_AT_count")
            if count_attr:
                dimension_size = count_attr.value
            else:
                # Calculate from bounds
                upper_attr = child.attributes.get("DW_AT_upper_bound")
                lower_attr = child.attributes.get("DW_AT_lower_bound")
                if upper_attr:
                    upper = upper_attr.value
                    lower = lower_attr.value if lower_attr else 0
                    dimension_size = (upper - lower) + 1
                else:
                    dimension_size = 0  # Unknown size

            dimensions.append(dimension_size)
            if dimension_size > 0:
                total_elements *= dimension_size

    # Generate array type string
    if dimensions:
        dimension_str = "][".join(str(d) if d > 0 else "" for d in dimensions)
        array_name = f"{element_type}[{dimension_str}]"
    else:
        array_name = f"{element_type}[]"

    return {
        "name": array_name,
        "element_type": element_type,
        "dimensions": dimensions,
        "total_elements": total_elements,
    }
```

---

## Working with Enums

### Parsing Enum Definitions

```python
def parse_enum(self, enum_die: DIE) -> EnumInfo | None:
    """Parse enumeration with enumerators."""
    # Get enum name
    name_attr = enum_die.attributes.get("DW_AT_name")
    enum_name = name_attr.value.decode("utf-8") if name_attr else "unknown_enum"

    # Get enum size
    size_attr = enum_die.attributes.get("DW_AT_byte_size")
    byte_size = size_attr.value if size_attr else 4

    # Parse enumerators
    enumerators = []
    for child in enum_die.iter_children():
        if child.tag == "DW_TAG_enumerator":
            enumerator = self.parse_enumerator(child)
            if enumerator:
                enumerators.append(enumerator)

    return EnumInfo(
        name=enum_name,
        byte_size=byte_size,
        enumerators=enumerators,
    )

def parse_enumerator(self, enumerator_die: DIE) -> EnumeratorInfo | None:
    """Parse single enum value."""
    # Get enumerator name
    name_attr = enumerator_die.attributes.get("DW_AT_name")
    if not name_attr:
        return None
    name = name_attr.value.decode("utf-8")

    # Get enumerator value
    value_attr = enumerator_die.attributes.get("DW_AT_const_value")
    if not value_attr:
        return None

    # Handle different value formats
    value = value_attr.value
    if isinstance(value, bytes):
        value = int.from_bytes(value, byteorder="little", signed=True)
    elif not isinstance(value, int):
        value = int(value)

    return EnumeratorInfo(name=name, value=value)
```

---

## Anonymous Types (Unions, Structs)

### Detecting Anonymous Union Members

```python
def parse_class_info(self, cu: CompileUnit, class_die: DIE) -> ClassInfo:
    """Parse class with anonymous union detection."""
    unions = []
    processed_offsets = set()

    for child in class_die.iter_children():
        if child.tag == "DW_TAG_member":
            # Check for anonymous union
            name_attr = child.attributes.get("DW_AT_name")
            type_attr = child.attributes.get("DW_AT_type")

            if not name_attr and type_attr:
                # Might be anonymous union/struct
                try:
                    type_die = child.get_DIE_from_attribute("DW_AT_type")
                    if type_die and type_die.tag == "DW_TAG_union_type":
                        union_info = self.parse_union(type_die)
                        if union_info:
                            unions.append(union_info)
                            processed_offsets.add(type_die.offset)
                            continue
                except Exception as e:
                    logger.debug(f"Failed to resolve anonymous member: {e}")

            # Regular member
            member = self.parse_member(child)
            if member:
                members.append(member)
```

### Parsing Union with Nested Structs

```python
def parse_union(self, union_die: DIE) -> UnionInfo | None:
    """Parse union including nested anonymous structs."""
    # Get union name (might be None)
    name_attr = union_die.attributes.get("DW_AT_name")
    union_name = name_attr.value.decode("utf-8") if name_attr else ""

    # Get union size
    size_attr = union_die.attributes.get("DW_AT_byte_size")
    union_size = size_attr.value if size_attr else 0

    members = []
    nested_structs = []

    for child in union_die.iter_children():
        if child.tag == "DW_TAG_member":
            member = self.parse_member(child)
            if member:
                members.append(member)

        elif child.tag == "DW_TAG_structure_type":
            # Anonymous struct within union
            struct_info = self.parse_nested_structure(child)
            if struct_info:
                nested_structs.append(StructInfo(
                    name=struct_info["name"] or "",
                    byte_size=struct_info["size"],
                    members=struct_info["members"],
                ))

    return UnionInfo(
        name=union_name,
        byte_size=union_size,
        members=members,
        nested_structs=nested_structs,
    )
```

---

## Progress Tracking

### Logging CU Iteration

```python
def find_class_with_progress(self, class_name: str) -> tuple[CompileUnit, DIE] | None:
    """Find class with detailed progress logging."""
    target_name = class_name.encode("utf-8")
    cu_count = 0
    die_count = 0

    logger.info(f"Searching for class: {class_name}")

    for cu in self.dwarf_info.iter_CUs():
        cu_count += 1
        logger.debug(f"Searching CU #{cu_count} at offset 0x{cu.cu_offset:x}")

        for die in cu.iter_DIEs():
            die_count += 1

            if die.tag == "DW_TAG_class_type":
                name_attr = die.attributes.get("DW_AT_name")
                if name_attr and name_attr.value == target_name:
                    logger.info(
                        f"Found {class_name} in CU #{cu_count} "
                        f"after checking {die_count} DIEs"
                    )
                    return cu, die

    logger.warning(
        f"Class {class_name} not found after searching "
        f"{cu_count} CUs and {die_count} DIEs"
    )
    return None
```

### Performance Timing

```python
import time
from functools import wraps

def log_timing(func):
    """Decorator for timing function execution."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        logger.debug(f"Starting {func.__name__}")

        result = func(*args, **kwargs)

        elapsed = time.time() - start_time
        logger.info(f"{func.__name__} completed in {elapsed:.3f}s")

        return result
    return wrapper

# Usage
@log_timing
def generate_header(self, class_name: str) -> str:
    """Generate header with timing."""
    # ... implementation
```

---

## Complete Example: Class Parsing Pipeline

```python
from pathlib import Path
from elftools.elf.elffile import ELFFile
from elftools.dwarf.die import DIE

class CompleteDwarfParser:
    """Complete example of DWARF parsing pipeline."""

    def __init__(self, elf_path: Path):
        self.elf_path = elf_path
        self._typedef_cache = {}

    def __enter__(self):
        self.file_handle = open(self.elf_path, "rb")
        self.elf_file = ELFFile(self.file_handle)
        self.dwarf_info = self.elf_file.get_dwarf_info()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file_handle.close()

    def parse_complete_class(self, class_name: str) -> ClassInfo | None:
        """Parse complete class information."""
        # Step 1: Find class DIE
        result = self.find_class(class_name)
        if not result:
            return None

        cu, class_die = result

        # Step 2: Parse basic class info
        class_info = self.parse_class_info(cu, class_die)

        # Step 3: Build inheritance hierarchy
        class_info.hierarchy = self.build_inheritance_hierarchy(class_name)

        # Step 4: Collect used typedefs
        class_info.typedefs = self.collect_used_typedefs(class_info)

        return class_info

# Usage
with CompleteDwarfParser(Path("game.elf")) as parser:
    class_info = parser.parse_complete_class("MtObject")
    if class_info:
        print(f"Class: {class_info.name}")
        print(f"Size: {class_info.byte_size} bytes")
        print(f"Members: {len(class_info.members)}")
        print(f"Methods: {len(class_info.methods)}")
```

---

## References

- [pyelftools-api-reference.md](pyelftools-api-reference.md) - Complete API documentation
- [dwarf-parsing-patterns.md](dwarf-parsing-patterns.md) - Advanced DWARF patterns
- [pyelftools GitHub](https://github.com/eliben/pyelftools)
