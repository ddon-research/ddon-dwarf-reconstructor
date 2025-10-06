"""Consolidated C++ header generator with multiple generation strategies.

This module replaces the previous scattered header generation files:
- logged_header_gen.py
- fast_header_gen.py  
- ultra_fast_header_gen.py
- simple_header_gen.py
- header_generator.py

It provides a unified interface with different generation modes for performance optimization.
"""

import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Set, Tuple, Generator
from dataclasses import dataclass, field
from enum import Enum

from ..core.dwarf_parser import DWARFParser
from ..core.die_extractor import DIEExtractor


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class GenerationMode(Enum):
    """Header generation modes with different performance characteristics."""
    
    ULTRA_FAST = "ultra_fast"      # Scan only first few CUs (1-5 seconds)
    FAST = "fast"                  # Limited dependency resolution (5-30 seconds)
    FULL = "full"                  # Complete dependency tree (30 seconds - few minutes)
    SIMPLE = "simple"              # Basic single-class generation (1-10 seconds)


@dataclass
class GenerationOptions:
    """Configuration options for header generation."""
    
    mode: GenerationMode = GenerationMode.FAST
    max_classes: int = 10          # For FAST mode
    max_dependency_depth: int = 50  # For FULL mode
    max_cu_scan: int = 10          # For ULTRA_FAST mode
    add_metadata: bool = True      # Include comments and metadata
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
    _all_class_names: Optional[Set[str]] = None
    _type_resolution_cache: Dict[str, str] = field(default_factory=dict)
    
    def get_all_class_names(self) -> Set[str]:
        """Get all class/struct names with caching."""
        if self._all_class_names is None:
            logger.info("  Building class name cache...")
            start_time = time.time()
            
            self._all_class_names = set()
            for cu in self.extractor.compilation_units:
                for die in cu.dies:
                    if die.is_class() or die.is_struct():
                        name = die.get_name()
                        if name:
                            self._all_class_names.add(name)
            
            build_time = time.time() - start_time
            logger.info(f"  ✓ Built class name cache: {len(self._all_class_names)} classes in {build_time:.2f}s")
        
        return self._all_class_names
    
    def find_class_cached(self, class_name: str) -> Optional[Tuple[any, any]]:
        """Find class with caching to avoid repeated searches."""
        if class_name in self._class_cache:
            cached_result = self._class_cache[class_name]
            return cached_result if cached_result != (None, None) else None
        
        # Search for class
        result = self.extractor.find_class_by_name(class_name)
        if not result:
            result = self.extractor.find_struct_by_name(class_name)
        
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
    """Unified C++ header generator with multiple generation strategies."""

    def __init__(self, parser: DWARFParser, options: GenerationOptions = None):
        """
        Initialize the header generator.
        
        Args:
            parser: DWARFParser with loaded DWARF info
            options: Generation options (defaults to FAST mode)
        """
        self.parser = parser
        self.options = options or GenerationOptions()
        
    def generate_header(
        self, 
        symbol_name: str, 
        output_path: Optional[Path] = None
    ) -> str:
        """
        Generate C++ header using the configured generation mode.
        
        Args:
            symbol_name: Name of class/struct to generate header for
            output_path: Optional output file path
            
        Returns:
            Generated header content
            
        Raises:
            ValueError: If symbol not found
        """
        start_time = time.time()
        mode_name = self.options.mode.value.replace('_', '-')
        logger.info(f"=" * 70)
        logger.info(f"Starting {mode_name} header generation for: {symbol_name}")
        logger.info(f"=" * 70)
        
        if self.options.mode == GenerationMode.ULTRA_FAST:
            return self._generate_ultra_fast(symbol_name, output_path)
        elif self.options.mode == GenerationMode.FAST:
            return self._generate_fast(symbol_name, output_path)
        elif self.options.mode == GenerationMode.FULL:
            return self._generate_full(symbol_name, output_path)
        elif self.options.mode == GenerationMode.SIMPLE:
            return self._generate_simple(symbol_name, output_path)
        else:
            raise ValueError(f"Unknown generation mode: {self.options.mode}")
    
    def _generate_ultra_fast(self, symbol_name: str, output_path: Optional[Path]) -> str:
        """Generate header by scanning only first few compilation units."""
        # Find target symbol in first few CUs
        found_target = False
        target_die = None
        scanned_cus = []
        
        cu_count = 0
        for cu in self.parser.iter_compilation_units():
            cu_count += 1
            if cu_count > self.options.max_cu_scan:
                break
                
            logger.info(f"  Scanning CU #{cu_count} (offset: 0x{cu.offset:08x}, {len(cu.dies)} DIEs)")
            scanned_cus.append(cu)
            
            # Quick scan for target symbol
            for die in cu.dies:
                if (die.is_class() or die.is_struct()) and die.get_name() == symbol_name:
                    found_target = True
                    target_die = die
                    logger.info(f"  ✅ Found '{symbol_name}' in CU #{cu_count}!")
                    break
                    
            if found_target:
                break
        
        if not found_target:
            raise ValueError(f"Symbol '{symbol_name}' not found in first {cu_count} compilation units")

        # Parse target class only
        target_class = self._parse_class_from_die(target_die, cu.offset)
        classes = {symbol_name: target_class}
        
        logger.info(f"✅ Parsed target: {symbol_name} ({len(target_class.members)} members)")
        
        return self._generate_header_content(classes, [symbol_name], symbol_name, output_path)
    
    def _generate_fast(self, symbol_name: str, output_path: Optional[Path]) -> str:
        """Generate header with limited dependency resolution."""
        compilation_units = self.parser.parse_all_compilation_units()
        extractor = DIEExtractor(compilation_units)
        
        # Find target class
        result = extractor.find_class_by_name(symbol_name)
        if not result:
            result = extractor.find_struct_by_name(symbol_name)
        if not result:
            raise ValueError(f"Symbol '{symbol_name}' not found")
            
        cu, target_die = result
        
        # Limited dependency resolution
        parsed_classes = {}
        classes_to_process = [symbol_name]
        processed_count = 0

        while classes_to_process and processed_count < self.options.max_classes:
            class_name = classes_to_process.pop(0)
            
            if class_name in parsed_classes:
                continue
                
            class_result = extractor.find_class_by_name(class_name)
            if not class_result:
                class_result = extractor.find_struct_by_name(class_name)
            if not class_result:
                continue
                
            _, die = class_result
            processed_count += 1
            
            cls = self._parse_class_from_die(die, cu.offset)
            parsed_classes[class_name] = cls
            
            # Add base classes to queue (limited)
            for base in cls.base_classes:
                if (processed_count < self.options.max_classes and 
                    base not in classes_to_process and 
                    base not in parsed_classes):
                    classes_to_process.append(base)
        
        ordered = self._order_classes(parsed_classes)
        return self._generate_header_content(parsed_classes, ordered, symbol_name, output_path)
    
    def _generate_full(self, symbol_name: str, output_path: Optional[Path]) -> str:
        """Generate header with complete dependency resolution."""
        compilation_units = self.parser.parse_all_compilation_units()
        base_extractor = DIEExtractor(compilation_units)
        extractor = OptimizedExtractor(extractor=base_extractor)
        
        # Find target class
        target_result = extractor.find_class_cached(symbol_name)
        if not target_result:
            raise ValueError(f"Symbol '{symbol_name}' not found")

        cu, target_die = target_result
        
        # Full dependency resolution with optimizations
        parsed_classes = {}
        classes_to_parse = [(symbol_name, 0)]  # (class_name, depth)
        visited_classes = set()
        all_class_names = extractor.get_all_class_names()

        while classes_to_parse:
            class_name, depth = classes_to_parse.pop(0)

            # Depth limiting
            if depth > self.options.max_dependency_depth:
                continue

            if class_name in parsed_classes or class_name in visited_classes:
                continue

            if class_name not in all_class_names:
                visited_classes.add(class_name)
                continue

            result = extractor.find_class_cached(class_name)
            if not result:
                visited_classes.add(class_name)
                continue

            cu, die = result
            visited_classes.add(class_name)
            
            cls = self._parse_class_from_die_optimized(die, extractor, cu.offset)
            parsed_classes[class_name] = cls

            # Add dependencies
            for base in cls.base_classes:
                if base not in visited_classes:
                    classes_to_parse.append((base, depth + 1))

        ordered = self._order_classes(parsed_classes)
        return self._generate_header_content(parsed_classes, ordered, symbol_name, output_path)
    
    def _generate_simple(self, symbol_name: str, output_path: Optional[Path]) -> str:
        """Generate header for single class without dependencies."""
        compilation_units = self.parser.parse_all_compilation_units()
        extractor = DIEExtractor(compilation_units)
        
        # Find target class only
        result = extractor.find_class_by_name(symbol_name)
        if not result:
            result = extractor.find_struct_by_name(symbol_name)
        if not result:
            raise ValueError(f"Symbol '{symbol_name}' not found")
            
        cu, target_die = result
        target_class = self._parse_class_from_die(target_die, cu.offset)
        
        classes = {symbol_name: target_class}
        return self._generate_header_content(classes, [symbol_name], symbol_name, output_path)
    
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
            lines.append(f"// Generated from DWARF debug information")
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


# Convenience functions for backward compatibility
def generate_header_with_logging(
    parser: DWARFParser,
    symbol_name: str,
    output_path: Optional[Path] = None,
    add_metadata: bool = True,
    max_dependency_depth: int = 50
) -> str:
    """Generate header with full dependency resolution (backward compatibility)."""
    options = GenerationOptions(
        mode=GenerationMode.FULL,
        max_dependency_depth=max_dependency_depth,
        add_metadata=add_metadata
    )
    generator = HeaderGenerator(parser, options)
    return generator.generate_header(symbol_name, output_path)


def generate_fast_header(
    parser: DWARFParser,
    symbol_name: str,
    output_path: Optional[Path] = None,
    max_classes: int = 10
) -> str:
    """Generate header with limited dependencies (backward compatibility)."""
    options = GenerationOptions(
        mode=GenerationMode.FAST,
        max_classes=max_classes
    )
    generator = HeaderGenerator(parser, options)
    return generator.generate_header(symbol_name, output_path)


def generate_ultra_fast_header(
    parser: DWARFParser,
    symbol_name: str,
    output_path: Optional[Path] = None,
    max_cu_scan: int = 10
) -> str:
    """Generate header by scanning only first few CUs (backward compatibility)."""
    options = GenerationOptions(
        mode=GenerationMode.ULTRA_FAST,
        max_cu_scan=max_cu_scan
    )
    generator = HeaderGenerator(parser, options)
    return generator.generate_header(symbol_name, output_path)
