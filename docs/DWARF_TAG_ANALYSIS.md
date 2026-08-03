# DWARF Tag Analysis and Type Resolution Strategy

**Date:** October 11, 2025  
**Status:** ✅ IMPLEMENTED - Offset-based architecture complete  
**Purpose:** Deep analysis of DWARF tags and pyelftools API - Implementation validated with 289/289 symbols

The current producer evidence is narrower than the historical label: the external PS4
02020005 ELF is uniformly DWARF4 (2,305 CUs, one PS4 Clang producer), while the comparison PS3
asset is uniformly DWARF2. The parser maintains a DWARF2-4 vocabulary contract; "supported"
means the exercised producer subset and evidence relationships are handled, not that every
standard tag/form is reconstructed into C++.

Use the generated [semantic index](knowledge-base/dwarf-specification/generated/semantic-index.md)
when reviewing a relationship. In particular, `DW_AT_containing_type` is a reference applicable
to `DW_TAG_ptr_to_member_type`; it is not evidence that a `DW_TAG_class_type` is the selected
class definition. `DW_AT_specification` and `DW_AT_abstract_origin` are distinct reference
relationships and must not be substituted for one another.

**Implementation Status:**
- ✅ Tag constants defined (tag_constants.py)
- ✅ DIETypeClassifier with tag validation (die_type_classifier.py)
- ✅ TypeChainTraverser for offset extraction (type_chain_traverser.py)
- ✅ Offset-based data models (type_offset fields added)
- ✅ DependencyExtractor using pure offset logic (dependency_extractor.py)
- ✅ Full integration testing: 289/289 symbols (100% success rate)

---

## 1. DWARF Tag Inventory

### 1.1 All Tags in Project DWARF Data

From `resources/dw-tags.txt`, the project's ELF file contains these tags:

#### **Type Definition Tags** (Define actual types)
- `DW_TAG_class_type` - C++ class definitions
- `DW_TAG_structure_type` - C struct definitions  
- `DW_TAG_union_type` - Union definitions
- `DW_TAG_enumeration_type` - Enum definitions
- `DW_TAG_base_type` - Primitive types (int, char, float, etc.)
- `DW_TAG_array_type` - Array type definitions
- `DW_TAG_subroutine_type` - Function pointer types

#### **Type Qualifier Tags** (Modify existing types)
- `DW_TAG_pointer_type` - Pointer to another type
- `DW_TAG_reference_type` - Lvalue reference (&)
- `DW_TAG_rvalue_reference_type` - Rvalue reference (&&)
- `DW_TAG_const_type` - Const qualifier
- `DW_TAG_volatile_type` - Volatile qualifier
- `DW_TAG_restrict_type` - Restrict qualifier
- `DW_TAG_typedef` - Type alias

#### **Member/Component Tags** (Parts of types)
- `DW_TAG_member` - Class/struct member variable
- `DW_TAG_enumerator` - Enum value
- `DW_TAG_subrange_type` - Array dimension
- `DW_TAG_formal_parameter` - Function/method parameter
- `DW_TAG_inheritance` - Base class inheritance

#### **Code Tags** (Functions/methods)
- `DW_TAG_subprogram` - Function or method definition
- `DW_TAG_inlined_subroutine` - Inlined function instance
- `DW_TAG_variable` - Variable definition

#### **Scope Tags** (Organization)
- `DW_TAG_compile_unit` - Compilation unit (root)
- `DW_TAG_namespace` - C++ namespace
- `DW_TAG_lexical_block` - Code block scope

#### **Template Tags** (C++ templates)
- `DW_TAG_template_type_parameter` - Template type parameter
- `DW_TAG_template_value_parameter` - Template value parameter
- `DW_TAG_GNU_template_parameter_pack` - Template parameter pack

#### **Other Tags**
- `DW_TAG_ptr_to_member_type` - Pointer-to-member type
- `DW_TAG_unspecified_parameters` - Variadic function marker
- `DW_TAG_unspecified_type` - Unknown/incomplete type
- `DW_TAG_imported_declaration` - Using declaration
- `DW_TAG_imported_module` - Using namespace

---

## 2. Tag Behavioral Categories

### 2.1 Type Resolution Categories

#### **Category A: Named Terminal Types** (Have DW_AT_name, end traversal)

These are the types we want to find and resolve:

```python
NAMED_TERMINAL_TYPES = {
    "DW_TAG_class_type",       # C++ classes
    "DW_TAG_structure_type",   # C structs
    "DW_TAG_union_type",       # Unions
    "DW_TAG_enumeration_type", # Enums
    "DW_TAG_base_type",        # Primitives (int, char, etc.)
    "DW_TAG_namespace",        # Namespaces
}
```

**Characteristics:**
- Have `DW_AT_name` attribute
- Represent actual type definitions
- Should be stored as dependencies
- May need forward declarations

**Example from rGUI.dwarfdump:**
```
0x000eb46a:   DW_TAG_class_type
                DW_AT_name	("rGUI::MyDTI")
                DW_AT_byte_size	(0x38)
```

#### **Category B: Type Qualifiers** (Transparent wrappers, traverse through)

These modify other types but don't have names themselves:

```python
TYPE_QUALIFIER_TAGS = {
    "DW_TAG_pointer_type",
    "DW_TAG_reference_type",
    "DW_TAG_rvalue_reference_type",
    "DW_TAG_const_type",
    "DW_TAG_volatile_type",
    "DW_TAG_restrict_type",
}
```

**Characteristics:**
- No `DW_AT_name` attribute
- Have `DW_AT_type` attribute pointing to wrapped type
- Must traverse to find base type
- Do NOT store as dependencies (transparent)

**Example from sample-dump-cSetInfoOmBreakTarget.dwarfdump:**
```
0x00065b7d:  DW_TAG_pointer_type
               DW_AT_type  (0x00065b82)  # Points to next type
               
0x00065b82:  DW_TAG_const_type
               DW_AT_type  (0x00065923)  # Points to MyDTI class
               
0x00065923:  DW_TAG_class_type
               DW_AT_name  ("MyDTI")  # TERMINAL - this is what we want
```

**Type chain**: `MyDTI* const` → pointer → const → MyDTI class

#### **Category C: Typedef (Special Case)**

Typedefs are aliases that may need to be preserved:

```python
TYPEDEF_TAG = "DW_TAG_typedef"
```

**Characteristics:**
- Has `DW_AT_name` attribute (the alias name)
- Has `DW_AT_type` attribute (the target type)
- May need to be collected for header generation
- Should traverse to find ultimate base type

**Example:**
```
0x12345:  DW_TAG_typedef
            DW_AT_name  ("size_t")
            DW_AT_type  (0x23456)  # Points to unsigned long

0x23456:  DW_TAG_base_type
            DW_AT_name  ("unsigned long")
```

#### **Category D: Anonymous/Inline Types** (No name, inline only)

These are embedded in parent structures:

```python
ANONYMOUS_TYPES = {
    "DW_TAG_array_type",        # Arrays (member[10])
    "DW_TAG_subroutine_type",   # Function pointers
    "DW_TAG_ptr_to_member_type",# Member pointers (int Class::*)
}
```

**Characteristics:**
- No `DW_AT_name` attribute
- Cannot be forward declared
- Must be fully defined inline
- Traverse for element/return types

---

## 3. pyelftools DIE API Analysis

### 3.1 DIE Class Structure

**Source**: `elftools/dwarf/die.py` in pyelftools package

**Public Methods:**
```python
class DIE:
    # Attributes
    tag: str                    # e.g., "DW_TAG_class_type"
    offset: int                 # Absolute offset in .debug_info
    attributes: OrderedDict     # DIE attributes
    size: int                   # Size of this DIE
    cu: CompileUnit             # Parent CU
    
    # Methods
    def get_DIE_from_attribute(attr_name: str) -> DIE | None
    def get_full_path() -> str | None
    def get_parent() -> DIE | None
    def is_null() -> bool
    def iter_children() -> Iterator[DIE]
    def iter_siblings() -> Iterator[DIE]
    def set_parent(die: DIE) -> None
```

### 3.2 Critical Method: `get_DIE_from_attribute()`

**Purpose**: Resolve DWARF reference attributes to actual DIE objects

**Implementation** (from pyelftools source):
```python
def get_DIE_from_attribute(self, attr_name):
    """Get a DIE referenced by the given attribute (DW_AT_type, etc.)"""
    attr = self.attributes.get(attr_name)
    if attr is None:
        return None
    
    # attr.value is the offset of the referenced DIE
    # pyelftools handles CU-relative vs absolute offsets
    return self.cu.get_DIE_from_offset(attr.value)
```

**Key Points:**
- Takes attribute name (e.g., "DW_AT_type")
- Returns DIE object directly (not offset, not string)
- Handles offset resolution internally
- Works across compilation units
- Returns None if attribute missing or reference invalid

**Usage Pattern:**
```python
# Given a member DIE
member_die = ...  # DW_TAG_member

# Resolve its type
type_die = member_die.get_DIE_from_attribute("DW_AT_type")

if type_die:
    # type_die is a DIE object, can check tag
    if type_die.tag == "DW_TAG_pointer_type":
        # Follow the pointer chain
        pointed_die = type_die.get_DIE_from_attribute("DW_AT_type")
        # ... continue traversal
```

### 3.3 DIE Attribute Access

**Accessing Attributes:**
```python
# Get attribute (returns AttributeValue or None)
name_attr = die.attributes.get("DW_AT_name")

if name_attr:
    # For string attributes, value is bytes
    if isinstance(name_attr.value, bytes):
        name = name_attr.value.decode("utf-8")
    else:
        name = str(name_attr.value)

# For integer attributes
size_attr = die.attributes.get("DW_AT_byte_size")
if size_attr:
    size = size_attr.value  # int

# For reference attributes - DON'T use .value directly
# USE get_DIE_from_attribute() instead
type_die = die.get_DIE_from_attribute("DW_AT_type")  # ✅ Correct
# type_offset = die.attributes["DW_AT_type"].value   # ❌ Wrong approach
```

---

## 4. Type Chain Traversal Algorithm

### 4.1 Implementation Status

**✅ IMPLEMENTED in TypeChainTraverser (type_chain_traverser.py)**

The traversal algorithm described below has been fully implemented and validated with 289 symbols.

**Current Implementation:**
```python
class TypeChainTraverser:
    @staticmethod
    def get_terminal_type_offset(die: DIE, dwarf_info) -> int | None:
        """Extract terminal type offset from DIE chain."""
        terminal_die = TypeChainTraverser.follow_to_terminal_type(die, dwarf_info)
        return terminal_die.offset if terminal_die else None
    
    @staticmethod
    def follow_to_terminal_type(die: DIE, dwarf_info, max_depth: int = 20) -> DIE | None:
        """Follow DW_AT_type chain to named terminal type."""
        # Handles: pointers, const, volatile, typedef chains
        # Returns: Terminal DIE (class, struct, base_type, enum, etc.)
        # Cycle detection: max_depth + visited set
```

**Key Features:**
- Cycle detection (max depth 20)
- Handles all type qualifier tags
- Returns terminal DIE offset for storage
- Used in parse_member(), parse_method(), parse_parameter()

### 4.2 The Problem (SOLVED)

**Current approach (WRONG):**
```python
# In parse_member():
type_name = self.type_resolver.resolve_type_name(member_die)
# Returns: "const MtObject*" as string
# Stores: MemberInfo(type_name="const MtObject*")
# Lost:   DIE offset, tag information, traversal path

# Later in dependency resolution:
# Must parse "const MtObject*" string to extract "MtObject"
# Must search entire DWARF to find "MtObject" class
```

**Example from DWARF dump:**
```
Member DIE (0x12345):
  DW_AT_name: "obj"
  DW_AT_type: 0x23456  ← Points to pointer

Pointer DIE (0x23456):
  DW_TAG_pointer_type
  DW_AT_type: 0x34567  ← Points to const

Const DIE (0x34567):
  DW_TAG_const_type
  DW_AT_type: 0x45678  ← Points to class

Class DIE (0x45678):
  DW_TAG_class_type
  DW_AT_name: "MtObject"  ← TERMINAL TYPE
```

Current code discards offsets 0x23456, 0x34567, 0x45678 and only keeps string "const MtObject*"

### 4.2 Correct Traversal Algorithm

```python
def follow_type_chain_to_terminal(self, start_die: DIE) -> tuple[DIE, list[str]]:
    """
    Follow type references to terminal type, collecting qualifiers.
    
    Args:
        start_die: Starting DIE (usually from DW_AT_type attribute)
        
    Returns:
        (terminal_die, qualifiers) where:
        - terminal_die: Final DIE with DW_AT_name (class, base type, etc.)
        - qualifiers: List of qualifiers encountered (["pointer", "const"])
    """
    current = start_die
    qualifiers = []
    visited = set()  # Prevent infinite loops
    
    while current and current.offset not in visited:
        visited.add(current.offset)
        
        # Check if we've reached a named terminal type
        if current.tag in NAMED_TERMINAL_TYPES:
            # Found terminal - class, struct, base type, etc.
            return current, qualifiers
        
        # Handle type qualifiers (traverse through)
        if current.tag in TYPE_QUALIFIER_TAGS:
            # Record qualifier
            if current.tag == "DW_TAG_pointer_type":
                qualifiers.append("pointer")
            elif current.tag == "DW_TAG_reference_type":
                qualifiers.append("reference")
            elif current.tag == "DW_TAG_rvalue_reference_type":
                qualifiers.append("rvalue_reference")
            elif current.tag == "DW_TAG_const_type":
                qualifiers.append("const")
            elif current.tag == "DW_TAG_volatile_type":
                qualifiers.append("volatile")
            elif current.tag == "DW_TAG_restrict_type":
                qualifiers.append("restrict")
            
            # Continue traversal
            next_die = current.get_DIE_from_attribute("DW_AT_type")
            if next_die:
                current = next_die
                continue
            else:
                # Qualifier with no target (void*, etc.)
                return None, qualifiers
        
        # Handle typedef (traverse but record name)
        elif current.tag == "DW_TAG_typedef":
            # Could record typedef name if needed
            typedef_name = current.attributes.get("DW_AT_name")
            # ... store typedef_name if collecting typedefs
            
            # Continue to underlying type
            next_die = current.get_DIE_from_attribute("DW_AT_type")
            if next_die:
                current = next_die
                continue
            else:
                # Typedef with no target (incomplete typedef)
                return None, qualifiers
        
        # Handle array type (special case)
        elif current.tag == "DW_TAG_array_type":
            # Arrays need special handling for dimensions
            # For now, just get element type
            element_die = current.get_DIE_from_attribute("DW_AT_type")
            if element_die:
                qualifiers.append("array")
                current = element_die
                continue
            else:
                return None, qualifiers
        
        # Unknown/unhandled tag
        else:
            logger.warning(f"Unhandled type tag in chain: {current.tag}")
            return None, qualifiers
    
    # Circular reference or incomplete chain
    return None, qualifiers
```

### 4.3 Usage in parse_member() - IMPLEMENTED

**✅ Current Implementation in class_parser.py:**

```python
def parse_member(self, member_die: DIE) -> MemberInfo | None:
    # Get type name for display
    type_name = self.type_resolver.resolve_type_name(member_die)
    
    # NEW: Capture terminal type offset using TypeChainTraverser
    type_offset = None
    if "DW_AT_type" in member_die.attributes:
        type_offset = TypeChainTraverser.get_terminal_type_offset(
            member_die, self.dwarf_info
        )
    
    return MemberInfo(
        name=member_name,
        type_name=type_name,        # Display string: "const MtObject*"
        type_offset=type_offset,    # Terminal DIE offset: 0x45678
        offset=offset,
        bit_size=bit_size,
        bit_offset=bit_offset,
    )
```

**Validation:** 289/289 symbols processed successfully with type_offset capture.

---

## 5. Type Classification for Dependencies - IMPLEMENTED

### 5.1 Which Types Need Forward Declarations? - IMPLEMENTED in DIETypeClassifier

**✅ Implemented in domain/services/parsing/die_type_classifier.py:**

```python
class DIETypeClassifier:
    @staticmethod
    def is_forward_declarable(die: DIE) -> bool:
        """Check if DIE can be forward declared (class/struct/union only)."""
        return die.tag in FORWARD_DECLARABLE_TYPES
    
    @staticmethod
    def requires_resolution(die: DIE) -> bool:
        """Check if type needs dependency resolution."""
        return die.tag in {
            "DW_TAG_class_type",
            "DW_TAG_structure_type", 
            "DW_TAG_union_type",
            "DW_TAG_enumeration_type",
        }
```

**From tag_constants.py:**
```python
FORWARD_DECLARABLE_TYPES = frozenset({
    "DW_TAG_class_type",
    "DW_TAG_structure_type",
    "DW_TAG_union_type",
})
```

**Validation:** Used throughout hierarchy_builder.py and header_generator.py for offset-based type validation.

### 5.2 Dependency Extraction Algorithm - IMPLEMENTED

**✅ Implemented in domain/services/generation/dependency_extractor.py (307 lines):**

```python
class DependencyExtractor:
    def extract_dependencies(self, class_info: ClassInfo) -> set[int]:
        """Extract DIE offsets of types requiring resolution."""
        dependencies = set()
        
        # Extract from members
        for member in class_info.members:
            if member.type_offset:
                dependencies.add(member.type_offset)
        
        # Extract from methods
        for method in class_info.methods:
            if method.return_type_offset:
                dependencies.add(method.return_type_offset)
            for param in method.parameters or []:
                if param.type_offset:
                    dependencies.add(param.type_offset)
        
        return dependencies
    
    def filter_resolvable_types(self, offsets: set[int]) -> set[int]:
        """Filter to types requiring dependency resolution."""
        resolvable = set()
        
        for offset in offsets:
            die = self.dwarf_index.get_die_by_offset(offset)
            if die and DIETypeClassifier.requires_resolution(die):
                if "DW_AT_name" in die.attributes:
                    resolvable.add(offset)
        
        return resolvable
```

**Key Features:**
- Pure offset-based logic (no string parsing)
- Uses DIETypeClassifier for tag validation
- O(1) DIE lookups via LazyDwarfIndexService
- Filters internal DWARF types automatically

**Validation:** Successfully used in 289-symbol integration test with zero parsing bugs.

---

## 6. Key Insights for Refactoring

### 6.1 Critical Distinctions

**1. Terminal vs Transparent Types**
- Terminal types have names, can be forward declared
- Transparent types (pointers, const) must be traversed

**2. Offset vs Name**
- Store offset of terminal type, not intermediate qualifiers
- Name is for display, offset is for resolution

**3. Tag Checking is Essential**
- Must check `die.tag` to determine type category
- Cannot assume any DIE with DW_AT_name is a class

**4. pyelftools Does the Work**
- `get_DIE_from_attribute()` handles all offset resolution
- Never manually resolve offsets from attribute values

### 6.2 Common Pitfalls to Avoid

**❌ WRONG: Treating all named types as classes**
```python
# Bad - assumes any name is a class
name_attr = die.attributes.get("DW_AT_name")
if name_attr:
    forward_declarations.add(name_attr.value.decode("utf-8"))
```

**✅ CORRECT: Check tag first**
```python
# Good - verifies it's actually a class/struct
name_attr = die.attributes.get("DW_AT_name")
if name_attr and die.tag in FORWARD_DECLARABLE_TYPES:
    forward_declarations.add(name_attr.value.decode("utf-8"))
```

**❌ WRONG: Storing intermediate DIE offsets**
```python
# Bad - stores pointer DIE offset
type_die = member_die.get_DIE_from_attribute("DW_AT_type")
type_offset = type_die.offset  # Offset of pointer, not class!
```

**✅ CORRECT: Store terminal type offset**
```python
# Good - follows chain to class
type_die = member_die.get_DIE_from_attribute("DW_AT_type")
terminal_die, _ = follow_type_chain_to_terminal(type_die)
type_offset = terminal_die.offset  # Offset of actual class
```

---

## 7. Tag Handling Requirements

### 7.1 Required Tag Constants

```python
# In domain/models/dwarf/tag_constants.py (new file)

# Terminal types that have names and can be dependencies
NAMED_TERMINAL_TYPES = {
    "DW_TAG_class_type",
    "DW_TAG_structure_type",
    "DW_TAG_union_type",
    "DW_TAG_enumeration_type",
    "DW_TAG_base_type",
    "DW_TAG_namespace",
}

# Types that can be forward declared
FORWARD_DECLARABLE_TYPES = {
    "DW_TAG_class_type",
    "DW_TAG_structure_type",
    "DW_TAG_union_type",
}

# Type qualifiers that must be traversed
TYPE_QUALIFIER_TAGS = {
    "DW_TAG_pointer_type",
    "DW_TAG_reference_type",
    "DW_TAG_rvalue_reference_type",
    "DW_TAG_const_type",
    "DW_TAG_volatile_type",
    "DW_TAG_restrict_type",
}

# Primitive types (built-in)
PRIMITIVE_BASE_TYPES = {
    "void", "bool", "char", "signed char", "unsigned char",
    "short", "unsigned short", "int", "unsigned int",
    "long", "unsigned long", "long long", "unsigned long long",
    "float", "double", "long double",
    "wchar_t", "char16_t", "char32_t",
}
```

### 7.2 Tag Validation Functions

```python
def is_named_type(die: DIE) -> bool:
    """Check if DIE represents a named type."""
    return (
        die.tag in NAMED_TERMINAL_TYPES
        and "DW_AT_name" in die.attributes
    )

def is_forward_declarable(die: DIE) -> bool:
    """Check if DIE represents a type that can be forward declared."""
    return (
        die.tag in FORWARD_DECLARABLE_TYPES
        and "DW_AT_name" in die.attributes
    )

def is_primitive_type(die: DIE) -> bool:
    """Check if DIE represents a primitive base type."""
    if die.tag != "DW_TAG_base_type":
        return False
    
    name_attr = die.attributes.get("DW_AT_name")
    if not name_attr:
        return False
    
    name = name_attr.value.decode("utf-8") if isinstance(name_attr.value, bytes) else str(name_attr.value)
    return name in PRIMITIVE_BASE_TYPES
```

---

## 8. Revised Algorithm Summary

### Complete Type Resolution Flow

```
1. User Input: `generate --symbol rGUI`
   └─> Exhaustive DWARF search for class named "rGUI" ✅ CORRECT

2. Parse rGUI class:
   For each member:
     ├─> Get DW_AT_type reference (offset to type DIE)
     ├─> Call get_DIE_from_attribute("DW_AT_type") → type_die
     ├─> Follow type chain:
     │   ├─> Check type_die.tag
     │   ├─> If TYPE_QUALIFIER_TAGS: get next DW_AT_type, repeat
     │   ├─> If NAMED_TERMINAL_TYPES: terminal found!
     │   └─> Store terminal DIE offset
     └─> Create MemberInfo with:
         ├─> type_name: "const MtObject*" (display)
         └─> type_offset: 0x45678 (MtObject class DIE)

3. Extract Dependencies:
   For each member.type_offset:
     ├─> Lookup DIE by offset (O(1) cache)
     ├─> Check die.tag in FORWARD_DECLARABLE_TYPES
     ├─> Check die has DW_AT_name
     └─> Add to dependencies if yes

4. Process Dependencies:
   For each dependency offset:
     ├─> Lookup DIE by offset (O(1))
     ├─> Get DW_AT_name
     ├─> Call parse_class_info(die)
     └─> Add to header

5. Generate Forward Declarations:
   For each type_offset:
     ├─> Check if already in header
     ├─> Check if forward declarable
     └─> Emit forward declaration if needed
```

**Key Points:**
- No string parsing except for final display names
- All type resolution uses DIE traversal
- Offsets stored at parsing time, never searched again
- Tag checking at every step ensures correctness

---

## 9. Example: Complete Member Parsing

### Input DWARF Structure
```
0x10000: DW_TAG_class_type "rGUI"
  0x10010: DW_TAG_member "obj"
    DW_AT_type: 0x20000  ← Start here

0x20000: DW_TAG_pointer_type
  DW_AT_type: 0x30000

0x30000: DW_TAG_const_type
  DW_AT_type: 0x40000

0x40000: DW_TAG_class_type "MtObject"
  DW_AT_name: "MtObject"
  DW_AT_byte_size: 8
```

### Parsing Steps

```python
# Step 1: Get member type reference
member_die = # DIE at 0x10010
type_die = member_die.get_DIE_from_attribute("DW_AT_type")
# type_die = DIE at 0x20000 (pointer)

# Step 2: Follow chain
current = type_die  # 0x20000, DW_TAG_pointer_type
qualifiers = []

# 2a: Pointer tag
current.tag == "DW_TAG_pointer_type"  # True
qualifiers.append("pointer")
current = current.get_DIE_from_attribute("DW_AT_type")
# current = DIE at 0x30000 (const)

# 2b: Const tag
current.tag == "DW_TAG_const_type"  # True
qualifiers.append("const")
current = current.get_DIE_from_attribute("DW_AT_type")
# current = DIE at 0x40000 (class)

# 2c: Terminal type
current.tag == "DW_TAG_class_type"  # True
current.tag in NAMED_TERMINAL_TYPES  # True
terminal_die = current
type_offset = terminal_die.offset  # 0x40000

# Step 3: Create MemberInfo
MemberInfo(
    name="obj",
    type_name="const MtObject*",  # From resolve_type_name() for display
    type_offset=0x40000,          # Terminal MtObject class DIE
)

# Step 4: Later dependency extraction
die = index.get_die_by_offset(0x40000)  # O(1) lookup
die.tag == "DW_TAG_class_type"          # True
die.tag in FORWARD_DECLARABLE_TYPES     # True
"DW_AT_name" in die.attributes          # True
# → Include in dependencies ✅
```

---

## Conclusion - IMPLEMENTATION COMPLETE ✅

**Status: All predictions and requirements successfully implemented**

### Implementation Summary

**Created Components:**

1. **tag_constants.py** - Frozensets for O(1) tag classification
   - NAMED_TERMINAL_TYPES (6 tags)
   - FORWARD_DECLARABLE_TYPES (3 tags)
   - TYPE_QUALIFIER_TAGS (6 tags)
   - PRIMITIVE_TYPE_NAMES (100+ types)

2. **die_type_classifier.py** - Static validation methods
   - `is_named_type()` - Check if DIE has name
   - `is_forward_declarable()` - Validate forward declaration eligibility
   - `is_type_qualifier()` - Identify transparent wrappers
   - `requires_resolution()` - Determine if needs dependency resolution

3. **type_chain_traverser.py** - Offset extraction algorithm
   - `follow_to_terminal_type()` - Traverse type chains
   - `get_terminal_type_offset()` - Extract terminal DIE offset
   - Cycle detection, max depth 20
   - Handles all qualifier tags

4. **dependency_extractor.py** (307 lines) - Pure offset-based extraction
   - `extract_dependencies()` - Get all type offsets from ClassInfo
   - `filter_resolvable_types()` - Validate with DIETypeClassifier
   - `get_type_name()` - Resolve offset to name
   - Zero string parsing

5. **Data Model Extensions**
   - `MemberInfo.type_offset: int | None`
   - `MethodInfo.return_type_offset: int | None`
   - `ParameterInfo.type_offset: int | None`

6. **Integration Points**
   - `class_parser.py` - Captures type_offset during parsing
   - `hierarchy_builder.py` - Uses DependencyExtractor (243 lines, 60% reduction)
   - `header_generator.py` - Offset-based forward declarations
   - `lazy_type_resolver.py` - Internal type filtering

### Validation Results

**Integration Test: 289/289 symbols (100% success rate)**

```bash
uv run ddon-dwarf-reconstructor generate resources/DDOORBIS.elf \
  --symbols-file resources/season2-resources.txt \
  --full-hierarchy
```

**Results:**
- ✅ Zero hangs (no infinite loops on internal types)
- ✅ Zero string parsing bugs (class_type, void, pointer_type eliminated)
- ✅ Clean forward declarations (only class/struct/union)
- ✅ Valid typedefs only (no void*, MtDTI*, etc.)
- ✅ 1519 symbols cached for performance

**Bugs Fixed:**
- Internal DWARF type searches (class_type, structure_type, void)
- Invalid typedef generation (typedef void void*)
- Array forward declarations (ANIMATION*[], ANIMATION_STATE[])
- Anonymous struct/union handling

### Key Takeaways (VALIDATED)

1. ✅ **Tag checking is mandatory** - Implemented in DIETypeClassifier
2. ✅ **Follow chains to terminals** - Implemented in TypeChainTraverser
3. ✅ **Use pyelftools API** - All code uses `get_DIE_from_attribute()`
4. ✅ **Separate display from resolution** - type_name vs type_offset fields
5. ✅ **Validate at every step** - DIETypeClassifier used throughout

### Performance Impact

**Code Reduction:**
- hierarchy_builder.py: 614→243 lines (60% reduction, 371 lines deleted)
- header_generator.py: 18 lines deleted (_extract_base_type removed)
- Total: 389 lines of string parsing eliminated

**Reliability:**
- The 289-case validation sample passed after the offset-based changes.
- This sample is not a proof of corpus-wide correctness; current edge cases and
  unresolved evidence are tracked in `specs/006-clean-architecture-audit/`.

**Architecture:**
- Before: String parsing, linear searches, bug-prone assumptions
- After: Offset-based validation, O(1) lookups, tag verification

The offset-based architecture reduces repeated string parsing and makes type
references auditable. Correctness remains tied to explicit evidence status,
source identity, and the focused regression suite.
