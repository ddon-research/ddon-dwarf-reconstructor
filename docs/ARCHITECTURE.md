# Architecture

Domain-driven architecture for reconstructing C++ class headers from DWARF debug information embedded in ELF binaries.

## Purpose and Scope

This tool reconstructs C++ header files from compiled binaries (ELF format) for the Dragon's Dogma Online game engine (MTFramework). The primary use case is reverse engineering and modding support where original source code is unavailable but debug symbols remain in the binary.

**Key Challenge:** DWARF debug information references types across multiple compilation units (CUs), can contain incomplete definitions (forward declarations), and requires complex resolution to reconstruct complete class hierarchies. The tool must efficiently search potentially thousands of CUs while avoiding performance pitfalls and handling edge cases.

## System Architecture

The architecture follows domain-driven design with clear separation between orchestration, business logic, and infrastructure:

```
┌─────────────────────────────────────────────────────────────┐
│  Application Layer: Orchestration & Public API              │
│  - DwarfGenerator (main entry point)                        │
│  - Coordinates domain services                              │
│  - Manages lifecycle and caching                            │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  Domain Layer: Core Business Logic                          │
├─────────────────────────────────────────────────────────────┤
│  Models: ClassInfo, MemberInfo, MethodInfo                  │
│  Services:                                                   │
│    - ClassParser: DWARF parsing with multi-CU resolution    │
│    - TypeResolver: Typedef and type chain resolution        │
│    - HierarchyBuilder: Dependency graph construction        │
│    - HeaderGenerator: C++ code generation                   │
│  Repositories: Symbol cache, Header cache                   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│  Infrastructure Layer: Configuration & External Interfaces   │
│  - ELF file handling (PS3/PS4 compatibility)                │
│  - Logging and performance tracking                         │
│  - Configuration management                                 │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
src/ddon_dwarf_reconstructor/
├── application/
│   └── generators/
│       └── dwarf_generator.py          # Main orchestrator and public API
│
├── domain/
│   ├── models/dwarf/                   # Data structures
│   │   ├── class_info.py              # Complete class representation
│   │   ├── member_info.py             # Member variables with DWARF offsets
│   │   ├── method_info.py             # Method signatures with type offsets
│   │   ├── parameter_info.py          # Parameter definitions
│   │   ├── enum_info.py               # Enumeration types
│   │   ├── struct_info.py             # Nested structures
│   │   └── tag_constants.py           # DWARF tag classification constants
│   │
│   ├── repositories/cache/             # Caching layer
│   │   ├── lru_cache.py               # In-memory LRU cache
│   │   ├── persistent_symbol_cache.py # Disk-persisted symbol cache
│   │   └── header_cache.py            # SHA256-based header deduplication
│   │
│   └── services/
│       ├── parsing/                    # DWARF parsing services
│       │   ├── class_parser.py        # Multi-CU class discovery & parsing
│       │   ├── array_parser.py        # Array type handling
│       │   ├── die_type_classifier.py # Tag validation with O(1) lookup
│       │   └── type_chain_traverser.py # Type reference resolution
│       │
│       ├── generation/                 # Code generation services
│       │   ├── header_generator.py    # C++ header file generation
│       │   ├── hierarchy_builder.py   # Inheritance hierarchy construction
│       │   ├── dependency_extractor.py # Dependency graph analysis
│       │   ├── file_registry.py       # Source file organization
│       │   └── packing_analyzer.py    # Memory layout analysis
│       │
│       └── lazy_dwarf_index_service.py # Lazy DIE loading with offset index
│
├── core/
│   └── lazy_type_resolver.py          # Type resolution with filtering
│
└── infrastructure/
    ├── config/                         # Configuration
    │   ├── application_config.py      # Application settings
    │   └── dwarf_config.py            # DWARF-specific constants
    │
    ├── logging/                        # Observability
    │   ├── logger_setup.py            # Structured logging
    │   └── progress_tracker.py        # Performance tracking
    │
    └── elf_platform.py                 # Platform detection (PS3/PS4)
```

## Core Components

### Application Layer

#### DwarfGenerator

**Purpose:** Main orchestrator providing the public API for header generation.

**Responsibilities:**
- Initializes and coordinates all domain services
- Manages ELF file lifecycle (open/close)
- Provides generation modes (single class, full hierarchy, multi-file)
- Handles platform detection automatically

**Why this design:** Centralizing orchestration separates high-level workflows from low-level parsing logic. Clients interact with a simple API while complex multi-CU resolution, caching, and type resolution happen transparently.

```python
class DwarfGenerator(BaseGenerator):
    def generate_header(self, class_name: str) -> str:
        """Generate header for a single class.
        
        Use case: Quick extraction of one class without dependencies.
        Returns: Single header file as string.
        """
    
    def generate_complete_hierarchy_header(self, class_name: str) -> str:
        """Generate complete inheritance hierarchy in single file.
        
        Use case: Reverse engineering where all dependencies needed in one file.
        Returns: Monolithic header with all base classes and dependencies.
        """
    
    def generate_multi_file_hierarchy(self, class_name: str) -> dict[str, str]:
        """Generate hierarchy organized by source files.
        
        Use case: Modular codebases where classes organized by original files.
        Returns: Dict mapping filename to header content.
        """
```

**Helper Methods:** To avoid code duplication between generation modes, common operations are extracted:

```python
def _expand_typedef_search(self, full_hierarchy: bool = True) -> None:
    """Configure type resolver for hierarchy mode.
    
    Why: Hierarchy generation requires broader typedef search than single class.
    """

def _build_hierarchy_with_timing(
    self, class_name: str, max_depth: int = 10
) -> tuple[dict[str, ClassInfo], list[str]]:
    """Build complete inheritance chain with dependencies.
    
    Why: Centralize hierarchy logic to ensure consistency across modes.
    Returns: (class_infos dict, hierarchical ordering)
    """

def _validate_hierarchy(
    self, class_infos: dict[str, ClassInfo], class_name: str
) -> bool:
    """Check if hierarchy contains any classes.
    
    Why: Early failure detection prevents downstream errors in generation.
    """

def _collect_typedefs_and_packing(
    self, class_infos: dict[str, ClassInfo]
) -> dict[str, str]:
    """Analyze memory layout and collect typedef dependencies.
    
    Why: Combine two iterations into one for efficiency.
    Single pass through all classes reduces complexity from O(2n) to O(n).
    """
```

**Rationale for helper extraction:** Both single-file and multi-file modes share ~85% of logic. Extracting shared operations:
- Ensures bug fixes apply to all modes automatically
- Makes mode-specific differences explicit (FileRegistry, output format)
- Enables independent testing of each step
- Reduces maintenance burden

### Domain Layer - Models

#### Data Structures

**Design principle:** All models capture DWARF offset references alongside human-readable type names. This enables validation and prevents string-based parsing errors.

```python
@dataclass
class ClassInfo:
    """Complete representation of a C++ class."""
    name: str
    size: int                       # Memory footprint in bytes
    members: list[MemberInfo]
    methods: list[MethodInfo]
    enums: list[EnumInfo]
    structs: list[StructInfo]
    unions: list[UnionInfo]
    base_classes: list[str]         # Inheritance hierarchy
    vtable_ptr_offset: int | None   # Virtual table pointer location
    packing_info: PackingInfo | None
    cu_offset: int | None           # DWARF compilation unit offset
    declaration_file: str | None    # Source file path

@dataclass  
class MemberInfo:
    """Member variable with type validation support."""
    name: str
    type_name: str                  # Human-readable (e.g., "MtObject*")
    type_offset: int | None         # DWARF DIE offset for validation
    offset: int                     # Memory offset within class
    bit_size: int | None            # Bitfield width (if applicable)
    bit_offset: int | None          # Bitfield position

@dataclass
class MethodInfo:
    """Method signature with return type validation."""
    name: str
    return_type: str
    return_type_offset: int | None  # DWARF DIE offset
    parameters: list[ParameterInfo]
    is_virtual: bool
    vtable_index: int | None        # Position in vtable
```

**Why track offsets?** DWARF uses cross-references between DIEs (Debug Information Entries) via offsets. Storing these offsets enables:
- O(1) validation: Quickly verify type exists via offset lookup
- Cross-CU references: Types can reference DIEs in different compilation units
- Cycle detection: Track visited offsets to prevent infinite loops
- Cache efficiency: Offsets are smaller and more cacheable than full DIE structures

### Domain Layer - Parsing Services

#### ClassParser

**Purpose:** Discover and parse C++ classes from DWARF debug information across multiple compilation units.

**Key challenge:** Classes can appear in multiple CUs with varying completeness:
1. **Forward declaration:** `class Foo;` (DW_AT_declaration=true, no members)
2. **Complete definition:** Full class with all members and methods
3. **Partial definition:** Some members missing due to compiler optimizations

**Multi-CU Resolution Strategy:**

The parser uses a scoring algorithm to select the best definition:

```python
def _calculate_type_score(self, die: DIE) -> int:
    """Assign quality score to type definition.
    
    Scoring rules:
    - Forward declaration: -1000  (explicitly marked incomplete)
    - Typedef with target: 5000   (valid type alias)
    - Base type (int, float): 8000 (primitive type)
    - Enum with size: 6000        (complete enumeration)
    - Class with members: 10000 + byte_size (prefer larger/more complete)
    
    Rationale:
    - Negative score for forward declarations ensures they're only used as fallback
    - Base types score highest as they're always complete
    - Class size as tiebreaker: larger classes typically more complete
    - Early exit at score >= 5000 avoids scanning all CUs unnecessarily
    """
```

**Search algorithm:**

```python
def find_class(self, class_name: str) -> tuple[CompileUnit, DIE] | None:
    """Locate best class definition with intelligent fallback.
    
    Algorithm:
    1. Check cache (lazy-loaded persistent cache)
    2. Validate cached entry: Is it a forward declaration?
    3. If forward declaration, trigger targeted multi-CU search
    4. If search fails, fall back to full DWARF scan with timeout
    5. Return highest-scoring definition found
    
    Why this order:
    - Cache first: O(1) for repeated lookups (85% hit rate)
    - Validation catches incomplete cache entries early
    - Targeted search: Faster than full scan (uses symbol indices)
    - Full scan: Last resort with 180s timeout to prevent hangs
    """
```

**Timeout Protection:**

```python
def _find_class_full_scan(
    self, class_name: str, timeout: float = 180.0
) -> tuple[CompileUnit, DIE] | None:
    """Search all CUs with timeout protection.
    
    Why timeout needed:
    - Large ELF files have 1000+ compilation units
    - Some types (pthread_mutex, system types) lack debug info entirely
    - Without timeout, tool hangs indefinitely on missing types
    - 180s default: Sufficient for full scan while preventing infinite wait
    
    Optimization: Early exit when score >= 5000 (complete type found)
    """
```

**Type Blacklist:**

```python
TYPE_BLACKLIST = {
    "pthread_mutex",
    "pthread_cond",
    "ScePthreadMutex",
    # ... other system types
}
```

**Why blacklist?** System types often lack debug information in game binaries. Searching all CUs for them wastes time. Blacklisting provides immediate failure for known problematic types.

#### TypeChainTraverser

**Purpose:** Follow chains of type references to find the terminal (named) type.

**Problem:** DWARF represents complex types as chains:
```
pointer → const → class Foo
pointer → pointer → int
```

**Solution:**

```python
@staticmethod
def get_terminal_type_offset(die: DIE, dwarf_info) -> int | None:
    """Extract terminal type offset from reference chain.
    
    Handles:
    - DW_TAG_pointer_type → DW_TAG_const_type → DW_TAG_class_type
    - DW_TAG_typedef → DW_TAG_base_type
    - Cycles (self-referential types)
    
    Why offsets not names:
    - Offset lookup is O(1) via index
    - Names may not be unique (templates, nested types)
    - Offsets enable cross-CU references
    
    Max depth: 20 (prevents infinite loops from malformed DWARF)
    """
```

#### LazyTypeResolver

**Purpose:** Resolve typedef aliases and filter internal DWARF type names.

**Key insight:** DWARF uses internal type names like `class_type`, `structure_type`, `void` that shouldn't appear in generated headers. The resolver filters these:

```python
DWARF_INTERNAL_TYPES = {
    "class_type", "structure_type", "union_type",
    "enumeration_type", "void", "subroutine_type"
}

def _is_internal_type_name(self, type_name: str) -> bool:
    """Check if name is DWARF internal representation.
    
    Why filter:
    - "class_type" isn't valid C++
    - These indicate missing type information
    - Better to use "void*" than invalid type name
    """
```

**Typedef collection:**

```python
def collect_used_typedefs(
    self,
    members: list[MemberInfo],
    methods: list[MethodInfo],
    # ...
) -> dict[str, str]:
    """Gather typedef definitions referenced by class.
    
    Why separate collection:
    - Typedefs may be defined in different headers
    - Need complete set before generating #include directives
    - Enables deduplication across multiple classes
    - Cache improves performance (85% hit rate)
    
    Returns: dict[typedef_name] = resolved_type
    Example: {"u32": "unsigned int", "s16": "short"}
    """
```

#### LazyDwarfIndexService

**Purpose:** Provide O(1) offset-based DIE lookup with lazy index building.

**Why lazy loading?** Building a complete offset→DIE index upfront for a large ELF file:
- Takes 5-10 seconds
- Consumes significant memory
- Most lookups only access small subset of DIEs

**Lazy approach:**

```python
class LazyDwarfIndexService:
    def get_die_by_offset(self, offset: int) -> DIE | None:
        """Retrieve DIE by offset with on-demand index building.
        
        Algorithm:
        1. Check if offset in cache → return immediately
        2. Find compilation unit containing offset (binary search)
        3. Index that CU's DIEs
        4. Cache result
        5. Return DIE
        
        Performance:
        - First lookup in CU: O(n) to index CU
        - Subsequent lookups: O(1) from cache
        - Memory: Only indexes accessed CUs (10-20% typical)
        """
```

**Multi-CU symbol search:**

```python
def targeted_symbol_search(
    self, symbol_name: str, timeout: float = 180.0
) -> int | None:
    """Search all CUs for symbol with scoring.
    
    Use case: Cache returned forward declaration, need complete definition.
    
    Advantages over full scan:
    - Uses same scoring algorithm as ClassParser (consistency)
    - Tracks global best score across CUs
    - Early exit optimization
    - Timeout protection
    
    Returns: Offset of best match (or None if not found/timeout)
    """
```

### Domain Layer - Generation Services

#### HierarchyBuilder

**Purpose:** Construct complete inheritance hierarchies with dependency resolution.

**Challenge:** C++ classes have complex dependencies:
```cpp
class rLayout : public cResource {  // Inheritance
    MtDTI* mpDTI;                  // Member type
    SetInfo mInfo;                 // Embedded struct
    MtArray<Material*> materials;  // Template with pointer
};
```

All types (cResource, MtDTI, SetInfo, MtArray, Material) must be declared before rLayout.

**Algorithm:**

```python
def build_full_hierarchy_with_dependencies(
    self, class_name: str, max_depth: int = 10
) -> tuple[dict[str, ClassInfo], list[str]]:
    """Build complete dependency graph in topological order.
    
    Steps:
    1. Parse target class
    2. Recursively parse base classes (inheritance chain)
    3. Extract member type dependencies
    4. Extract method parameter/return type dependencies
    5. Topologically sort: bases before derived, dependencies before users
    
    Returns:
    - class_infos: Dict of all classes needed
    - hierarchy_order: List of class names in declaration order
    
    Why topological sort:
    - C++ requires types declared before use
    - Forward declarations insufficient for inheritance
    - Compiler processes declarations linearly
    
    Max depth limit:
    - Prevents infinite recursion from circular references
    - Handles malformed DWARF gracefully
    """
```

**Dependency extraction uses offsets:**

```python
def _extract_member_dependencies(
    self, class_info: ClassInfo
) -> set[int]:
    """Extract type offsets from members.
    
    Why offsets not names:
    - Handles templates: "MtArray<Material*>" → offsets for MtArray and Material
    - Avoids string parsing edge cases
    - Enables validation via LazyDwarfIndexService
    """
```

#### HeaderGenerator

**Purpose:** Generate valid C++ header files from parsed class information.

**Responsibilities:**
- Format class declarations with proper syntax
- Generate forward declarations for dependencies
- Include typedef definitions
- Add header guards and includes
- Optionally include DWARF metadata as comments

**Single-file vs Multi-file:**

```python
def generate_single_file_hierarchy_header(
    self,
    class_infos: dict[str, ClassInfo],
    hierarchy_order: list[str],
    target_class: str,
    typedefs: dict[str, str],
    include_metadata: bool = True
) -> str:
    """Generate monolithic header with all classes.
    
    Use case: Reverse engineering, all-in-one header for single class
    
    Structure:
    #ifndef CLASSNAME_HIERARCHY_H
    #define CLASSNAME_HIERARCHY_H
    
    // Typedefs
    typedef unsigned int u32;
    
    // Forward declarations
    class MtObject;
    
    // Classes in dependency order
    class MtObject { ... };
    class cResource : public MtObject { ... };
    class rLayout : public cResource { ... };
    
    #endif
    """
```

**Multi-file generation uses FileRegistry:**

```python
# In DwarfGenerator.generate_multi_file_hierarchy()
file_registry = FileRegistry(dwarf_info)
for class_name, class_info in class_infos.items():
    file_registry.register_class(
        class_name,
        class_info.cu_offset,
        class_info.declaration_file  # From DW_AT_decl_file attribute
    )

classes_by_file = file_registry.get_classes_by_file()
# Returns: {"MtObject.h": ["MtObject"], "cResource.h": ["cResource"], ...}
```

**Why FileRegistry?** DWARF's `DW_AT_decl_file` attribute records the original source file path. Using this:
- Preserves original project organization
- Makes generated headers modular
- Enables selective inclusion
- Matches developer expectations

#### PackingAnalyzer

**Purpose:** Analyze memory layout and detect padding inefficiencies.

**Why important:** Understanding class size and alignment helps:
- Verify reverse engineering accuracy
- Identify optimization opportunities
- Match original struct layout exactly (critical for binary compatibility)

```python
@dataclass
class PackingInfo:
    natural_size: int      # Sum of member sizes
    actual_size: int       # Class size from DWARF
    padding_bytes: int     # actual_size - natural_size
    suggested_pack: int    # Recommended #pragma pack value
    efficiency: float      # 1.0 - (padding / actual_size)

def calculate_packing_info(class_info: ClassInfo) -> PackingInfo:
    """Analyze member alignment and padding.
    
    Algorithm:
    1. Sum natural member sizes
    2. Compare with actual class size from DWARF
    3. Calculate padding as difference
    4. Suggest #pragma pack value (1, 2, 4, 8) based on alignment
    
    Why include in generated header:
    - Documents memory layout for reverse engineers
    - Identifies discrepancies between DWARF and reality
    - Helps reproduce exact binary layout
    """
```

### Domain Layer - Repositories

#### Caching Strategy

**Three-tier caching for performance:**

1. **LRU Cache (in-memory):**
```python
# O(1) access for hot data
die_cache: LRUCache[int, DIE] = LRUCache(maxsize=10000)
type_cache: LRUCache[int, str] = LRUCache(maxsize=5000)
```

**Why LRU?** Parsing exhibits locality:
- Classes reference same types repeatedly
- Base classes parsed before derived classes
- Hot data stays in cache, cold data evicted automatically

2. **PersistentSymbolCache (disk-based JSON):**
```python
# Persists offset→class_name mappings
{
  "MtObject": {"offset": 34021, "size": 8, "has_children": true},
  "cResource": {"offset": 77887, "size": 112, "has_children": true}
}
```

**Rationale:**
- Repeated tool runs avoid re-parsing (5-10s saved per run)
- Cache invalidation via ELF file modification time
- Human-readable format aids debugging

3. **HeaderCache (SHA256-based):**
```python
def should_regenerate(self, filename: str, new_content: str) -> bool:
    """Check if header content changed.
    
    Use case: Multi-file generation creates many headers.
    Only write files that actually changed to:
    - Preserve timestamps for build systems
    - Reduce disk I/O
    - Avoid unnecessary recompilation
    """
```

**Why SHA256?** Content-addressable storage:
- Small cache files (hashes are 32 bytes)
- Cryptographically collision-resistant
- Fast comparison (no need to read full old content)

### Infrastructure Layer

#### Platform Detection

**Challenge:** Tool must support both PS3 (PowerPC, big-endian, DWARF2) and PS4 (x86-64, little-endian, DWARF3/4).

```python
@dataclass
class PlatformDetector:
    @staticmethod
    def detect_platform(elf_file: ELFFile) -> ELFPlatform:
        """Identify platform from ELF characteristics.
        
        Detection criteria:
        PS4:
        - Machine: EM_X86_64
        - Endianness: Little-endian
        - ELF type: 0xfe10 (Sony custom)
        - OS/ABI: FreeBSD
        
        PS3:
        - Machine: EM_PPC64
        - Endianness: Big-endian
        - Standard ELF attributes
        
        Why automatic detection:
        - User shouldn't need to specify platform
        - Prevents misconfiguration errors
        - Enables correct byte order interpretation
        """
```

**Platform-specific handling:**

```python
# In base_generator.py
self.platform = PlatformDetector.detect_platform(self.elf_file)

# Different output directories
output_dir = f"output/{self.platform.value}/"  # "output/ps4/" or "output/ps3/"

# Different DWARF location expression parsing
if self.platform == ELFPlatform.PS3:
    # Parse [0x23, offset] format
else:
    # Parse direct integer offsets
```

#### Logging and Observability

**Design goal:** Provide detailed diagnostics without impacting performance.

```python
@log_timing
def generate_complete_hierarchy_header(self, class_name: str) -> str:
    """Decorator automatically logs execution time.
    
    Output:
    INFO: Generating complete hierarchy header for: rLayout
    DEBUG: Typedef search expansion completed in 0.003s
    DEBUG: Hierarchy building completed in 0.156s
    DEBUG: Packing analysis completed in 0.042s
    INFO: Hierarchy header generated successfully for rLayout
    INFO: [timing] generate_complete_hierarchy_header: 0.234s
    """
```

**Performance tracking:**

```python
class ProgressTracker:
    """Track operations and generate performance reports.
    
    Captures:
    - Operation name and duration
    - Call count and frequency
    - Average/min/max times
    - Total time per operation type
    
    Why: Identify performance bottlenecks during development
    """
```

## Generation Workflows

### Single Class Generation

```python
# Generate header for one class without dependencies
with DwarfGenerator("game.elf") as gen:
    header = gen.generate_header("MtObject")
```

**Flow:**
1. ClassParser finds "MtObject" (checks cache, searches CUs if needed)
2. Parse class structure (members, methods, nested types)
3. TypeResolver collects typedefs used by class
4. HeaderGenerator formats C++ header
5. Output written to `output/ps4/MtObject.h`

**Use case:** Quick extraction of single class for inspection.

### Full Hierarchy Generation (Single File)

```python
# Generate complete inheritance chain in one file
with DwarfGenerator("game.elf") as gen:
    header = gen.generate_complete_hierarchy_header("rLayout")
```

**Flow:**
1. HierarchyBuilder walks inheritance chain: rLayout → cResource → MtObject
2. DependencyExtractor finds all member/parameter types
3. Topological sort orders classes: bases before derived
4. TypeResolver collects all typedefs
5. PackingAnalyzer computes memory layout for each class
6. HeaderGenerator creates single monolithic header
7. Output: `output/ps4/rLayout.h` contains all dependencies

**Use case:** Reverse engineering where all related classes needed together.

**Example output structure:**
```cpp
#ifndef RLAYOUT_HIERARCHY_H
#define RLAYOUT_HIERARCHY_H

// Typedefs (52 in this case)
typedef unsigned int u32;
typedef int s32;
// ...

// Forward declarations
class MtString;
class SetInfo;
// ...

// Base class
class MtObject { /* 8 bytes, 0 members */ };

// Intermediate class
class cResource : public MtObject { /* 112 bytes, 9 members */ };

// Target class
class rLayout : public cResource { /* 528 bytes, 12 members */ };

#endif
```

### Multi-File Hierarchy Generation

```python
# Generate hierarchy organized by original source files
with DwarfGenerator("game.elf") as gen:
    headers = gen.generate_multi_file_hierarchy("rLayout")
    # Returns: {"MtObject.h": "...", "cResource.h": "...", "rLayout.h": "..."}
```

**Flow:**
1. HierarchyBuilder constructs complete dependency graph
2. FileRegistry extracts `DW_AT_decl_file` from each class
3. Group classes by source file path
4. HeaderGenerator creates separate header per file
5. HeaderCache checks which files changed
6. Write only modified headers

**Use case:** Reconstructing modular codebase structure.

**Advantages:**
- Matches original project organization
- Enables selective includes
- Better IDE support (jump to definition works)
- Easier to navigate large codebases

## Design Principles and Rationale

### Offset-Based Type Resolution

**Core design decision:** Track DWARF offsets alongside type names.

**Why offsets?**
- **Validation:** O(1) lookup via LazyDwarfIndexService verifies type exists
- **Cross-CU references:** Types can reference DIEs in any compilation unit
- **Cache efficiency:** Integers (8 bytes) vs DIE structures (100s of bytes)
- **Eliminates string parsing:** Avoid complex template/pointer type string manipulation
- **Cycle detection:** Track visited offsets to prevent infinite loops

**Example:**
```python
# Without offsets (error-prone):
member.type_name = "MtArray<Material*>"  # How to parse this?

# With offsets (robust):
member.type_name = "MtArray<Material*>"   # For display
member.type_offset = 0x20f3c              # For validation
# Lookup validates MtArray exists and retrieves its full DIE
```

### Separation of Concerns

**Parsing (ClassParser) vs Generation (HeaderGenerator):**

**Why separate?**
- **Testability:** Mock HeaderGenerator to test parsing logic
- **Flexibility:** Generate different formats (JSON, XML) from same parsed models
- **Single Responsibility:** Each component has one reason to change
- **Reusability:** HeaderGenerator can format manually constructed ClassInfo

### Lazy Loading

**Applied throughout:**
- DWARF index built on-demand per CU
- Type resolution cached, not pre-computed
- Symbol cache loaded only if file exists

**Rationale:**
- Large ELF files have 1000+ CUs totaling 100+ MB of DWARF data
- Most tool invocations access <10% of data
- Upfront loading wastes time and memory
- Lazy approach: Fast startup, memory scales with usage

### Dependency Injection

**Pattern:**
```python
class DwarfGenerator:
    def __init__(self, elf_path: Path):
        # Initialize services
        self.lazy_index = LazyDwarfIndexService(dwarf_info)
        self.type_resolver = LazyTypeResolver(lazy_index)
        self.class_parser = ClassParser(type_resolver, dwarf_info)
        self.hierarchy_builder = HierarchyBuilder(class_parser, type_resolver)
```

**Benefits:**
- **Testing:** Replace real services with mocks
- **Configuration:** Inject different implementations
- **Clarity:** Dependencies explicit, not hidden in constructors
- **Lifecycle management:** Centralized in one place

### Type Safety

**Full type hints on all functions:**
```python
def get_die_by_offset(self, offset: int) -> DIE | None:
def build_hierarchy(self, name: str, max_depth: int = 10) -> tuple[dict, list]:
```

**Why important:**
- **Early error detection:** MyPy catches type mismatches at dev time
- **Documentation:** Type signatures document expected inputs/outputs
- **IDE support:** Autocomplete and type checking in editors
- **Refactoring safety:** Type checker validates changes across codebase

## Performance Characteristics

### Time Complexity

| Operation | Complexity | Rationale |
|-----------|-----------|-----------|
| DIE lookup by offset | O(1) | Hash table after lazy index build |
| Class cache lookup | O(1) | Dictionary keyed by class name |
| Typedef resolution | O(1) | LRU cache, high hit rate |
| Tag classification | O(1) | Set membership using frozensets |
| Single class parse | O(n) | n = number of members/methods |
| Full hierarchy build | O(d × n) | d = depth, n = avg members per class |
| Multi-CU search | O(c × m) | c = CUs, m = DIEs per CU (with early exit) |

### Space Complexity

| Component | Space | Notes |
|-----------|-------|-------|
| DIE cache | O(n) | n = accessed DIEs (~10-20% of total) |
| Symbol cache | O(s) | s = number of symbols (~500 typical) |
| Type cache | O(t) | t = unique types (~1000 typical) |
| ClassInfo | O(m + h) | m = members, h = methods |

### Benchmark Data (PS4 DDOORBIS.elf)

| Operation | Time | Details |
|-----------|------|---------|
| Initial load + cache build | 0.3s | First run, no cache |
| Cached load | 0.002s | Subsequent runs |
| Single class (MtObject) | 0.1s | 8 bytes, 0 members |
| Complex class (rLayout) | 0.2s | 528 bytes, 12 members, 19 methods |
| Full hierarchy (rLayout) | 4.6s | 285 classes, 341KB output |
| Multi-CU search (complete scan) | 8-12s | 1000+ CUs, no early exit |
| Multi-CU search (early exit) | 0.5-2s | Finds complete type quickly |

## Limitations and Trade-offs

### DWARF Support

**Supported:**
- DWARF 2 (PS3): Basic support, location expressions parsed
- DWARF 3/4 (PS4): Full support, primary target

**Limited:**
- DWARF 5: Untested, may work for basic features
- Missing debug sections: Cannot work without .debug_info/.debug_abbrev

**Not supported:**
- Stripped binaries (no debug symbols)
- Partial DWARF data (incomplete compilation)

### C++ Feature Coverage

**Supported:**
- Classes, structs, unions
- Inheritance (single and multiple)
- Virtual methods and vtables
- Templates (basic, name extracted as-is)
- Nested types
- Bitfields
- Enumerations
- Typedefs

**Limited:**
- Templates: No parameter extraction, treated as strings
- Namespaces: Parsed but minimal handling
- Anonymous types: Synthesized names used

**Not supported:**
- C++20 concepts, modules, coroutines
- constexpr evaluation
- Compile-time type traits

**Rationale:** Tool targets game engine reverse engineering where focus is runtime structure, not modern C++ metaprogramming.

### Binary Requirements

**Must have:**
- ELF format (PS3/PS4)
- Complete DWARF debug information
- .debug_info and .debug_abbrev sections

**Why games often have this:**
- Debug builds for testing
- Certification requirements (Sony)
- Crash report symbolication
- Development/QA builds leaked

### Performance Trade-offs

**Full scan timeout (180s):**
- **Pro:** Prevents infinite hangs on missing types
- **Con:** May give up on types that exist but are deep in symbol table
- **Mitigation:** Blacklist known problematic types, targeted search first

**Cache validation:**
- **Pro:** Detects forward declarations, finds complete types
- **Con:** Extra lookup per cached symbol
- **Mitigation:** Validation is O(1) DIE attribute check

**Multi-file generation:**
- **Pro:** Modular output, matches original structure
- **Con:** More complex than single-file, requires FileRegistry
- **Benefit:** Complexity isolated, shared helpers reused

## Testing Strategy

**Test categories:**

1. **Unit tests (216):** Mock all external dependencies
   - ClassParser with mocked DWARF structures
   - TypeResolver with mocked offset lookups
   - HeaderGenerator with mocked ClassInfo
   
2. **Integration tests (2):** Use real ELF files
   - PS4: `resources/DDOORBIS.elf`
   - PS3: `resources/PS3/EBOOT.ELF`
   
**Why this split:**
- Unit tests: Fast (<1s), test logic in isolation
- Integration tests: Slow (~4s), validate end-to-end with real data

**Critical test cases:**
- Multi-CU resolution: Verify complete definitions chosen over forward declarations
- Timeout handling: Ensure search terminates within configured limit
- Type blacklist: Verify known problematic types rejected immediately
- Scoring algorithm: Validate correct type selection across CUs
- Cache validation: Ensure forward declarations detected and re-searched

## Platform-Specific Validation

### PS4 (x86-64, DWARF 3/4)

**Test file:** `resources/DDOORBIS.elf` (Dragon's Dogma Online)

**Validated classes:**
```
MtDTI:     56 bytes, 14 members, 23 methods
rLayout:  528 bytes, 12 members, 19 methods  
MtFloat3:  12 bytes,  5 members, 10 methods
```

**Key features tested:**
- Standard DWARF 4 attribute parsing
- Little-endian byte order
- Virtual method extraction
- Template type handling
- Multi-CU type resolution (rLayout references 285 classes)

### PS3 (PowerPC64, DWARF 2)

**Test file:** `resources/PS3/EBOOT.ELF` (Dragon's Dogma)

**Validated classes:**
```
MtDTI:   32 bytes, 10 members,  2 methods
MtUI:     1 byte,   0 members,  0 methods
rLayout: 1144 bytes, 6 members, 0 methods
```

**Key differences:**
- **Location expressions:** Member offsets as `[DW_OP_plus_uconst, offset]` not integers
- **Big-endian:** Affects bit packing and byte order interpretation
- **DWARF 2:** Older specification, fewer attributes

**Compatibility approach:** Platform detection automatic, parser adapts to DWARF version.

## Extension Points

### Custom Generators

**Use case:** Generate formats other than C++ headers.

```python
class JsonGenerator(BaseGenerator):
    """Generate JSON schema from DWARF."""
    
    def generate(self, class_name: str) -> str:
        class_info = self.class_parser.parse_class(class_name)
        return json.dumps({
            "name": class_info.name,
            "size": class_info.size,
            "members": [m.to_dict() for m in class_info.members]
        }, indent=2)
```

**Benefit:** Reuse entire parsing layer, only change output format.

### Custom Type Resolution

**Use case:** Domain-specific type mappings.

```python
class GameTypeResolver(LazyTypeResolver):
    """Custom resolver for game engine types."""
    
    CUSTOM_MAPPINGS = {
        "MT_FLOAT": "float",
        "MT_INT": "int32_t"
    }
    
    def resolve_type(self, type_name: str) -> str:
        if type_name in self.CUSTOM_MAPPINGS:
            return self.CUSTOM_MAPPINGS[type_name]
        return super().resolve_type(type_name)
```

**Benefit:** Extend without modifying core resolver.

### Custom Validators

**Use case:** Verify generated headers match expected patterns.

```python
class HeaderValidator:
    """Validate generated headers for game-specific requirements."""
    
    def validate_vtable(self, class_info: ClassInfo) -> bool:
        """Ensure virtual method table matches expected layout."""
        if class_info.vtable_ptr_offset != 0:
            return False  # vtable must be first member
        return True
```

**Integration:** Run as post-generation step.

## References

- [DWARF 4 Standard](http://dwarfstd.org/doc/DWARF4.pdf)
- [pyelftools Documentation](https://github.com/eliben/pyelftools)
- [PS4 ELF Format](knowledge-base/ps4-elf/)
- [Testing Guide](TESTING.md)
- [Dragon's Dogma Online](https://en.wikipedia.org/wiki/Dragon%27s_Dogma_Online) - Target game
