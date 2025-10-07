"""C++ header generator with optimized early-stopping strategy.

This module provides a single, optimized approach to generating C++ headers
from DWARF debug information. It uses early-stopping CU parsing to find
target symbols quickly, then resolves dependencies up to a configurable depth.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ..core.die_extractor import DIEExtractor
from ..core.dwarf_parser import DWARFParser

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class GenerationMode(Enum):
    """Header generation mode - optimized with early-stopping CU parsing."""

    OPTIMIZED = "optimized"  # Single optimized strategy with early-stop parsing


@dataclass
class GenerationOptions:
    """Configuration options for header generation."""

    mode: GenerationMode = GenerationMode.OPTIMIZED
    max_dependency_depth: int = 50  # Maximum depth for dependency resolution
    max_cu_parse: Optional[int] = None  # Maximum CUs to parse (None = early stop on target found)
    add_metadata: bool = True       # Include comments and metadata
    include_dependencies: bool = True  # Include base classes and dependencies


@dataclass
class ClassDefinition:
    """Unified class definition used across all generation modes."""

    name: str
    size: Optional[int] = None
    alignment: Optional[int] = None
    base_classes: List[str] = field(default_factory=list)
    members: List[Tuple[str, str, Optional[int]]] = field(default_factory=list)  # name, type, offset
    is_struct: bool = True
    source_cu_offset: Optional[int] = None  # For debugging


@dataclass
class OptimizedExtractor:
    """Cached and optimized wrapper around DIEExtractor for header generation."""

    extractor: DIEExtractor

    # Performance caches
    _class_cache: Dict[str, Tuple[Optional[any], Optional[any]]] = field(default_factory=dict)
    _type_resolution_cache: Dict[str, str] = field(default_factory=dict)

    def get_all_class_names(self) -> Set[str]:
        """Get all class/struct names using optimized type index."""
        # Use the new type_exists infrastructure for O(1) lookup
        # This triggers index building once, then all checks are O(1)
        self.extractor._build_type_indexes()
        return self.extractor._all_type_names

    def type_exists(self, type_name: str) -> bool:
        """Fast O(1) check if type exists."""
        return self.extractor.type_exists(type_name)

    def find_class_cached(self, class_name: str) -> Optional[Tuple[any, any]]:
        """Find class with caching to avoid repeated searches."""
        if class_name in self._class_cache:
            cached_result = self._class_cache[class_name]
            return cached_result if cached_result != (None, None) else None

        # Use optimized type index for faster lookup
        result = self.extractor.find_type_by_name(class_name)

        # Cache result (including negative results)
        self._class_cache[class_name] = result if result else (None, None)
        return result

    def resolve_type_name(self, type_attr_value) -> str:
        """Resolve and cache type name resolution."""
        # Handle both string and DIEReference types
        if isinstance(type_attr_value, str):
            if type_attr_value in self._type_resolution_cache:
                return self._type_resolution_cache[type_attr_value]

            # Clean up type name
            clean_type = type_attr_value.replace('class ', '').replace('struct ', '').strip()

            # Cache the result
            self._type_resolution_cache[type_attr_value] = clean_type
            return clean_type
        else:
            # For DIEReference objects, generate a unique type name
            return f"type_ref_{type_attr_value.offset:x}" if hasattr(type_attr_value, 'offset') else "unknown_type"


class HeaderGenerator:
    """C++ header generator with optimized early-stopping strategy."""

    def __init__(self, parser: DWARFParser, options: GenerationOptions = None):
        """
        Initialize the header generator.

        Args:
            parser: DWARFParser with loaded DWARF info
            options: Generation options (defaults to OPTIMIZED mode)
        """
        self.parser = parser
        self.options = options or GenerationOptions()

    def generate_header(
        self,
        symbol_name: str,
        output_path: Optional[Path] = None
    ) -> str:
        """
        Generate C++ header using optimized early-stopping strategy.

        Args:
            symbol_name: Name of class/struct to generate header for
            output_path: Optional output file path

        Returns:
            Generated header content

        Raises:
            ValueError: If symbol not found
        """
        start_time = time.time()
        logger.info("=" * 70)
        logger.info(f"Starting optimized header generation for: {symbol_name}")
        logger.info("=" * 70)

        # Use single optimized strategy with configured dependency depth
        return self._generate_optimized(
            symbol_name,
            output_path,
            depth_limit=self.options.max_dependency_depth
        )

    def _generate_optimized(
        self, symbol_name: str, output_path: Optional[Path], depth_limit: int
    ) -> str:
        """Consolidated optimized header generation strategy.

        Uses all performance optimizations:
        - Memory-limited CU parsing
        - Type-specific indexing with caching
        - Fast O(1) existence checks
        - BFS dependency resolution

        Args:
            symbol_name: Target symbol to generate header for
            output_path: Optional output file path
            depth_limit: Maximum dependency depth (0 = no deps, 3 = fast, 50 = full)

        Returns:
            Generated header content
        """
        import time

        overall_start = time.time()

        # Phase 1: Parse CUs with early stopping
        logger.info(f"[Phase 1/5] Parsing CUs with early stop for '{symbol_name}'...")
        parse_start = time.time()
        compilation_units, found_target = self.parser.parse_cus_until_target_found(
            target_symbol=symbol_name,
            max_cus=self.options.max_cu_parse
        )
        parse_time = time.time() - parse_start

        if not found_target:
            raise ValueError(f"Symbol '{symbol_name}' not found in {len(compilation_units)} CUs")

        logger.info(f"  ✓ Phase 1 complete in {parse_time:.2f}s")

        # Phase 2: Create extractor and build indexes
        logger.info("[Phase 2/5] Creating extractor with caching...")
        extractor_start = time.time()
        base_extractor = DIEExtractor(
            compilation_units, elf_file_path=getattr(self.parser, "elf_path", None)
        )
        extractor = OptimizedExtractor(extractor=base_extractor)
        extractor_time = time.time() - extractor_start
        logger.info(f"  ✓ Phase 2 complete in {extractor_time:.2f}s")

        # Phase 3: Locate target symbol (guaranteed to exist from Phase 1)
        logger.info(f"[Phase 3/5] Locating target symbol '{symbol_name}' in parsed CUs...")
        find_start = time.time()
        target_result = extractor.find_class_cached(symbol_name)
        if not target_result:
            # This should never happen since early stopping found it
            raise RuntimeError(f"Internal error: '{symbol_name}' found in Phase 1 but not in extractor")
        cu, target_die = target_result
        find_time = time.time() - find_start
        logger.info(f"  ✓ Phase 3 complete in {find_time:.3f}s")

        # Phase 4: Build type index
        logger.info("[Phase 4/5] Building type index...")
        index_start = time.time()
        all_type_names = extractor.get_all_class_names()
        index_time = time.time() - index_start
        logger.info(f"  ✓ Phase 4 complete: {len(all_type_names)} types indexed in {index_time:.3f}s")

        # Phase 5: Resolve dependencies
        logger.info(f"[Phase 5/5] Resolving dependencies (depth limit: {depth_limit})...")
        resolve_start = time.time()

        parsed_classes = {}
        classes_to_parse = [(symbol_name, 0)]  # (class_name, depth)
        visited_classes = set()

        lookup_count = 0
        hit_count = 0
        miss_count = 0

        while classes_to_parse:
            class_name, depth = classes_to_parse.pop(0)

            # Depth limiting
            if depth > depth_limit:
                continue

            if class_name in parsed_classes or class_name in visited_classes:
                continue

            # Fast O(1) existence check
            lookup_count += 1
            if not extractor.type_exists(class_name):
                visited_classes.add(class_name)
                miss_count += 1
                continue

            # Cached lookup
            result = extractor.find_class_cached(class_name)
            if not result:
                visited_classes.add(class_name)
                miss_count += 1
                continue

            hit_count += 1
            cu, die = result
            visited_classes.add(class_name)

            # Parse class
            cls = self._parse_class_from_die_optimized(die, extractor, cu.offset)
            parsed_classes[class_name] = cls

            # Add dependencies to queue
            if depth < depth_limit:
                for base in cls.base_classes:
                    if base not in visited_classes:
                        classes_to_parse.append((base, depth + 1))

        resolve_time = time.time() - resolve_start
        logger.info(
            f"  ✓ Phase 5 complete: Resolved {len(parsed_classes)} classes "
            f"in {resolve_time:.3f}s ({lookup_count} lookups: {hit_count} hits, {miss_count} misses)"
        )

        # Phase 6: Generate output
        logger.info("[Phase 6/6] Generating header content...")
        gen_start = time.time()
        ordered = self._order_classes(parsed_classes)
        header_content = self._generate_header_content(parsed_classes, ordered, symbol_name, output_path)
        gen_time = time.time() - gen_start
        logger.info(f"  ✓ Phase 6 complete in {gen_time:.3f}s ({len(header_content)} bytes)")

        total_time = time.time() - overall_start
        logger.info(
            f"\n{'='*70}\n"
            f"TOTAL TIME: {total_time:.2f}s\n"
            f"  Parse CUs:     {parse_time:6.2f}s ({parse_time/total_time*100:5.1f}%)\n"
            f"  Create index:  {extractor_time:6.2f}s ({extractor_time/total_time*100:5.1f}%)\n"
            f"  Find symbol:   {find_time:6.3f}s ({find_time/total_time*100:5.1f}%)\n"
            f"  Build index:   {index_time:6.3f}s ({index_time/total_time*100:5.1f}%)\n"
            f"  Resolve deps:  {resolve_time:6.3f}s ({resolve_time/total_time*100:5.1f}%)\n"
            f"  Generate:      {gen_time:6.3f}s ({gen_time/total_time*100:5.1f}%)\n"
            f"{'='*70}"
        )

        return header_content

    def _parse_class_from_die(self, die, cu_offset: int) -> ClassDefinition:
        """Parse a DIE into ClassDefinition (basic version)."""
        name = die.get_name() or "unknown"
        size = die.get_byte_size()
        is_struct = die.is_struct()

        cls = ClassDefinition(
            name=name,
            size=size,
            is_struct=is_struct,
            source_cu_offset=cu_offset
        )

        # Extract base classes
        for child in die.children:
            if child.tag == 'DW_TAG_inheritance':
                base_type_attr = child.get_attribute('DW_AT_type')
                if base_type_attr and isinstance(base_type_attr.value, str):
                    base_name = base_type_attr.value.replace('class ', '').replace('struct ', '').strip()
                    cls.base_classes.append(base_name)

        # Extract members
        for child in die.children:
            if child.is_member():
                member_name = child.get_name() or "unknown"
                member_type_attr = child.get_attribute('DW_AT_type')

                # Handle both string and DIEReference types
                if member_type_attr:
                    if isinstance(member_type_attr.value, str):
                        member_type = member_type_attr.value.replace('class ', '').replace('struct ', '').strip()
                    else:
                        # For DIEReference objects, use a generic type name
                        member_type = f"type_ref_{member_type_attr.value.offset:x}" if hasattr(member_type_attr.value, 'offset') else "unknown_type"
                else:
                    member_type = "void"

                offset_attr = child.get_attribute('DW_AT_data_member_location')
                offset = offset_attr.value if offset_attr else None

                cls.members.append((member_name, member_type, offset))

        return cls

    def _parse_class_from_die_optimized(self, die, extractor: OptimizedExtractor, cu_offset: int) -> ClassDefinition:
        """Parse a DIE into ClassDefinition with optimized type resolution."""
        name = die.get_name() or "unknown"
        size = die.get_byte_size()
        is_struct = die.is_struct()

        cls = ClassDefinition(
            name=name,
            size=size,
            is_struct=is_struct,
            source_cu_offset=cu_offset
        )

        # Extract base classes with optimized type resolution
        for child in die.children:
            if child.tag == 'DW_TAG_inheritance':
                base_type_attr = child.get_attribute('DW_AT_type')
                if base_type_attr and isinstance(base_type_attr.value, str):
                    base_name = extractor.resolve_type_name(base_type_attr.value)
                    cls.base_classes.append(base_name)

        # Extract members with optimized type resolution
        for child in die.children:
            if child.is_member():
                member_name = child.get_name() or "unknown"
                member_type_attr = child.get_attribute('DW_AT_type')

                if member_type_attr:
                    member_type = extractor.resolve_type_name(member_type_attr.value)
                else:
                    member_type = "void"

                offset_attr = child.get_attribute('DW_AT_data_member_location')
                offset = offset_attr.value if offset_attr else None

                cls.members.append((member_name, member_type, offset))

        return cls

    def _order_classes(self, classes: Dict[str, ClassDefinition]) -> List[str]:
        """Order classes so dependencies come first."""
        ordered = []
        visited = set()
        visiting = set()  # For cycle detection

        def visit(name: str) -> bool:
            if name in visited:
                return True
            if name in visiting:
                return False  # Cycle detected
            if name not in classes:
                return True

            visiting.add(name)

            cls = classes[name]
            for base in cls.base_classes:
                visit(base)

            visiting.remove(name)
            visited.add(name)
            ordered.append(name)
            return True

        for name in classes:
            visit(name)

        return ordered

    def _generate_header_content(
        self,
        classes: Dict[str, ClassDefinition],
        ordered: List[str],
        target_symbol: str,
        output_path: Optional[Path]
    ) -> str:
        """Generate the final header content."""
        lines = []

        # Header guard
        guard = target_symbol.upper().replace('::', '_') + "_H"
        lines.append(f"#ifndef {guard}")
        lines.append(f"#define {guard}")
        lines.append("")

        # Standard includes
        lines.append("#include <cstdint>")
        lines.append("")

        # Type aliases
        lines.append("// Game-specific type aliases")
        lines.append("typedef int8_t s8;")
        lines.append("typedef int16_t s16;")
        lines.append("typedef int32_t s32;")
        lines.append("typedef int64_t s64;")
        lines.append("typedef uint8_t u8;")
        lines.append("typedef uint16_t u16;")
        lines.append("typedef uint32_t u32;")
        lines.append("typedef uint64_t u64;")
        lines.append("")

        # Metadata
        if self.options.add_metadata:
            lines.append("// Generated from DWARF debug information")
            lines.append(f"// Target symbol: {target_symbol}")
            lines.append(f"// Generation mode: {self.options.mode.value}")
            lines.append(f"// Classes: {len(classes)}")
            lines.append("")

        # Forward declarations
        if self.options.include_dependencies:
            forward_decls = self._collect_forward_decls(classes, ordered)
            if forward_decls:
                lines.append("// Forward declarations for external types")
                for fwd in sorted(forward_decls):
                    lines.append(f"struct {fwd};")
                lines.append("")

        # Class definitions
        for class_name in ordered:
            cls = classes[class_name]
            lines.extend(self._generate_class_definition(cls))
            lines.append("")

        lines.append(f"#endif // {guard}")

        content = "\n".join(lines)

        # Write to file if requested
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding='utf-8')
            logger.info(f"✅ Wrote to: {output_path}")

        return content

    def _generate_class_definition(self, cls: ClassDefinition) -> List[str]:
        """Generate class definition lines."""
        lines = []

        if self.options.add_metadata:
            if cls.size:
                lines.append(f"// Size: {cls.size} bytes")
            if cls.alignment and cls.alignment > 1:
                lines.append(f"// Alignment: {cls.alignment} bytes")
            if cls.source_cu_offset:
                lines.append(f"// Source CU: 0x{cls.source_cu_offset:08x}")

        keyword = "struct" if cls.is_struct else "class"
        align_attr = f" __attribute__((aligned({cls.alignment})))" if cls.alignment and cls.alignment > 1 else ""

        if cls.base_classes and self.options.include_dependencies:
            bases = " : " + ", ".join(f"public {base}" for base in cls.base_classes)
        else:
            bases = ""

        lines.append(f"{keyword}{align_attr} {cls.name}{bases}")
        lines.append("{")

        if cls.members:
            for member_name, member_type, offset in cls.members:
                if self.options.add_metadata and offset is not None:
                    lines.append(f"    // offset: {offset:#x}")
                lines.append(f"    {member_type} {member_name};")
        else:
            if self.options.add_metadata:
                lines.append("    // No members found in DWARF")

        lines.append("};")

        return lines

    def _collect_forward_decls(self, classes: Dict[str, ClassDefinition], ordered: List[str]) -> Set[str]:
        """Collect types that need forward declarations."""
        forward_decls = set()
        known_types = set(classes.keys())

        primitives = {
            'void', 'bool', 'char', 'short', 'int', 'long', 'float', 'double',
            's8', 's16', 's32', 's64', 'u8', 'u16', 'u32', 'u64',
            'int8_t', 'int16_t', 'int32_t', 'int64_t',
            'uint8_t', 'uint16_t', 'uint32_t', 'uint64_t',
        }

        for class_name in ordered:
            cls = classes[class_name]
            for _, member_type, _ in cls.members:
                base_type = member_type.replace('*', '').replace('&', '').replace('const', '').replace('volatile', '').strip()

                if (base_type and
                    base_type not in known_types and
                    base_type not in primitives and
                    base_type[0].isupper()):
                    forward_decls.add(base_type)

        return forward_decls


def generate_header(
    parser: DWARFParser,
    symbol_name: str,
    output_path: Optional[Path] = None,
    add_metadata: bool = True,
    max_dependency_depth: int = 50
) -> str:
    """
    Generate C++ header with optimized early-stopping strategy.

    Uses early-stop CU parsing to find the target symbol quickly,
    then resolves dependencies up to the specified depth.

    Args:
        parser: DWARFParser with loaded DWARF info
        symbol_name: Name of class/struct to generate header for
        output_path: Optional output file path
        add_metadata: Include metadata comments in header
        max_dependency_depth: Maximum depth for dependency resolution

    Returns:
        Generated header content as string

    Raises:
        ValueError: If symbol not found
    """
    options = GenerationOptions(
        mode=GenerationMode.OPTIMIZED,
        max_dependency_depth=max_dependency_depth,
        add_metadata=add_metadata,
        max_cu_parse=None  # Use early stopping
    )
    generator = HeaderGenerator(parser, options)
    return generator.generate_header(symbol_name, output_path)
