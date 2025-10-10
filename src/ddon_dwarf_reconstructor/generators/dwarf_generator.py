#!/usr/bin/env python3

"""Refactored DWARF-to-C++ header generator using modular architecture.

This is the main generator that orchestrates the modular components:
- TypeResolver: Type resolution and typedef handling
- ClassParser: DWARF class parsing
- HeaderGenerator: C++ header generation
- HierarchyBuilder: Inheritance hierarchy management
- PackingAnalyzer: Struct packing analysis
"""

from pathlib import Path

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE

from ..models import ClassInfo
from ..utils.logger import get_logger, log_timing
from time import time
from .base_generator import BaseGenerator
from .class_parser import ClassParser
from .header_generator import HeaderGenerator
from .hierarchy_builder import HierarchyBuilder
from .type_resolver import TypeResolver
from .utils.packing_analyzer import calculate_packing_info

logger = get_logger(__name__)


class DwarfGenerator(BaseGenerator):
    """DWARF-to-C++ header generator using modular architecture.

    This refactored implementation delegates responsibilities to specialized modules:
    - Parsing is handled by ClassParser
    - Type resolution by TypeResolver
    - Header generation by HeaderGenerator
    - Hierarchy management by HierarchyBuilder
    """

    def __init__(self, elf_path: Path):
        """Initialize generator with ELF file path.

        Args:
            elf_path: Path to ELF file containing DWARF information
        """
        super().__init__(elf_path)
        self.type_resolver: TypeResolver | None = None
        self.class_parser: ClassParser | None = None
        self.header_generator: HeaderGenerator | None = None
        self.hierarchy_builder: HierarchyBuilder | None = None

    def __enter__(self) -> "DwarfGenerator":
        """Context manager entry - initializes all modules."""
        super().__enter__()

        # Initialize modules (dwarf_info is guaranteed non-None after __enter__)
        initialization_start = time()
        assert self.dwarf_info is not None
        
        # Initialize components with timing
        resolver_start = time()
        self.type_resolver = TypeResolver(self.dwarf_info)
        resolver_elapsed = time() - resolver_start
        logger.debug(f"TypeResolver initialization: {resolver_elapsed:.3f}s")
        
        parser_start = time()
        self.class_parser = ClassParser(self.type_resolver, self.dwarf_info)
        parser_elapsed = time() - parser_start
        logger.debug(f"ClassParser initialization: {parser_elapsed:.3f}s")
        
        header_start = time()
        self.header_generator = HeaderGenerator()
        header_elapsed = time() - header_start
        logger.debug(f"HeaderGenerator initialization: {header_elapsed:.3f}s")
        
        hierarchy_start = time()
        self.hierarchy_builder = HierarchyBuilder(self.class_parser)
        hierarchy_elapsed = time() - hierarchy_start
        logger.debug(f"HierarchyBuilder initialization: {hierarchy_elapsed:.3f}s")

        total_elapsed = time() - initialization_start
        logger.info(f"DwarfGenerator initialized with modular architecture in {total_elapsed:.3f}s")
        return self

    def generate(self, symbol: str, **options: bool) -> str:
        """Generate C++ header for the specified symbol.

        Args:
            symbol: Target symbol name to generate header for
            **options: Generation options
                - full_hierarchy (bool): Generate complete inheritance hierarchy
                - no_metadata (bool): Skip DWARF metadata comments

        Returns:
            Generated C++ header as string
        """
        full_hierarchy = options.get("full_hierarchy", False)
        no_metadata = options.get("no_metadata", False)

        if full_hierarchy:
            return self.generate_complete_hierarchy_header(symbol, not no_metadata)
        else:
            return self.generate_header(symbol, not no_metadata)

    def find_class(self, class_name: str) -> tuple[CompileUnit, DIE] | None:
        """Find a class/type DIE by name.

        Delegates to ClassParser for the search.

        Args:
            class_name: Name of the class to find

        Returns:
            Tuple of (CompileUnit, DIE) if found, None otherwise
        """
        assert self.class_parser is not None
        return self.class_parser.find_class(class_name)

    def parse_class_info(self, cu: CompileUnit, class_die: DIE) -> ClassInfo:
        """Parse class information from DIE.

        Delegates to ClassParser and adds packing analysis.

        Args:
            cu: Compilation unit containing the class
            class_die: DIE representing the class

        Returns:
            ClassInfo object with complete information including packing
        """
        assert self.class_parser is not None
        class_info = self.class_parser.parse_class_info(cu, class_die)

        # Add packing information
        class_info.packing_info = calculate_packing_info(class_info)

        return class_info

    @log_timing
    def generate_header(self, class_name: str, include_metadata: bool = True) -> str:
        """Generate C++ header for a single class.

        Args:
            class_name: Name of the class to generate header for
            include_metadata: Whether to include DWARF metadata comments

        Returns:
            Complete C++ header file as string
        """
        logger.info(f"Generating header for: {class_name}")

        # Find class with timing
        find_start = time()
        result = self.find_class(class_name)
        find_elapsed = time() - find_start
        logger.debug(f"Class search completed in {find_elapsed:.3f}s")
        
        if not result:
            logger.warning(f"Class {class_name} not found")
            return self._generate_not_found_header(class_name)

        cu, class_die = result

        # Parse class with timing
        parse_start = time()
        class_info = self.parse_class_info(cu, class_die)
        parse_elapsed = time() - parse_start
        logger.debug(f"Class parsing completed in {parse_elapsed:.3f}s")
        
        logger.info(
            f"Parsed {class_name}: {class_info.byte_size} bytes, "
            f"{len(class_info.members)} members, {len(class_info.methods)} methods",
        )

        # Collect used typedefs with timing
        typedef_start = time()
        assert self.type_resolver is not None
        typedefs = self.type_resolver.collect_used_typedefs(
            class_info.members,
            class_info.methods,
        )
        typedef_elapsed = time() - typedef_start
        logger.debug(f"Collected {len(typedefs)} typedefs in {typedef_elapsed:.3f}s")

        # Generate header with timing
        header_start = time()
        assert self.header_generator is not None
        header = self.header_generator.generate_header(
            class_info,
            typedefs=typedefs,
            cu_offset=cu.cu_offset,
            include_metadata=include_metadata,
        )
        header_elapsed = time() - header_start
        logger.debug(f"Header generation completed in {header_elapsed:.3f}s")

        logger.info(f"Header generated successfully for {class_name}")
        return header

    @log_timing
    def generate_complete_hierarchy_header(
        self,
        class_name: str,
        include_metadata: bool = True,
    ) -> str:
        """Generate C++ header with complete inheritance hierarchy.

        This method generates headers for the entire inheritance chain,
        from base class to derived class, with proper ordering.

        Args:
            class_name: Name of the target class
            include_metadata: Whether to include DWARF metadata comments

        Returns:
            Complete C++ header file with full hierarchy
        """
        logger.info(f"Generating complete hierarchy header for: {class_name}")

        # Expand typedef search for full hierarchy mode
        typedef_expand_start = time()
        assert self.type_resolver is not None
        self.type_resolver.expand_primitive_search(full_hierarchy=True)
        typedef_expand_elapsed = time() - typedef_expand_start
        logger.debug(f"Typedef search expansion completed in {typedef_expand_elapsed:.3f}s")

        # Build full hierarchy with timing
        hierarchy_start = time()
        assert self.hierarchy_builder is not None
        class_infos, hierarchy_order = self.hierarchy_builder.build_full_hierarchy(class_name)
        hierarchy_elapsed = time() - hierarchy_start
        logger.debug(f"Hierarchy building completed in {hierarchy_elapsed:.3f}s")

        if not class_infos:
            logger.warning(f"No classes found in hierarchy for {class_name}")
            return self._generate_not_found_header(class_name)

        # Add packing info and collect typedefs from all classes with timing
        packing_start = time()
        all_typedefs: dict[str, str] = {}
        for _cls_name, class_info in class_infos.items():
            if class_info.packing_info is None:
                class_info.packing_info = calculate_packing_info(class_info)

            # Collect typedefs for this class
            class_typedefs = self.type_resolver.collect_used_typedefs(
                class_info.members,
                class_info.methods,
            )
            all_typedefs.update(class_typedefs)
        
        packing_elapsed = time() - packing_start
        logger.debug(f"Packing analysis and typedef collection completed in {packing_elapsed:.3f}s")

        logger.info(
            f"Hierarchy complete: {len(class_infos)} classes in order: "
            f"{' -> '.join(hierarchy_order)}, collected {len(all_typedefs)} typedefs",
        )

        # Generate hierarchy header with timing
        header_gen_start = time()
        assert self.header_generator is not None
        header = self.header_generator.generate_hierarchy_header(
            class_infos,
            hierarchy_order,
            class_name,
            typedefs=all_typedefs,
            include_metadata=include_metadata,
        )
        header_gen_elapsed = time() - header_gen_start
        logger.debug(f"Hierarchy header generation completed in {header_gen_elapsed:.3f}s")

        logger.info(f"Hierarchy header generated successfully for {class_name}")
        return header

    def build_inheritance_hierarchy(self, class_name: str) -> list[str]:
        """Build inheritance chain for a class.

        Args:
            class_name: Name of the class

        Returns:
            List of base class names from root to derived
        """
        assert self.hierarchy_builder is not None
        return self.hierarchy_builder.build_hierarchy_chain(class_name)

    def _generate_not_found_header(self, class_name: str) -> str:
        """Generate placeholder header when class is not found.

        Args:
            class_name: Name of the class that wasn't found

        Returns:
            Placeholder C++ header
        """
        return f"""#ifndef {class_name.upper()}_H
#define {class_name.upper()}_H

// Class '{class_name}' not found in DWARF information
// Generated from DWARF debug information using pyelftools

#endif // {class_name.upper()}_H
"""
