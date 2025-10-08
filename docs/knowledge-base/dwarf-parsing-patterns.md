# DWARF Parsing Patterns

Advanced patterns and strategies for parsing DWARF debug information to reconstruct C++ headers.

## Table of Contents

1. [DWARF Structure Overview](#dwarf-structure-overview)
2. [Class and Struct Parsing](#class-and-struct-parsing)
3. [Inheritance Relationships](#inheritance-relationships)
4. [Template Handling](#template-handling)
5. [Anonymous Types](#anonymous-types)
6. [Type Qualification Chains](#type-qualification-chains)
7. [Member Layout and Packing](#member-layout-and-packing)
8. [Virtual Methods and VTables](#virtual-methods-and-vtables)
9. [Optimization Strategies](#optimization-strategies)

---

## DWARF Structure Overview

### Compilation Unit Hierarchy

```
DW_TAG_compile_unit (Root of CU)
├── DW_TAG_class_type (MtObject)
│   ├── DW_TAG_inheritance (base class reference)
│   ├── DW_TAG_member (data member)
│   │   └── DW_AT_type -> DW_TAG_typedef (u32)
│   ├── DW_TAG_subprogram (method)
│   │   ├── DW_TAG_formal_parameter (parameter)
│   │   └── DW_AT_virtuality (virtual flag)
│   ├── DW_TAG_enumeration_type (nested enum)
│   │   └── DW_TAG_enumerator (enum value)
│   └── DW_TAG_union_type (nested union)
├── DW_TAG_typedef (u32 -> unsigned int)
└── DW_TAG_structure_type (another struct)
```

### Key Principles

1. **References, Not Copies**: DWARF uses offsets to reference types, avoiding duplication
2. **Lazy Resolution**: Follow references only when needed
3. **Hierarchy Matters**: Child DIEs inherit context from parents
4. **Declaration vs Definition**: A type may have multiple declarations but one definition

---

## Class and Struct Parsing

### Complete Class Definition Pattern

```python
def parse_class_info(self, cu: CompileUnit, class_die: DIE) -> ClassInfo:
    """Parse complete class with all nested types."""

    # 1. Extract basic attributes
    name = self._get_name(class_die)
    byte_size = self._get_byte_size(class_die)
    alignment = self._get_alignment(class_die)

    # 2. Parse children by tag type
    members = []
    methods = []
    base_classes = []
    enums = []
    nested_structs = []
    unions = []

    for child in class_die.iter_children():
        if child.tag == "DW_TAG_member":
            member = self.parse_member(child)
            if member:
                members.append(member)

        elif child.tag == "DW_TAG_subprogram":
            method = self.parse_method(child)
            if method:
                methods.append(method)

        elif child.tag == "DW_TAG_inheritance":
            base_type = self.resolve_type_name(child)
            if base_type != "unknown_type":
                base_classes.append(base_type)

        elif child.tag == "DW_TAG_enumeration_type":
            enum = self.parse_enum(child)
            if enum:
                enums.append(enum)

        elif child.tag == "DW_TAG_structure_type":
            struct = self.parse_nested_structure(child)
            if struct:
                nested_structs.append(struct)

        elif child.tag == "DW_TAG_union_type":
            union = self.parse_union(child)
            if union:
                unions.append(union)

    # 3. Build ClassInfo
    return ClassInfo(
        name=name,
        byte_size=byte_size,
        members=members,
        methods=methods,
        base_classes=base_classes,
        enums=enums,
        nested_structs=nested_structs,
        unions=unions,
        alignment=alignment,
    )
```

### Handling Forward Declarations

DWARF distinguishes between declarations and definitions:

```python
def find_complete_definition(self, class_name: str) -> tuple[CompileUnit, DIE] | None:
    """Find complete definition, preferring sized types over forward declarations."""
    target_name = class_name.encode("utf-8")
    forward_decl = None

    for cu in self.dwarf_info.iter_CUs():
        for die in cu.iter_DIEs():
            if die.tag == "DW_TAG_class_type":
                name_attr = die.attributes.get("DW_AT_name")
                if name_attr and name_attr.value == target_name:
                    # Check if this is a complete definition
                    size_attr = die.attributes.get("DW_AT_byte_size")
                    if size_attr and size_attr.value > 0:
                        return cu, die  # Complete definition

                    # Or has members (implicit definition)
                    if die.has_children:
                        return cu, die

                    # Save as fallback
                    if not forward_decl:
                        forward_decl = (cu, die)

    return forward_decl  # Return forward declaration if no definition found
```

---

## Inheritance Relationships

### Single Inheritance Chain

```python
def build_inheritance_chain(self, class_name: str) -> list[str]:
    """Build linear inheritance chain from base to derived."""
    hierarchy = []
    current_class = class_name
    visited = set()

    while current_class and current_class not in visited:
        visited.add(current_class)

        result = self.find_class(current_class)
        if not result:
            break

        cu, class_die = result

        # Find direct base class
        for child in class_die.iter_children():
            if child.tag == "DW_TAG_inheritance":
                base_type = self.resolve_type_name(child)
                if base_type != "unknown_type":
                    hierarchy.append(base_type)
                    current_class = base_type
                    break
        else:
            # No base class found
            break

    return list(reversed(hierarchy))  # Base to derived order
```

### Multiple Inheritance

```python
def find_all_base_classes(self, class_die: DIE) -> list[BaseClassInfo]:
    """Find all direct base classes (handles multiple inheritance)."""
    base_classes = []

    for child in class_die.iter_children():
        if child.tag == "DW_TAG_inheritance":
            # Get base class type
            base_type = self.resolve_type_name(child)

            # Get inheritance offset (for multiple inheritance)
            offset_attr = child.attributes.get("DW_AT_data_member_location")
            offset = offset_attr.value if offset_attr else 0

            # Get accessibility (public/private/protected)
            access_attr = child.attributes.get("DW_AT_accessibility")
            access = self._map_accessibility(access_attr)

            base_classes.append(BaseClassInfo(
                type_name=base_type,
                offset=offset,
                accessibility=access,
            ))

    return base_classes
```

---

## Template Handling

### Template Class Recognition

DWARF doesn't explicitly mark templates, but they have characteristic naming patterns:

```python
def is_template_class(self, class_name: str) -> bool:
    """Detect if a class is a template instantiation."""
    return "<" in class_name and ">" in class_name

def parse_template_parameters(self, class_name: str) -> list[str]:
    """Extract template parameters from mangled name."""
    # Example: "std::vector<int, std::allocator<int>>"
    if not self.is_template_class(class_name):
        return []

    start = class_name.find("<")
    end = class_name.rfind(">")
    if start == -1 or end == -1:
        return []

    params_str = class_name[start + 1:end]

    # Simple comma split (doesn't handle nested templates perfectly)
    params = [p.strip() for p in params_str.split(",")]

    return params
```

### Template Specialization

```python
def find_template_instantiations(self, template_base: str) -> list[tuple[str, DIE]]:
    """Find all instantiations of a template."""
    instantiations = []
    template_prefix = template_base.encode("utf-8")

    for cu in self.dwarf_info.iter_CUs():
        for die in cu.iter_DIEs():
            if die.tag == "DW_TAG_class_type":
                name_attr = die.attributes.get("DW_AT_name")
                if name_attr and name_attr.value.startswith(template_prefix):
                    full_name = name_attr.value.decode("utf-8")
                    if self.is_template_class(full_name):
                        instantiations.append((full_name, die))

    return instantiations
```

---

## Anonymous Types

### Anonymous Union Detection

Anonymous unions appear as members without names but with union types:

```python
def detect_anonymous_union(self, member_die: DIE) -> bool:
    """Check if a member represents an anonymous union."""
    # No name attribute
    name_attr = member_die.attributes.get("DW_AT_name")
    if name_attr:
        return False

    # Has type attribute
    type_attr = member_die.attributes.get("DW_AT_type")
    if not type_attr:
        return False

    # Type resolves to union
    try:
        type_die = member_die.get_DIE_from_attribute("DW_AT_type")
        return type_die and type_die.tag == "DW_TAG_union_type"
    except Exception:
        return False
```

### Anonymous Union Parsing

```python
def parse_class_with_anonymous_unions(self, class_die: DIE) -> ClassInfo:
    """Parse class handling anonymous unions correctly."""
    members = []
    unions = []
    processed_union_offsets = set()

    for child in class_die.iter_children():
        if child.tag == "DW_TAG_member":
            # Check for anonymous union
            if self.detect_anonymous_union(child):
                type_die = child.get_DIE_from_attribute("DW_AT_type")
                if type_die:
                    # Parse the union directly
                    union_info = self.parse_union(type_die)
                    if union_info:
                        unions.append(union_info)
                        processed_union_offsets.add(type_die.offset)
                    continue

            # Regular member
            member = self.parse_member(child)
            if member:
                members.append(member)

        elif child.tag == "DW_TAG_union_type":
            # Named union or already processed anonymous union
            if child.offset not in processed_union_offsets:
                union_info = self.parse_union(child)
                if union_info:
                    unions.append(union_info)

    return ClassInfo(members=members, unions=unions, ...)
```

### Anonymous Struct in Union

```python
def parse_union_with_anonymous_struct(self, union_die: DIE) -> UnionInfo:
    """Parse union containing anonymous structs."""
    members = []
    nested_structs = []

    for child in union_die.iter_children():
        if child.tag == "DW_TAG_member":
            member = self.parse_member(child)
            if member:
                members.append(member)

        elif child.tag == "DW_TAG_structure_type":
            # Nested struct (might be anonymous)
            struct_info = self.parse_nested_structure(child)
            if struct_info:
                struct_obj = StructInfo(
                    name=struct_info["name"] or "",  # Empty for anonymous
                    byte_size=struct_info["size"],
                    members=struct_info["members"],
                )
                nested_structs.append(struct_obj)

    return UnionInfo(
        name=union_die.attributes.get("DW_AT_name", "").value.decode("utf-8"),
        members=members,
        nested_structs=nested_structs,
        byte_size=union_die.attributes.get("DW_AT_byte_size", 0).value,
    )
```

---

## Type Qualification Chains

### Resolving Qualified Types

Types can be qualified with `const`, `volatile`, pointers, references, etc.

```python
def resolve_qualified_type(self, die: DIE) -> tuple[str, list[str]]:
    """Resolve type with qualifiers, returning (base_type, qualifiers)."""
    qualifiers = []
    current_die = die

    # Follow type chain
    while True:
        type_die = current_die.get_DIE_from_attribute("DW_AT_type")
        if not type_die:
            break

        # Collect qualifier
        if type_die.tag == "DW_TAG_pointer_type":
            qualifiers.append("*")
        elif type_die.tag == "DW_TAG_reference_type":
            qualifiers.append("&")
        elif type_die.tag == "DW_TAG_rvalue_reference_type":
            qualifiers.append("&&")
        elif type_die.tag == "DW_TAG_const_type":
            qualifiers.append("const")
        elif type_die.tag == "DW_TAG_volatile_type":
            qualifiers.append("volatile")
        elif type_die.tag == "DW_TAG_restrict_type":
            qualifiers.append("restrict")
        else:
            # Found base type
            name_attr = type_die.attributes.get("DW_AT_name")
            if name_attr:
                base_type = name_attr.value.decode("utf-8")
                return base_type, qualifiers
            break

        current_die = type_die

    return "unknown_type", qualifiers

def format_qualified_type(self, base_type: str, qualifiers: list[str]) -> str:
    """Format type with qualifiers in correct C++ order."""
    result = base_type

    # Apply qualifiers in reverse order (they were collected innermost-first)
    for qual in reversed(qualifiers):
        if qual in ("const", "volatile", "restrict"):
            result = f"{qual} {result}"
        else:
            result = f"{result}{qual}"

    return result
```

### Typedef Resolution

Typedefs create indirection in type resolution:

```python
def resolve_through_typedef(self, die: DIE) -> str:
    """Resolve type, following typedef chain."""
    current_die = die
    visited = set()

    while current_die:
        # Prevent infinite loops
        if current_die.offset in visited:
            return "unknown_type"
        visited.add(current_die.offset)

        # Get type
        type_die = current_die.get_DIE_from_attribute("DW_AT_type")
        if not type_die:
            return "void"

        # Check if it's a typedef
        if type_die.tag == "DW_TAG_typedef":
            # Continue following typedef chain
            current_die = type_die
            continue

        # Found underlying type
        name_attr = type_die.attributes.get("DW_AT_name")
        if name_attr:
            return name_attr.value.decode("utf-8")

        # Handle type modifiers
        return self.resolve_type_name(type_die)

    return "unknown_type"
```

---

## Member Layout and Packing

### Calculating Member Offsets

```python
def analyze_member_layout(self, class_info: ClassInfo) -> dict:
    """Analyze member layout to detect padding and alignment."""
    analysis = {
        "total_size": class_info.byte_size,
        "member_size": 0,
        "padding_bytes": 0,
        "gaps": [],
    }

    # Sort members by offset
    sorted_members = sorted(
        [m for m in class_info.members if m.offset is not None],
        key=lambda m: m.offset,
    )

    if not sorted_members:
        return analysis

    current_offset = 0

    for i, member in enumerate(sorted_members):
        member_offset = member.offset

        # Detect gap (padding)
        if member_offset > current_offset:
            gap_size = member_offset - current_offset
            analysis["gaps"].append({
                "after_member": sorted_members[i-1].name if i > 0 else "start",
                "offset": current_offset,
                "size": gap_size,
            })
            analysis["padding_bytes"] += gap_size

        # Estimate member size
        member_size = self._estimate_type_size(member.type_name)
        analysis["member_size"] += member_size
        current_offset = member_offset + member_size

    # Tail padding
    if current_offset < class_info.byte_size:
        tail_padding = class_info.byte_size - current_offset
        analysis["gaps"].append({
            "after_member": sorted_members[-1].name,
            "offset": current_offset,
            "size": tail_padding,
        })
        analysis["padding_bytes"] += tail_padding

    return analysis
```

### Detecting Packing Attributes

```python
def detect_packing(self, class_info: ClassInfo) -> int | None:
    """Detect #pragma pack or __attribute__((packed)) from layout."""
    layout = self.analyze_member_layout(class_info)

    # No padding = likely packed
    if layout["padding_bytes"] == 0:
        return 1  # #pragma pack(1)

    # Minimal padding = 4-byte alignment
    if layout["padding_bytes"] <= class_info.byte_size * 0.1:
        return 4

    # Default alignment = 8 bytes (x64)
    return 8
```

---

## Virtual Methods and VTables

### Detecting Virtual Methods

```python
def parse_virtual_method(self, method_die: DIE) -> MethodInfo:
    """Parse method with virtual information."""
    # Check virtuality attribute
    virtuality_attr = method_die.attributes.get("DW_AT_virtuality")
    is_virtual = virtuality_attr is not None

    # Get vtable index if available
    vtable_index = None
    if is_virtual:
        # DWARF may encode vtable index in DW_AT_vtable_elem_location
        vtable_attr = method_die.attributes.get("DW_AT_vtable_elem_location")
        if vtable_attr:
            # This is typically a location expression
            # Simplified: extract constant if present
            vtable_index = self._extract_vtable_index(vtable_attr)

    return MethodInfo(
        name=self._get_name(method_die),
        return_type=self.resolve_type_name(method_die),
        is_virtual=is_virtual,
        vtable_index=vtable_index,
    )
```

### VTable Pointer Detection

```python
def detect_vtable_pointer(self, class_info: ClassInfo) -> MemberInfo | None:
    """Detect _vptr$ member (virtual table pointer)."""
    for member in class_info.members:
        # VTable pointers have characteristic names
        if member.name.startswith("_vptr$") or member.name == "_vptr":
            # Usually at offset 0
            if member.offset == 0:
                return member

    return None
```

---

## Optimization Strategies

### 1. Targeted Search with Tag Filtering

Only iterate DIEs with relevant tags:

```python
def find_types_optimized(self, target_tags: set[str]) -> list[DIE]:
    """Find DIEs matching specific tags only."""
    results = []

    for cu in self.dwarf_info.iter_CUs():
        for die in cu.iter_DIEs():
            if die.tag in target_tags:
                results.append(die)

    return results

# Usage
class_dies = generator.find_types_optimized({
    "DW_TAG_class_type",
    "DW_TAG_structure_type",
})
```

### 2. Compilation Unit Filtering

Skip CUs based on name/path patterns:

```python
def should_process_cu(self, cu: CompileUnit) -> bool:
    """Filter CUs based on source file patterns."""
    root_die = cu.get_top_DIE()
    name_attr = root_die.attributes.get("DW_AT_name")

    if not name_attr:
        return False

    cu_name = name_attr.value.decode("utf-8")

    # Skip system headers
    if cu_name.startswith("/usr/include/"):
        return False

    # Skip standard library
    if "std::" in cu_name or "stl_" in cu_name:
        return False

    return True

# Usage
for cu in dwarf_info.iter_CUs():
    if not self.should_process_cu(cu):
        continue
    # Process CU
```

### 3. Two-Pass Resolution

Separate finding from parsing to avoid repeated searches:

```python
def build_type_index(self) -> dict[str, tuple[CompileUnit, DIE]]:
    """Build index of all types (first pass)."""
    type_index = {}

    for cu in self.dwarf_info.iter_CUs():
        for die in cu.iter_DIEs():
            if die.tag in ("DW_TAG_class_type", "DW_TAG_structure_type"):
                name_attr = die.attributes.get("DW_AT_name")
                if name_attr:
                    type_name = name_attr.value.decode("utf-8")
                    type_index[type_name] = (cu, die)

    return type_index

def parse_with_index(self, class_name: str, type_index: dict) -> ClassInfo:
    """Parse using pre-built index (second pass)."""
    if class_name not in type_index:
        return None

    cu, die = type_index[class_name]
    return self.parse_class_info(cu, die)
```

### 4. Lazy Typedef Resolution

Only resolve typedefs when actually needed:

```python
class LazyTypedefResolver:
    """Resolve typedefs on-demand with caching."""

    def __init__(self, dwarf_info):
        self.dwarf_info = dwarf_info
        self._cache = {}
        self._primitive_types = {"u8", "u16", "u32", "u64", "s8", "s16", "s32", "s64"}

    def resolve(self, typedef_name: str) -> str | None:
        """Resolve typedef lazily."""
        # Check cache
        if typedef_name in self._cache:
            return self._cache[typedef_name]

        # Skip non-primitives (performance optimization)
        if typedef_name not in self._primitive_types:
            return None

        # Search DWARF
        result = self._search_typedef(typedef_name)
        self._cache[typedef_name] = result
        return result
```

---

## Common Pitfalls and Solutions

### Pitfall 1: Infinite Loops in Type Resolution

**Problem**: Circular type references cause infinite recursion

**Solution**: Track visited DIEs

```python
def resolve_type_safe(self, die: DIE, visited: set[int] | None = None) -> str:
    """Resolve type with cycle detection."""
    if visited is None:
        visited = set()

    if die.offset in visited:
        return "recursive_type"

    visited.add(die.offset)

    # Normal resolution logic
    type_die = die.get_DIE_from_attribute("DW_AT_type")
    if type_die:
        return self.resolve_type_safe(type_die, visited)

    return "unknown_type"
```

### Pitfall 2: Missing Anonymous Union Members

**Problem**: Anonymous unions don't generate members in C++ output

**Solution**: Explicitly handle anonymous union members

```python
# Wrong: Anonymous union ignored
union MyUnion {
    int a;
    float b;
};  // <-- No member name!

# Correct: Generate anonymous union syntax
class MyClass {
    union {
        int a;
        float b;
    };  // <-- Anonymous union in C++
};
```

### Pitfall 3: Incorrect Typedef Resolution

**Problem**: Resolving all typedefs causes performance issues

**Solution**: Only resolve primitive typedefs

```python
# Only resolve these
PRIMITIVE_TYPEDEFS = {"u8", "u16", "u32", "u64", "s8", "s16", "s32", "s64"}

def should_resolve_typedef(self, name: str) -> bool:
    return name in PRIMITIVE_TYPEDEFS
```

---

## References

- [pyelftools-api-reference.md](pyelftools-api-reference.md) - PyElfTools API
- [pyelftools-examples.md](pyelftools-examples.md) - Code examples
- [DWARF 4 Standard](http://dwarfstd.org/doc/DWARF4.pdf)
- [DWARF 5 Standard](http://dwarfstd.org/doc/DWARF5.pdf)
