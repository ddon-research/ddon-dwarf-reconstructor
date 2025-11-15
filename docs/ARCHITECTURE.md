# Architecture

Domain-driven architecture for DWARF-to-C++ header reconstruction.

## System Overview

```
ELF File  DWARF Info  Parsed Models  C++ Headers
           
    Application Layer (Orchestration)
           
    Domain Layer (Business Logic)
           
    Infrastructure Layer (Config, Logging)
```

## Directory Structure

```
src/ddon_dwarf_reconstructor/
 application/
    generators/
        dwarf_generator.py      # Main orchestrator

 domain/
    models/dwarf/               # Data structures
       class_info.py           # Class representation
       member_info.py          # Member variables with type_offset
       method_info.py          # Method signatures with return_type_offset
       parameter_info.py       # Parameters with type_offset
       enum_info.py            # Enumerations
       struct_info.py          # Nested types
       tag_constants.py        # DWARF tag classification (frozensets)
   
    repositories/cache/
       lru_cache.py            # Fast in-memory cache
       persistent_symbol_cache.py  # Disk-based cache
       header_cache.py         # SHA256-based header cache with persistence
   
    services/
        parsing/
           class_parser.py         # DWARF parsing with offset capture
           array_parser.py         # Array type parsing
           die_type_classifier.py  # Tag validation (O(1) lookups)
           type_chain_traverser.py # Offset-based type traversal
       
        generation/
            base_generator.py       # ELF management
            header_generator.py     # C++ code generation (offset-based)
            hierarchy_builder.py    # Offset-based dependencies (243 lines)
            dependency_extractor.py # Pure offset-based extraction (307 lines)
            packing_analyzer.py     # Memory layout
       
        lazy_dwarf_index_service.py # Lazy DIE loading with O(1) offset lookup

 core/
     lazy_type_resolver.py      # Type resolution with internal type filtering

 infrastructure/
     config/
        application_config.py   # App settings
        dwarf_config.py         # DWARF constants
    
     logging/
         logger_setup.py         # Logging config
         progress_tracker.py     # Performance tracking
```

## Core Components

### Application Layer

**dwarf_generator.py** - Main orchestrator
- Coordinates all domain services
- Provides public API (generate_header, generate_complete_hierarchy_header)
- Handles PS4 ELF compatibility automatically
- Manages component lifecycle

```python
class DwarfGenerator(BaseGenerator):
    def __init__(self, elf_path: Path):
        self.type_resolver: TypeResolver
        self.class_parser: ClassParser
        self.hierarchy_builder: HierarchyBuilder
        self.header_generator: HeaderGenerator
    
    @log_timing
    def generate_header(self, class_name: str) -> str:
        """Single class generation pipeline."""
    
    @log_timing
    def generate_complete_hierarchy_header(self, class_name: str) -> str:
        """Full inheritance hierarchy pipeline."""
```

### Domain Layer - Models

**Data Structures** (src/domain/models/dwarf/)

```python
@dataclass
class ClassInfo:
    name: str
    size: int
    members: list[MemberInfo]
    methods: list[MethodInfo]
    enums: list[EnumInfo]
    structs: list[StructInfo]
    unions: list[UnionInfo]
    base_classes: list[str]
    vtable_ptr_offset: int | None

@dataclass  
class MemberInfo:
    name: str
    type_name: str              # Display name (e.g., "MtObject*")
    type_offset: int | None     # DWARF DIE offset for validation
    offset: int
    bit_size: int | None
    bit_offset: int | None

@dataclass
class MethodInfo:
    name: str
    return_type: str            # Display name
    return_type_offset: int | None  # DWARF DIE offset
    parameters: list[ParameterInfo]
    is_virtual: bool
    vtable_index: int | None

@dataclass
class ParameterInfo:
    name: str
    type_name: str              # Display name
    type_offset: int | None     # DWARF DIE offset
```

### Domain Layer - Services

**Parsing Services** (src/domain/services/parsing/)

**die_type_classifier.py** - Tag validation service (NEW)

- Static methods for O(1) tag classification
- Prevents invalid assumptions (enums as forward-declarable, namespaces as classes)
- Uses frozensets from tag_constants.py

```python
class DIETypeClassifier:
    @staticmethod
    def is_named_type(die: DIE) -> bool:
        """Check if DIE is class/struct/union/enum/typedef/namespace."""
    
    @staticmethod
    def is_forward_declarable(die: DIE) -> bool:
        """Check if DIE is class/struct/union (only these can be forward declared)."""
    
    @staticmethod
    def requires_resolution(die: DIE) -> bool:
        """Check if type needs dependency resolution."""
```

**type_chain_traverser.py** - Offset extraction service (NEW)

- Follows type chains to terminal types (pointer→const→class)
- Returns DWARF offsets, not string names
- Cycle detection, max depth 20

```python
class TypeChainTraverser:
    @staticmethod
    def get_terminal_type_offset(die: DIE, dwarf_info) -> int | None:
        """Extract terminal type offset from DIE chain."""
    
    @staticmethod
    def follow_to_terminal_type(die: DIE, dwarf_info) -> DIE | None:
        """Follow DW_AT_type chain to named type."""
```

**class_parser.py** - DWARF parsing with multi-CU resolution

- Finds classes in compilation units with intelligent scoring
- **Multi-CU type resolution:** Searches all compilation units to find complete definitions
- **Type-aware scoring algorithm:**
  - Forward declarations (DW_AT_declaration): -1000 penalty
  - Typedefs with DW_AT_type: 5000
  - Base types (int, float, etc.): 8000
  - Enums with size: 6000
  - Classes with members: 10000 + byte_size
- **Smart cache validation:** Validates cached entries are complete, not forward declarations
- **Timeout protection:** 180-second default prevents indefinite searches on missing types
- **Blacklist mechanism:** Skips pthread and system types without debug info
- **Early exit optimization:** Returns immediately when finding complete type (score >= 5000)
- Parses members, methods, nested types
- **Captures type_offset fields** using TypeChainTraverser
- Handles anonymous unions, virtual methods
- No generation logic (separation of concerns)

```python
class ClassParser:
    def __init__(self, type_resolver, dwarf_info, full_scan_timeout: float = 180.0):
        """Initialize with configurable timeout for full DWARF scans."""
        self.timed_out_symbols: set[str] = set()  # Track symbols that exceeded timeout
    
    @log_timing
    def find_class(self, class_name: str) -> tuple[CompileUnit, DIE] | None:
        """Efficient class discovery with scoring and timeout protection.
        
        Algorithm:
        1. Try cache first (lazy loading)
        2. Validate cached entry is not forward declaration
        3. If forward declaration, trigger targeted search across all CUs
        4. Fall back to full scan with timeout if needed
        5. Prefer complete definitions over forward declarations via scoring
        """
    
    def _find_class_full_scan(self, class_name: str) -> tuple[CompileUnit, DIE] | None:
        """Search all CUs with type-aware scoring.
        
        Scoring rules:
        - Forward declaration: -1000
        - Typedef with DW_AT_type: 5000
        - Base type: 8000
        - Enum with size: 6000
        - Class with members: 10000 + size
        
        Early exit at score >= 5000 (typedefs, base types, enums).
        Times out after full_scan_timeout seconds (default 180s).
        """
    
    def _find_class_lazy(self, class_name: str) -> tuple[CompileUnit, DIE] | None:
        """Lazy loading with cache validation.
        
        Validates cached entries via DW_AT_declaration attribute.
        If forward declaration found, tries targeted_symbol_search.
        Falls back to returning forward declaration if no better match exists.
        """
    
    @log_timing
    def parse_class_info(self, cu: CompileUnit, class_die: DIE) -> ClassInfo:
        """Complete class parsing with type_offset capture."""
    
    def parse_member(self, member_die: DIE) -> MemberInfo:
        """Parse member with type_offset field."""
```

**lazy_dwarf_index_service.py** - Lazy DIE loading with multi-CU search

- O(1) DIE lookup by offset via lazy-loaded index
- Caches offset→DIE mappings
- **Multi-CU symbol search with scoring:** Searches all compilation units with same scoring logic as class_parser
- **Timeout protection:** Configurable timeout for targeted searches (default 180s)
- **Early exit optimization:** Returns immediately when finding complete type (score >= 5000)
- Enables offset-based type validation

```python
class LazyDwarfIndexService:
    def get_die_by_offset(self, offset: int) -> DIE | None:
        """O(1) DIE retrieval by DWARF offset."""
    
    def targeted_symbol_search(
        self, symbol_name: str, timeout: float = 180.0
    ) -> int | None:
        """Search all CUs for symbol with type-aware scoring.
        
        Uses same scoring algorithm as ClassParser:
        - Forward declaration: -1000
        - Typedef with DW_AT_type: 5000
        - Base type: 8000
        - Enum with size: 6000
        - Class with members: 10000 + size
        
        Returns offset of best match, or None if not found/timed out.
        Tracks global best score across all CUs for intelligent selection.
        """
    
    def _search_cu_for_symbol_with_score(
        self, cu: CompileUnit, symbol_name: str
    ) -> tuple[int | None, int]:
        """Search single CU and return (offset, score) tuple."""
```

**lazy_type_resolver.py** - Type resolution (REFACTORED)

- Resolves typedefs, pointers, references
- **Filters internal DWARF type names** (class_type, structure_type, void, etc.)
- Validates typedef targets (rejects names with *, &, [)
- Handles void* and anonymous structs correctly
- Caches typedef lookups (85% hit rate)

```python
class LazyTypeResolver:
    def collect_used_typedefs(self, class_infos: dict) -> dict[str, str]:
        """Collect typedefs with internal type filtering."""
    
    def _resolve_primitive_typedef(self, typedef_name: str) -> str:
        """Resolve typedef with excluded type checking."""
```

**array_parser.py** - Array type parsing

---

### Shared Generation Helper Methods (Code Duplication Reduction)

**Problem:** Originally, `generate_complete_hierarchy_header` (single-file mode) and `generate_multi_file_hierarchy` (multi-file mode) duplicated ~75% of their code:
- Typedef expansion
- Hierarchy building with timing
- Empty hierarchy validation
- Packing info and typedef collection

**Solution:** Extract shared logic into reusable helper methods (November 2025 refactoring):

**dwarf_generator.py** - Shared helper methods

```python
class DwarfGenerator:
    def _expand_typedef_search(self, full_hierarchy: bool = True) -> None:
        """Expand typedef search for hierarchy generation.
        
        Shared by both single-file and multi-file modes.
        Includes timing instrumentation for performance tracking.
        """
    
    def _build_hierarchy_with_timing(
        self, class_name: str, max_depth: int = 10
    ) -> tuple[dict[str, ClassInfo], list[str]]:
        """Build full hierarchy with dependencies and timing.
        
        Returns:
            Tuple of (class_infos dict, hierarchy_order list)
        
        Shared by both modes. Delegates to HierarchyBuilder.
        """
    
    def _validate_hierarchy(
        self, class_infos: dict[str, ClassInfo], class_name: str
    ) -> bool:
        """Validate hierarchy is not empty.
        
        Returns:
            True if valid, False if empty
        
        Shared validation logic for both modes.
        """
    
    def _collect_typedefs_and_packing(
        self, class_infos: dict[str, ClassInfo]
    ) -> dict[str, str]:
        """Add packing info and collect all typedefs from classes.
        
        Returns:
            Dictionary of collected typedefs
        
        Shared by both modes. Combines packing analysis with typedef collection
        for efficiency (single iteration over class_infos).
        """
```

**Impact:**
- Code duplication reduced from ~75% to ~15%
- Only mode-specific logic remains in main methods:
  - Single-file: Direct header generation
  - Multi-file: FileRegistry + per-file header generation
- Future bug fixes in shared logic automatically apply to both modes
- All 218 tests pass (216 unit + 2 integration)
- No regression in functionality (verified with rLayout generation)

**Usage in refactored methods:**

```python
def generate_complete_hierarchy_header(self, class_name: str) -> str:
    """Single-file mode (legacy)."""
    # Step 1: Shared - Expand typedef search
    self._expand_typedef_search(full_hierarchy=True)
    
    # Step 2: Shared - Build hierarchy
    class_infos, hierarchy_order = self._build_hierarchy_with_timing(
        class_name, max_depth=10
    )
    
    # Step 3: Shared - Validate
    if not self._validate_hierarchy(class_infos, class_name):
        return self._generate_not_found_header(class_name)
    
    # Step 4: Shared - Collect typedefs and packing
    all_typedefs = self._collect_typedefs_and_packing(class_infos)
    
    # Mode-specific: Generate single header
    header = self.header_generator.generate_single_file_hierarchy_header(
        class_infos, hierarchy_order, class_name,
        typedefs=all_typedefs, include_metadata=True
    )
    return header

def generate_multi_file_hierarchy(self, class_name: str) -> dict[str, str]:
    """Multi-file mode with FileRegistry."""
    # Steps 1-4: Same shared logic as single-file mode
    self._expand_typedef_search(full_hierarchy=True)
    class_infos, hierarchy_order = self._build_hierarchy_with_timing(
        class_name, max_depth=10
    )
    if not self._validate_hierarchy(class_infos, class_name):
        return {"UncategorizedDefinitions.h": self._generate_not_found_header(class_name)}
    
    # Mode-specific: FileRegistry for file organization
    file_registry = FileRegistry(self.dwarf_info)
    # ... register classes ...
    classes_by_file = file_registry.get_classes_by_file()
    
    # Step 4: Shared - Collect typedefs (same as single-file)
    all_typedefs = self._collect_typedefs_and_packing(class_infos)
    
    # Mode-specific: Generate headers per file
    output_headers: dict[str, str] = {}
    for file_path, file_classes in sorted(classes_by_file.items()):
        # ... generate header for each file ...
    return output_headers
```

---

**array_parser.py** - Array type parsing

- Multi-dimensional arrays: int\[10\]\[20\]\[30\]
- Bounds extraction from DWARF subrange DIEs
- Element type resolution

**Generation Services** (src/domain/services/generation/)

**base_generator.py** - ELF management

- ELF file loading with context management
- DWARF info extraction (pyelftools)
- PS4 ELF patching (automatic detection)
- Resource cleanup

```python
class BaseGenerator(ABC):
    def __enter__(self) -> "BaseGenerator":
        # Load ELF, extract DWARF, apply PS4 patches
    
    def __exit__(self):
        # Clean resource cleanup
    
    @abstractmethod
    def generate(self, symbol: str) -> str:
        """Implemented by concrete generators."""
```

**dependency_extractor.py** - Offset-based dependency resolution (NEW)

- Pure offset-based logic (no string parsing)
- Extracts dependencies from type_offset fields
- Validates types with DIETypeClassifier
- Filters internal DWARF types

```python
class DependencyExtractor:
    def extract_dependencies(self, class_info: ClassInfo) -> set[int]:
        """Extract all type offsets from members/methods/parameters."""
    
    def filter_resolvable_types(self, offsets: set[int]) -> set[int]:
        """Filter to types requiring forward declarations."""
    
    def get_type_name(self, offset: int) -> str | None:
        """Get type name from offset for resolution."""
```

**hierarchy_builder.py** - Offset-based inheritance management (REFACTORED)

- Complete inheritance chain discovery
- **Recursive offset-based dependency resolution** (371 lines deleted, 60% reduction)
- Uses DependencyExtractor for type validation
- Filters internal DWARF types (class_type, void, pointer_type, etc.)
- Base-to-derived ordering
- **Resolves ALL dependencies recursively** (not just direct references)

```python
class HierarchyBuilder:
    def __init__(self, class_parser: ClassParser, dwarf_index: LazyDwarfIndexService):
        """dwarf_index required for offset validation."""
    
    @log_timing
    def build_full_hierarchy_with_dependencies(
        self, class_name: str, max_depth: int = 10
    ) -> tuple[dict[str, ClassInfo], list[str]]:
        """Build complete hierarchy with recursive dependency resolution.
        
        Resolves all dependent types (members, methods, parameters) recursively
        up to max_depth levels. For example, if ClassA references ClassB, and
        ClassB references ClassC, all three are resolved and returned.
        """
    
    def _process_dependencies_offset_based(
        self, hierarchy_classes: dict[str, ClassInfo],
        all_classes: dict[str, ClassInfo],
        max_depth: int
    ) -> None:
        """Pure offset-based recursive dependency resolution.
        
        Algorithm:
        1. Extract type_offset from all members/methods/parameters
        2. For each offset, resolve to ClassInfo (parse full definition)
        3. Recursively extract dependencies from those ClassInfo objects
        4. Continue until max_depth or no new dependencies
        5. Track visited offsets to prevent infinite loops
        """
```

**header_generator.py** - C++ code generation (REFACTORED)

- Include guards, forward declarations
- Class definitions with members/methods
- Typedef integration
- Memory layout comments
- **Two-phase generation for full hierarchies:**
  1. **Inheritance hierarchy** (base → derived)
  2. **All dependency classes** (alphabetical order)
- **Offset-based forward declaration validation** (18 lines deleted)
- Only forward declares class/struct/union (validated via DIETypeClassifier)
- **Generates full definitions for all resolved dependencies** (not just forward declarations)

```python
class HeaderGenerator:
    def __init__(self, dwarf_index: LazyDwarfIndexService):
        """dwarf_index required for forward declaration validation."""
    
    def generate_single_class_header(self, class_info: ClassInfo) -> str:
        """Generate header for individual class."""
    
    def generate_single_file_hierarchy_header(
        self, class_infos: dict, order: list, target_class: str
    ) -> str:
        """Generate complete inheritance hierarchy in single file.
        
        Generates FULL CLASS DEFINITIONS for all classes in class_infos dict:
        - Phase 1: Inheritance chain (base → derived) 
        - Phase 2: All dependency classes (alphabetically)
        - Forward declarations: ONLY for external/unresolved types
        
        Before fix: Generated only hierarchy chain, forward declared dependencies
        After fix: Generates ALL resolved classes with full definitions
        """
    
    def _collect_forward_declarations(
        self, class_info: ClassInfo, typedefs: dict
    ) -> set[str]:
        """Offset-based validation of forward declarable types.
        
        Returns types that need forward declaration (not in class_infos dict).
        Most types should have full definitions, not forward declarations.
        """
```

**file_registry.py** - Multi-file class organization (NEW)

- Registers classes with source file mapping
- Organizes dependencies by declared file (DW_AT_decl_file)
- Handles both integer file indices and string paths
- Flexible type handling: `register_class(name, file_index: int | str | None)`
- Returns classes organized by file for multi-file generation

```python
class FileRegistry:
    def register_class(self, name: str, decl_file_index: int | str | None) -> None:
        """Register class with file mapping.
        
        Args:
            name: Class name
            decl_file_index: Integer DWARF file index, string path, or None
        """
    
    def get_classes_by_file(self) -> dict[str, list[str]]:
        """Get classes organized by source file."""
    
    def get_uncategorized_classes(self) -> list[str]:
        """Get classes without file mappings."""
    
    def summarize(self) -> dict[str, int]:
        """Display registry statistics."""
```

**header_cache.py** - Header persistence and change detection (NEW)

- SHA256-based header fingerprinting
- Persistent JSON cache: `.cache/{elf_name}_headers.json`
- Automatic change detection and invalidation
- Timestamp tracking for debugging
- Fast cache validation before regeneration

```python
class HeaderCache:
    def is_valid(self, filename: str, content: str) -> bool:
        """Check if cached header matches current content (SHA256)."""
    
    def set_header(self, filename: str, content: str) -> None:
        """Add header to cache."""
    
    def save(self) -> None:
        """Persist cache to disk as JSON."""
    
    def _compute_hash(self, content: str) -> str:
        """Generate SHA256 hash for content."""
```

**DwarfGenerator** - Multi-file hierarchy orchestration (ENHANCED)

- Added `generate_multi_file_hierarchy()` method
- Returns `dict[str, str]` mapping filename → content
- Integrates FileRegistry for class organization
- Integrates HeaderCache for change detection
- Supports both PS3 and PS4 platforms

```python
class DwarfGenerator(BaseGenerator):
    def generate_multi_file_hierarchy(
        self, class_name: str
    ) -> dict[str, str]:
        """Generate multi-file hierarchy with organization.
        
        1. Build complete hierarchy with dependencies
        2. Register all classes with FileRegistry using source files
        3. Organize classes by file
        4. Generate individual headers per file
        5. Validate against HeaderCache
        6. Return dict of filename → content
        
        Returns: dict[str, str] - mapping of filename to generated content
        """

```

**packing_analyzer.py** - Memory layout analysis

- Natural vs actual size comparison
- Padding detection
- #pragma pack suggestions
- Memory efficiency calculations

```python
def calculate_packing_info(class_info: ClassInfo) -> PackingInfo:
    """Analyze memory layout and suggest optimizations."""

@dataclass
class PackingInfo:
    natural_size: int
    actual_size: int
    padding_bytes: int
    suggested_pack: int
    efficiency: float
```

### Domain Layer - Repositories

**Cache Services** (src/domain/repositories/cache/)

**lru_cache.py** - Fast in-memory LRU cache
- O(1) get/put operations
- Configurable size limits
- Thread-safe

**persistent_symbol_cache.py** - Disk-based symbol cache
- Persists parsed class information
- Speeds up repeated lookups
- JSON serialization

### Infrastructure Layer

**Configuration** (src/infrastructure/config/)
- application_config.py: App settings, paths, verbose mode
- dwarf_config.py: DWARF constants, type mappings

**Logging** (src/infrastructure/logging/)
- logger_setup.py: Structured logging configuration
- progress_tracker.py: Performance tracking, operation timing

**Platform Detection** (src/infrastructure/elf_platform.py)
- ELFPlatform: Enum for PS3, PS4, UNKNOWN
- PlatformDetector: Detects platform from ELF characteristics
  - Machine type (EM_X86_64 vs EM_PPC64)
  - Endianness (little-endian vs big-endian)
  - DWARF version (DWARF3/4 vs DWARF2)
- BaseGenerator automatically detects platform and stores it
- Output files organized into platform-specific folders (output/ps4/, output/ps3/)

## Data Flow

### Single Class Generation

```text
1. DwarfGenerator.generate_header("MtObject")
2. ClassParser.find_class("MtObject")
    - Searches compilation units
    - Returns (CompileUnit, DIE)
3. ClassParser.parse_class_info(cu, die)
    - Parses members, methods, nested types
    - Captures type_offset fields via TypeChainTraverser
    - Returns ClassInfo with offsets
4. LazyTypeResolver.collect_used_typedefs(class_info)
    - Extracts types from members/methods
    - Filters internal DWARF types (class_type, void, etc.)
    - Returns typedef dict
5. HeaderGenerator.generate_single_class_header(class_info, typedefs)
    - Generates C++ code
    - Returns header string
```

### Full Hierarchy Generation (Offset-Based with Recursive Resolution)

```text
1. DwarfGenerator.generate_complete_hierarchy_header("MtPropertyList")
2. HierarchyBuilder.build_full_hierarchy_with_dependencies("MtPropertyList")
    a. build_full_hierarchy(): Discovers chain MtObject → MtPropertyList
    b. _process_dependencies_offset_based():
       - Uses DependencyExtractor.extract_dependencies()
       - Extracts type_offset from members/methods/parameters
       - Validates with DIETypeClassifier.requires_resolution()
       - Filters internal types (class_type, structure_type, void)
       - **Recursively resolves dependencies** (e.g., MtProperty → MtPropertyValue → MtType)
       - Continues until max_depth (default: 10) or no new dependencies
       - Tracks visited offsets to prevent infinite loops
       - **Result:** Full ClassInfo for ALL 74+ classes (hierarchy + dependencies)
    c. Returns {class_name: ClassInfo} dict + hierarchy order list
3. LazyTypeResolver.collect_used_typedefs(all_classes)
    - Gathers typedefs from entire hierarchy
    - Validates typedef targets (rejects *, &, [)
    - Returns filtered typedef dict
4. HeaderGenerator.generate_hierarchy_header(class_infos, order, typedefs)
    a. _collect_forward_declarations():
       - Uses type_offset fields from data models
       - Validates with DIETypeClassifier.is_forward_declarable()
       - Only forward declares class/struct/union
       - **Excludes all classes in class_infos dict** (they get full definitions)
       - Result: Minimal/zero forward declarations
    b. **Phase 1:** Generates inheritance hierarchy classes (base → derived)
    c. **Phase 2:** Generates ALL dependency classes (alphabetically)
    d. Returns complete self-contained header with 74+ full class definitions
```

**Example Output for MtObject:**
- Input: 1 class name
- Resolved: 74 classes (MtObject + 73 recursive dependencies)
- Generated: 3,605 lines with 74 full class definitions
- Forward declarations: 0 (all dependencies fully defined)
- File size: ~126 KB (complete, self-contained)

## Performance Optimizations

| Optimization | Component | Improvement |
|--------------|-----------|-------------|
| Offset-based resolution | HierarchyBuilder | Eliminates string parsing bugs, 60% code reduction |
| Typedef caching | LazyTypeResolver | 3-5x faster type resolution |
| O(1) DIE lookup | LazyDwarfIndexService | Instant type validation by offset |
| Tag classification | DIETypeClassifier | O(1) frozenset lookups vs linear search |
| Early exit search | ClassParser | 60-80% faster class discovery |
| Lazy loading | BaseGenerator | 40% memory reduction |
| LRU caching | LRUCache | O(1) lookups |
| Persistent cache | PersistentSymbolCache | Skip re-parsing across sessions |
| Internal type filtering | LazyTypeResolver | Prevents infinite search loops |
| Recursive dependency resolution | HierarchyBuilder | Complete headers with all dependencies |
| Two-phase generation | HeaderGenerator | Clear separation of hierarchy vs dependencies |

### Integration Test Results (289 symbols)

- **Success Rate:** 289/289 (100%)
- **No Hangs:** Zero infinite loops (previous bugs: class_type, void, pointer_type)
- **Clean Output:** No invalid typedefs, correct forward declarations
- **Cache Performance:** 1519 symbols cached for fast re-use
- **Complete Headers:** All dependencies fully resolved and generated
- **Multi-CU Resolution:** Successfully finds complete definitions across 2272+ compilation units
- **Timeout Protection:** No indefinite searches, all lookups complete within 180s timeout

### Multi-CU Type Resolution Performance

**Test Case: rLayout (single-file mode)**

- **Total Classes:** 285 classes resolved
- **Total Typedefs:** 52 typedefs resolved
- **Compilation Units:** 2272+ CUs searched
- **Execution Time:** 423 seconds (7 minutes)
- **Timeouts:** 0 (all types found within 180s limit)
- **Cache Hits:** 387 symbols from persistent cache

**Scoring Algorithm Efficiency:**

- **Early Exit:** Returns immediately at score >= 5000 (typedefs, base types, enums)
- **Complete Definition Priority:** Classes with members score 10000+, forward declarations score -1000
- **Type-Specific Handling:** Typedefs (5000), base types (8000), enums (6000) get appropriate scores
- **Best Match Tracking:** Searches all CUs to find highest-scored definition

**Example: cSetInfoOmTreasureBox**

- **Forward declaration:** Found at offset 0x0010fd6d (CU 0xc9d) with score -1000
- **Complete definition:** Found at offset 0x6a9a9cf (CU 0x699b890) with score 10128 (128 bytes + 10000 for members)
- **Result:** Complete definition selected and generated with proper inheritance and methods

### Offset-Based Architecture Benefits

**Before (String-Based):**

- Bug-prone string parsing (void*, MtDTI*, class_type, etc.)
- Invalid typedef generation (typedef void void*)
- Infinite search loops on internal DWARF types
- 614 lines in hierarchy_builder.py
- Forward declarations returned even when complete definitions exist

**After (Offset-Based with Multi-CU Scoring):**

- Type validation via DWARF offsets (no string parsing)
- Internal type filtering (class_type, structure_type, void)
- O(1) DIE lookups with LazyDwarfIndexService
- 243 lines in hierarchy_builder.py (60% reduction)
- Zero parsing bugs in 289-symbol integration test
- **Intelligent multi-CU search:** Finds complete definitions across all compilation units
- **Smart cache validation:** Validates cached forward declarations, searches for better matches
- **Timeout protection:** Prevents indefinite searches with configurable limits
- **Blacklist mechanism:** Skips known problematic types (pthread_mutex, FILE, etc.)

### Caching Strategy

**TypeResolver Cache:**
- Key: typedef name
- Value: resolved type string
- Hit rate: ~85% on complex hierarchies
- Lifetime: per-generation session

**Symbol Cache:**
- Key: (ELF path, class name)
- Value: serialized ClassInfo
- Storage: JSON files
- Persistence: across sessions

## PS4 ELF Compatibility

**Automatic Detection:**
- Identifies PS4 ELF by type (0xfe10) and OS/ABI (FreeBSD)
- Non-invasive: only activates on actual errors

**Fixes Applied:**
- Dynamic section sh_link=0 handling
- Unknown section type fallbacks
- String table resolution

**Implementation:** infrastructure/utils/elf_patches.py

## Error Handling

```python
class DwarfReconstructorError(Exception):
    """Base exception."""

class ELFLoadError(DwarfReconstructorError):
    """ELF loading failures."""

class ClassNotFoundError(DwarfReconstructorError):
    """Class not found in DWARF."""

class TypeResolutionError(DwarfReconstructorError):
    """Type resolution failures."""
```

**Recovery Strategies:**
- Graceful fallbacks to forward declarations
- Partial generation (log missing types)
- Context preservation for debugging
- Guaranteed cleanup via context managers

## Testing Strategy

**Unit Tests** (120 tests passing)

- Mocked DWARF structures based on actual dumps
- Fast execution (<1s)
- Component isolation
- Offset-based data models tested

```python
@pytest.mark.unit
def test_find_class_success(mocker):
    mock_die = Mock()
    mock_die.tag = "DW_TAG_class_type"
    mock_die.attributes = {'DW_AT_name': Mock(value=b'MtObject')}
    # Realistic DWARF structure from dwarfdump
```

**Integration Tests** (289-symbol validation)

- Real ELF files (DDOORBIS.elf)
- End-to-end validation
- Full hierarchy generation
- Tests: season2-resources.txt (289 symbols, 100% success rate)

```python
@pytest.mark.integration
def test_mtpropertylist_full_hierarchy():
    with DwarfGenerator(ELF_PATH) as gen:
        header = gen.generate_complete_hierarchy_header("MtPropertyList")
        assert "typedef unsigned short u16;" in header
        assert "class MtObject" in header
```

## Design Principles

**Separation of Concerns:**

- Parsing (ClassParser) separate from generation (HeaderGenerator)
- Type resolution (LazyTypeResolver) centralized
- ELF management (BaseGenerator) isolated

**Dependency Injection:**

- LazyTypeResolver injected into ClassParser
- LazyDwarfIndexService injected into HierarchyBuilder and HeaderGenerator
- All services initialized in DwarfGenerator
- Testable with mocks

**Offset-Based Type Resolution:**

- All type information tracked via DWARF offsets
- No string parsing for type validation
- O(1) DIE lookups via LazyDwarfIndexService
- Eliminates entire class of parsing bugs

**Performance First:**

- Caching at multiple levels (typedef, DIE offset, symbol)
- Lazy loading of DWARF index
- Early exit patterns
- O(1) cache lookups and tag classification

**Type Safety:**

- Full type hints on all functions
- MyPy compliance
- Dataclass models with frozen types

**Observability:**

- @log_timing decorators on major operations
- ProgressTracker for detailed metrics
- Structured logging

## Extension Points

**Custom Generators:**

- Subclass BaseGenerator
- Implement generate() method
- Reuse domain services (ClassParser, LazyTypeResolver, etc.)

**Custom Type Resolution:**

- Extend LazyTypeResolver
- Override _resolve_primitive_typedef() or collect_used_typedefs()
- Add custom type mappings or filtering

**Custom Output Formats:**

- Implement new generator service
- Use existing parsed models (ClassInfo with type_offset fields)
- Example: JSON, XML, Protobuf output

**Custom Type Validation:**

- Extend DIETypeClassifier
- Add custom tag classification logic
- Use offset-based validation patterns

## Limitations

**DWARF Support:**
- Primary: DWARF 4 (PS4)
- Limited: DWARF 5
- Requires .debug_info, .debug_abbrev sections

**C++ Features:**
- Basic template support
- Minimal namespace handling
- No concept support
- No C++20 modules

**Binary Requirements:**
- Must have debug information
- Does not work with stripped binaries
- Requires complete DWARF data

## Platform Testing

The tool has been validated on both PS3 and PS4 platforms:

### PS4 Testing (x86-64 DWARF3/4)
- **Test File:** `resources/DDOORBIS.elf`
- **Tested Classes:** MtDTI, rLayout, MtFloat3
- **Output:** Generated to `output/ps4/`
- **Status:** ✅ All tests passing

```
MtDTI:     56 bytes, 14 members, 23 methods
rLayout:  528 bytes, 12 members, 19 methods
MtFloat3:  12 bytes,  5 members, 10 methods
```

### PS3 Testing (PowerPC64 DWARF2)
- **Test File:** `resources/PS3/EBOOT.ELF`
- **Tested Classes:** MtDTI, MtUI, rLayout
- **Output:** Generated to `output/ps3/`
- **Status:** ✅ All tests passing
- **Key Validation:** Location expression parsing (DWARF2 `[DW_OP_plus_uconst, offset]` format)

```
MtDTI:   32 bytes, 10 members,  2 methods (DWARF2 encoded)
MtUI:     1 byte,   0 members,  0 methods
rLayout: 1144 bytes, 6 members,  0 methods
```

### Platform-Specific Behavior

**PS4 (DWARF3/4):**
- Member offsets as direct integers
- Standard little-endian layout
- Typical class hierarchies work directly

**PS3 (DWARF2):**
- Member offsets as location expressions `[0x23, offset]`
- Big-endian encoding affects bit packing calculations
- Successfully parsed and converted to correct offsets

## References

- [TESTING.md](TESTING.md) - Testing guide
- [REFACTORING_PLAN.md](../REFACTORING_PLAN.md) - Refactoring history
- [pyelftools documentation](https://github.com/eliben/pyelftools)
- [DWARF 4 specification](http://dwarfstd.org/)
