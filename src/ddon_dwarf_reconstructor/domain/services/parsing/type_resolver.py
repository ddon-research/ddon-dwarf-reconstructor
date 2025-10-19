#!/usr/bin/env python3

"""Type resolution and typedef handling for DWARF parsing - ENHANCED VERSION.

This module provides type resolution logic for DWARF DIEs, handling:
- ALL typedefs (not just primitives)
- Recursive typedef chains
- Type qualifiers (const, pointer, reference)
- Comprehensive caching for performance optimization
"""

from time import time
from typing import TYPE_CHECKING

from elftools.dwarf.die import DIE
from elftools.dwarf.dwarfinfo import DWARFInfo

if TYPE_CHECKING:
    from ...models.dwarf import MemberInfo, MethodInfo, StructInfo, UnionInfo

from ....infrastructure.logging import get_logger, log_timing

logger = get_logger(__name__)


class TypeResolver:
    """Handles all type resolution logic for DWARF parsing.

    This class resolves type names from DWARF DIEs, following reference chains,
    resolving typedefs, and applying type qualifiers. Includes comprehensive caching for
    performance optimization.

    Attributes:
        dwarf_info: DWARF information structure from pyelftools
        _typedef_cache: Cache of resolved typedefs for performance
        _all_typedefs: Complete map of all typedefs in the binary
        _typedef_chains: Cache of recursive typedef resolutions
    """

    # Common primitive typedefs for quick lookup
    PRIMITIVE_TYPEDEFS = frozenset(
        {
            "u8",
            "u16",
            "u32",
            "u64",
            "s8",
            "s16",
            "s32",
            "s64",
            "f32",
            "f64",
            "size_t",
            "ssize_t",
            "uint_fast8_t",
            "int_fast8_t",
            "uint_fast16_t",
            "int_fast16_t",
            "uint_fast32_t",
            "int_fast32_t",
            "uint_fast64_t",
            "int_fast64_t",
            # Platform-specific types
            "uint8_t",
            "int8_t",
            "uint16_t",
            "int16_t",
            "uint32_t",
            "int32_t",
            "uint64_t",
            "int64_t",
            "uintptr_t",
            "intptr_t",
            "__uint64_t",
            "__int64_t",
            "__uint32_t",
            "__int32_t",
            "__uint16_t",
            "__int16_t",
            "__uint8_t",
            "__int8_t",
        }
    )

    def __init__(self, dwarf_info: DWARFInfo):
        """Initialize type resolver with DWARF information.

        Args:
            dwarf_info: DWARF information structure from pyelftools
        """
        self.dwarf_info = dwarf_info
        self._typedef_cache: dict[str, tuple[str, str] | None] = {}
        self._all_typedefs: dict[str, str] | None = None  # Lazy loaded
        self._typedef_chains: dict[str, str] = {}  # Recursive resolution cache
        self._types_in_progress: set[str] = set()  # Prevent infinite recursion
        # Add instance attribute for test compatibility
        self._primitive_typedefs: set[str] = set(self.PRIMITIVE_TYPEDEFS)

    def expand_primitive_search(self, full_hierarchy: bool = False) -> None:
        """Expand the set of primitive types to search for.

        Args:
            full_hierarchy: If True, include additional platform-specific types
        """
        if full_hierarchy:
            # Add additional platform-specific types for full hierarchy mode
            additional_types = {
                "ptrdiff_t",
                "wchar_t",
                "char16_t",
                "char32_t",
                "long long",
                "unsigned long long",
                "long double",
                "bool",
                "char",
                "wchar",
                "std::size_t",
                "std::ptrdiff_t",
            }
            self._primitive_typedefs.update(additional_types)

    def resolve_type_name(self, die: DIE, type_attr_name: str = "DW_AT_type") -> str:
        """Resolve type name using pyelftools DIE reference resolution.

        Recursively resolves type references, handling type modifiers like
        pointers, const, references, and arrays.

        Args:
            die: DIE to resolve type from
            type_attr_name: Attribute name containing type reference (default: DW_AT_type)

        Returns:
            Resolved type name as string, or "void"/"unknown_type" if not resolvable
        """
        try:
            # Check if the DIE has the type attribute
            if type_attr_name not in die.attributes:
                logger.debug(f"DIE {die.tag} has no {type_attr_name} attribute")
                return "void"  # Methods without return type are void

            # Use pyelftools' method to resolve DIE reference
            type_die = die.get_DIE_from_attribute(type_attr_name)
            if not type_die:
                logger.debug(f"Could not resolve {type_attr_name} reference")
                return "unknown_type"

            # Get the type name
            name_attr = type_die.attributes.get("DW_AT_name")
            if name_attr:
                if isinstance(name_attr.value, bytes):
                    return name_attr.value.decode("utf-8")
                return str(name_attr.value)

            # Handle different type tags
            if type_die.tag == "DW_TAG_pointer_type":
                # Recurse to get pointed-to type
                pointed_type = self.resolve_type_name(type_die)
                return f"{pointed_type}*" if pointed_type != "unknown_type" else "void*"

            if type_die.tag == "DW_TAG_const_type":
                base_type = self.resolve_type_name(type_die)
                return f"const {base_type}"

            if type_die.tag == "DW_TAG_reference_type":
                base_type = self.resolve_type_name(type_die)
                return f"{base_type}&"

            if type_die.tag == "DW_TAG_rvalue_reference_type":
                base_type = self.resolve_type_name(type_die)
                return f"{base_type}&&"

            if type_die.tag == "DW_TAG_array_type":
                # Array handling delegated to separate method
                try:
                    from ....generators.utils.array_parser import parse_array_type

                    array_info = parse_array_type(type_die, self)
                    if array_info:
                        return str(array_info["name"])
                except ImportError as e:
                    logger.debug(f"Failed to import array_parser: {e}")
                except Exception as e:
                    logger.debug(f"Error in array parsing: {e}")

                # Fallback if parsing fails
                element_type = self.resolve_type_name(type_die)
                return f"{element_type}[]"

            if type_die.tag == "DW_TAG_base_type":
                # Base types should have names, but fallback to tag
                return str(type_die.tag).replace("DW_TAG_", "")

            # For unnamed types, use the tag name
            logger.debug(f"Unnamed type with tag: {type_die.tag}")
            return str(type_die.tag).replace("DW_TAG_", "")

        except Exception as e:
            logger.warning(f"Failed to resolve type reference for {die.tag}: {e}")
            return "unknown_type"

    @log_timing
    def collect_all_typedefs(self) -> dict[str, str]:
        """Collect ALL typedefs from the DWARF information.

        This method scans the entire DWARF info once and caches all typedefs for
        comprehensive type resolution. This includes primitive types, class types,
        struct types, and any other typedefs.

        Returns:
            Dictionary mapping typedef names to their underlying types
        """
        if self._all_typedefs is not None:
            return self._all_typedefs

        logger.info("Collecting all typedefs from DWARF info...")
        self._all_typedefs = {}

        cu_count = 0
        typedef_count = 0
        start_time = time()

        for cu in self.dwarf_info.iter_CUs():
            cu_count += 1

            for die in cu.iter_DIEs():
                if die.tag == "DW_TAG_typedef":
                    name_attr = die.attributes.get("DW_AT_name")
                    if name_attr:
                        typedef_name = (
                            name_attr.value.decode("utf-8")
                            if isinstance(name_attr.value, bytes)
                            else str(name_attr.value)
                        )

                        # Get the underlying type
                        underlying_type = self.resolve_type_name(die)
                        self._all_typedefs[typedef_name] = underlying_type
                        typedef_count += 1

                        logger.debug(f"Found typedef: {typedef_name} -> {underlying_type}")

        elapsed = time() - start_time
        logger.info(f"Collected {typedef_count} typedefs from {cu_count} CUs in {elapsed:.3f}s")

        return self._all_typedefs

    def resolve_typedef_chain(self, typedef_name: str) -> str:
        """Recursively resolve a typedef to its final underlying type.

        This handles typedef chains like:
        typedef __uint64_t u64;
        typedef unsigned long long __uint64_t;

        Args:
            typedef_name: Name of typedef to resolve

        Returns:
            Final underlying type after resolving all typedef chains
        """
        # Check cache first
        if typedef_name in self._typedef_chains:
            return self._typedef_chains[typedef_name]

        # Prevent infinite recursion
        if typedef_name in self._types_in_progress:
            logger.warning(f"Circular typedef dependency detected for {typedef_name}")
            return typedef_name

        self._types_in_progress.add(typedef_name)

        try:
            # Ensure all typedefs are collected
            if self._all_typedefs is None:
                self.collect_all_typedefs()

            # Check if this is a typedef
            if typedef_name not in self._all_typedefs:
                # Not a typedef, return as-is
                result = typedef_name
            else:
                # Get the underlying type
                underlying = self._all_typedefs[typedef_name]

                # Check if the underlying type is itself a typedef
                if underlying in self._all_typedefs:
                    # Recursively resolve
                    result = self.resolve_typedef_chain(underlying)
                else:
                    result = underlying

            # Cache the result
            self._typedef_chains[typedef_name] = result
            return result

        finally:
            self._types_in_progress.discard(typedef_name)

    @log_timing
    def find_typedef(self, typedef_name: str, deep_search: bool = False) -> tuple[str, str] | None:
        """Find a typedef definition by name.

        Returns (typedef_name, underlying_type) if found, None otherwise.
        Uses comprehensive typedef collection for full resolution.

        Args:
            typedef_name: Name of typedef to search for
            deep_search: If True, perform recursive resolution (always True in enhanced version)

        Returns:
            Tuple of (typedef_name, underlying_type) if found, None otherwise
        """
        # Create cache key
        cache_key = f"{typedef_name}_{deep_search}"

        # Check cache first
        if cache_key in self._typedef_cache:
            return self._typedef_cache[cache_key]

        # Ensure all typedefs are collected
        if self._all_typedefs is None:
            self.collect_all_typedefs()

        # Type guard - ensure _all_typedefs is not None after collection
        assert self._all_typedefs is not None

        # Check if the typedef exists
        if typedef_name not in self._all_typedefs:
            logger.debug(f"Typedef {typedef_name} not found in collected typedefs")
            result = None
        else:
            # Get the immediate underlying type
            underlying_type = self._all_typedefs[typedef_name]

            # Perform recursive resolution if needed
            final_type = self.resolve_typedef_chain(underlying_type)

            logger.debug(f"Typedef {typedef_name} -> {underlying_type} (final: {final_type})")
            result = (typedef_name, final_type)

        # Cache the result
        self._typedef_cache[cache_key] = result
        return result

    @log_timing
    def collect_used_typedefs(
        self,
        members: list["MemberInfo"],
        methods: list["MethodInfo"],
        unions: list["UnionInfo"] | None = None,
        nested_structs: list["StructInfo"] | None = None,
    ) -> dict[str, str]:
        """Collect only the typedefs that are actually used by members, methods, unions, and nested structs.

        Args:
            members: List of MemberInfo objects
            methods: List of MethodInfo objects
            unions: Optional list of UnionInfo objects to examine for typedefs
            nested_structs: Optional list of StructInfo objects to examine for typedefs

        Returns:
            Dictionary mapping typedef names to their fully resolved underlying types
        """
        total_members = len(members)
        total_methods = len(methods)
        total_unions = len(unions) if unions else 0
        total_structs = len(nested_structs) if nested_structs else 0

        logger.debug(
            f"Collecting used typedefs from {total_members} members, {total_methods} methods, "
            f"{total_unions} unions, {total_structs} nested structs"
        )

        # Ensure all typedefs are collected
        if self._all_typedefs is None:
            self.collect_all_typedefs()

        # Type guard - ensure _all_typedefs is not None after collection
        assert self._all_typedefs is not None

        used_typedefs = {}

        # Check all member types
        for member in members:
            # Extract base type name from complex types
            type_name = self._extract_base_type(member.type_name)
            logger.debug(f"Member {member.name} has cleaned type: {type_name}")

            # Check if it's a typedef using find_typedef
            typedef_result = self.find_typedef(type_name)
            if typedef_result:
                typedef_name, final_type = typedef_result
                used_typedefs[typedef_name] = final_type
                logger.debug(
                    f"Found typedef for member {member.name}: {typedef_name} -> {final_type}"
                )

        # Check method return types and parameters
        for method in methods:
            # Check return type
            return_type = self._extract_base_type(method.return_type)
            logger.debug(f"Method {method.name} has cleaned return type: {return_type}")

            typedef_result = self.find_typedef(return_type)
            if typedef_result:
                typedef_name, final_type = typedef_result
                used_typedefs[typedef_name] = final_type
                logger.debug(f"Found typedef for return type: {typedef_name} -> {final_type}")

            # Check parameter types
            if method.parameters:
                logger.debug(f"Method {method.name} has {len(method.parameters)} parameters")
                for param in method.parameters:
                    param_type = self._extract_base_type(param.type_name)
                    logger.debug(f"Parameter {param.name} has cleaned type: {param_type}")

                    typedef_result = self.find_typedef(param_type)
                    if typedef_result:
                        typedef_name, final_type = typedef_result
                        used_typedefs[typedef_name] = final_type
                        logger.debug(
                            f"Found typedef for parameter {param.name}: "
                            f"{typedef_name} -> {final_type}",
                        )

        # Check union member types
        if unions:
            for union in unions:
                logger.debug(f"Examining union {union.name} with {len(union.members)} members")
                for member in union.members:
                    type_name = self._extract_base_type(member.type_name)
                    logger.debug(f"Union member {member.name} has cleaned type: {type_name}")

                    typedef_result = self.find_typedef(type_name)
                    if typedef_result:
                        typedef_name, final_type = typedef_result
                        used_typedefs[typedef_name] = final_type
                        logger.debug(
                            f"Found typedef for union member {member.name}: {typedef_name} -> {final_type}"
                        )

                # Also check nested structs within unions
                if hasattr(union, "nested_structs") and union.nested_structs:
                    for nested_struct in union.nested_structs:
                        logger.debug(f"Examining nested struct in union {union.name}")
                        for member in nested_struct.members:
                            type_name = self._extract_base_type(member.type_name)
                            logger.debug(
                                f"Nested struct member {member.name} has cleaned type: {type_name}"
                            )

                            typedef_result = self.find_typedef(type_name)
                            if typedef_result:
                                typedef_name, final_type = typedef_result
                                used_typedefs[typedef_name] = final_type
                                logger.debug(
                                    f"Found typedef for nested struct member {member.name}: {typedef_name} -> {final_type}"
                                )

        # Check nested struct member types
        if nested_structs:
            for struct in nested_structs:
                logger.debug(
                    f"Examining nested struct {struct.name} with {len(struct.members)} members"
                )
                for member in struct.members:
                    type_name = self._extract_base_type(member.type_name)
                    logger.debug(
                        f"Nested struct member {member.name} has cleaned type: {type_name}"
                    )

                    typedef_result = self.find_typedef(type_name)
                    if typedef_result:
                        typedef_name, final_type = typedef_result
                        used_typedefs[typedef_name] = final_type
                        logger.debug(
                            f"Found typedef for nested struct member {member.name}: {typedef_name} -> {final_type}"
                        )

        # Also check for any indirect typedefs (typedefs used by resolved types)
        additional_typedefs = {}
        for _typedef_name, resolved_type in used_typedefs.items():
            # Check if resolved type contains other typedefs
            base_resolved = self._extract_base_type(resolved_type)
            if base_resolved in self._all_typedefs and base_resolved not in used_typedefs:
                final_type = self.resolve_typedef_chain(base_resolved)
                additional_typedefs[base_resolved] = final_type
                logger.debug(f"Found indirect typedef: {base_resolved} -> {final_type}")

        used_typedefs.update(additional_typedefs)

        logger.debug(f"Collected {len(used_typedefs)} total typedefs: {used_typedefs}")
        return used_typedefs

    def _extract_base_type(self, type_name: str) -> str:
        """Extract base type name from complex type declarations.

        Removes const, pointers, references, and array notation.

        Args:
            type_name: Full type name with qualifiers

        Returns:
            Base type name without qualifiers
        """
        logger.debug(f"Extracting base type from: {type_name}")

        # Remove const prefix
        if type_name.startswith("const "):
            type_name = type_name[6:].strip()

        # Remove pointer/reference suffixes
        while type_name.endswith("*") or type_name.endswith("&"):
            type_name = type_name[:-1].strip()

        # Handle array types - extract base type from array notation
        if "[" in type_name and "]" in type_name:
            base_type = type_name.split("[")[0].strip()
            logger.debug(f"Extracted base type from array: {base_type}")
            type_name = base_type

        logger.debug(f"Cleaned type: {type_name}")
        return type_name

    def clear_cache(self) -> None:
        """Clear all typedef caches.

        Useful for testing or when processing multiple ELF files.
        """
        self._typedef_cache.clear()
        self._all_typedefs = None
        self._typedef_chains.clear()
        self._types_in_progress.clear()
        logger.debug("All typedef caches cleared")
