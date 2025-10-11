#!/usr/bin/env python3

"""DWARF-to-C++ header generator orchestrator (Application Layer).

This is the main generator that orchestrates the modular components:
- TypeResolver: Type resolution and typedef handling
- ClassParser: DWARF class parsing
- HeaderGenerator: C++ header generation
- HierarchyBuilder: Inheritance hierarchy management
- PackingAnalyzer: Struct packing analysis
"""

from pathlib import Path
from time import time
from typing import TYPE_CHECKING

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE

from ...domain.models.dwarf import ClassInfo
from ...domain.services.generation import HeaderGenerator, HierarchyBuilder
from ...domain.services.parsing import ClassParser
from ...generators.base_generator import BaseGenerator
from ...generators.utils.packing_analyzer import calculate_packing_info
from ...infrastructure.logging import get_logger, log_timing

if TYPE_CHECKING:
    from ...core.lazy_type_resolver import LazyTypeResolver
    from ...domain.services.lazy_dwarf_index_service import LazyDwarfIndexService

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
        """Initialize generator with ELF file path using lazy loading.

        Args:
            elf_path: Path to ELF file containing DWARF information
        """
        super().__init__(elf_path)
        self.type_resolver: LazyTypeResolver | None = None
        self.class_parser: ClassParser | None = None
        self.header_generator: HeaderGenerator | None = None
        self.lazy_index: LazyDwarfIndexService | None = None
        self.hierarchy_builder: HierarchyBuilder | None = None

    def __enter__(self) -> "DwarfGenerator":
        """Context manager entry - initializes all modules."""
        super().__enter__()

        # Initialize modules (dwarf_info is guaranteed non-None after __enter__)
        initialization_start = time()
        assert self.dwarf_info is not None

        # Initialize components with lazy loading (only approach)
        self._initialize_components()

        total_elapsed = time() - initialization_start
        logger.info(f"DwarfGenerator initialized with modular architecture in {total_elapsed:.3f}s")
        return self

    def __exit__(
        self, exc_type: type | None, exc_val: Exception | None, exc_tb: object | None
    ) -> None:
        """Context manager exit - saves cache and closes resources."""
        # Save cache before parent cleanup
        if self.lazy_index is not None:
            logger.debug("Saving DWARF cache to disk")
            self.lazy_index.save_cache()
            logger.info("DWARF cache saved successfully")

        # Call parent cleanup
        super().__exit__(exc_type, exc_val, exc_tb)

    def _initialize_components(self) -> None:
        """Initialize components with lazy loading and memory monitoring."""
        from ...core.lazy_type_resolver import LazyTypeResolver
        from ...domain.services.lazy_dwarf_index_service import LazyDwarfIndexService
        from ...domain.services.parsing import ClassParser
        from ...infrastructure.config import get_cache_file_path, get_config

        assert self.dwarf_info is not None, "dwarf_info must be initialized"
        config = get_config()
        cache_file = get_cache_file_path(str(self.elf_path))

        # Initialize lazy index
        lazy_start = time()
        self.lazy_index = LazyDwarfIndexService(
            self.dwarf_info, str(cache_file), die_cache_size=config["DIE_CACHE_SIZE"]
        )
        lazy_elapsed = time() - lazy_start
        logger.debug(f"LazyDwarfIndex initialization: {lazy_elapsed:.3f}s")

        # Initialize lazy type resolver (the only type resolver now)
        resolver_start = time()
        self.type_resolver = LazyTypeResolver(self.dwarf_info, self.lazy_index)
        resolver_elapsed = time() - resolver_start
        logger.debug(f"LazyTypeResolver initialization: {resolver_elapsed:.3f}s")

        # Initialize class parser with lazy index
        parser_start = time()
        self.class_parser = ClassParser(self.type_resolver, self.dwarf_info, self.lazy_index)
        parser_elapsed = time() - parser_start
        logger.debug(f"ClassParser with lazy loading initialization: {parser_elapsed:.3f}s")

        # Initialize header generator with DWARF index
        header_start = time()
        self.header_generator = HeaderGenerator(self.lazy_index)
        header_elapsed = time() - header_start
        logger.debug(f"HeaderGenerator initialization: {header_elapsed:.3f}s")

        # Initialize hierarchy builder
        hierarchy_start = time()
        self.hierarchy_builder = HierarchyBuilder(self.class_parser, self.lazy_index)
        hierarchy_elapsed = time() - hierarchy_start
        logger.debug(f"HierarchyBuilder initialization: {hierarchy_elapsed:.3f}s")

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

    def is_namespace(self, die: DIE) -> bool:
        """Check if a DIE represents a namespace.

        Args:
            die: DIE to check

        Returns:
            True if DIE is a namespace, False otherwise
        """
        return die.tag == "DW_TAG_namespace"

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
        """Generate C++ header for a single class or namespace.

        Args:
            class_name: Name of the class/namespace to generate header for
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

        # Check if this is a namespace
        if self.is_namespace(class_die):
            logger.info(f"{class_name} is a namespace, generating namespace header")
            return self._generate_namespace_header(class_name, cu, class_die)

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
            class_info.unions,
            class_info.nested_structs,
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

        # Build full hierarchy with dependencies (timing included)
        hierarchy_start = time()
        assert self.hierarchy_builder is not None
        class_infos, hierarchy_order = self.hierarchy_builder.build_full_hierarchy_with_dependencies(
            class_name, max_depth=10
        )
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
                class_info.unions,
                class_info.nested_structs,
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

    def _generate_namespace_header(
        self, namespace_name: str, cu: CompileUnit, namespace_die: DIE
    ) -> str:
        """Generate header for a namespace with proper C++ namespace syntax.

        Args:
            namespace_name: Name of the namespace
            cu: Compilation unit containing the namespace
            namespace_die: DIE representing the namespace

        Returns:
            C++ header documenting the namespace with forward declarations
        """
        from ...utils.path_utils import sanitize_for_filesystem

        # Collect child classes and their types
        child_items = []
        try:
            for child in namespace_die.iter_children():  # type: ignore
                if child.tag in ("DW_TAG_class_type", "DW_TAG_structure_type"):
                    name_attr = child.attributes.get("DW_AT_name")
                    if name_attr:
                        if isinstance(name_attr.value, bytes):
                            class_name = name_attr.value.decode("utf-8")
                        else:
                            class_name = str(name_attr.value)

                        # Determine if it's a class or struct
                        item_type = "class" if child.tag == "DW_TAG_class_type" else "struct"
                        child_items.append((item_type, class_name))
        except Exception as e:
            logger.warning(f"Error iterating namespace children: {e}")

        child_items.sort(key=lambda x: x[1])  # Sort by name

        # Generate header
        sanitized_name = sanitize_for_filesystem(namespace_name).upper()
        lines = [
            f"#ifndef {sanitized_name}_NAMESPACE_H",
            f"#define {sanitized_name}_NAMESPACE_H",
            "",
            "#include <cstdint>",
            "",
            "// Generated from DWARF debug information using pyelftools",
            f"// Target namespace: {namespace_name}",
            "",
            "// DWARF Debug Information:",
            f"// - DIE Offset: 0x{namespace_die.offset:08x}",
            f"// - Source CU: 0x{cu.cu_offset:08x}",
        ]

        # Add source file info if available
        decl_file = namespace_die.attributes.get("DW_AT_decl_file")
        decl_line = namespace_die.attributes.get("DW_AT_decl_line")
        if decl_file and decl_line:
            lines.append(f"// - Declaration: {decl_file.value}")
            lines.append(f"//   Line: {decl_line.value}")

        lines.extend(
            [
                "",
                f"// Namespace: {namespace_name}",
                f"// Contains {len(child_items)} type(s)",
                "",
            ]
        )

        # Generate C++ namespace with forward declarations
        lines.append(f"namespace {namespace_name} {{")
        lines.append("")

        if child_items:
            lines.append("// Forward declarations")
            for item_type, class_name in child_items:
                lines.append(f"{item_type} {class_name};")
            lines.append("")
            lines.append("// To generate full headers for these classes, use:")
            for _, class_name in child_items:
                lines.append(f"//   --generate {namespace_name}::{class_name}")
        else:
            lines.append("// No classes found in this namespace")

        lines.extend(
            [
                "",
                f"}}  // namespace {namespace_name}",
                "",
                f"#endif // {sanitized_name}_NAMESPACE_H",
                "",
            ]
        )

        return "\n".join(lines)
