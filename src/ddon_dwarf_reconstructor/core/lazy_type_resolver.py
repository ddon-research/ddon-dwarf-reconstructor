#!/usr/bin/env python3

"""Lazy type resolution for memory-efficient DWARF parsing.

This module provides on-demand type resolution without loading entire DWARF
information into memory. Uses offset-based caching and pyelftools' efficient
DIE reference resolution.
"""

from typing import Any

from elftools.dwarf.die import DIE
from elftools.dwarf.dwarfinfo import DWARFInfo

from ..domain.services.lazy_dwarf_index_service import LazyDwarfIndexService
from ..utils.logger import get_logger

logger = get_logger(__name__)


class LazyTypeResolver:
    """On-demand type resolution without full DWARF loading.
    
    This class provides memory-efficient type resolution by:
    1. Using offset-based caching instead of loading all typedefs
    2. Leveraging pyelftools' get_DIE_from_attribute() for reference resolution
    3. Implementing lazy typedef discovery with persistent caching
    4. Providing recursive type chain resolution with cycle detection
    """
    
    # Common primitive typedefs for quick lookup
    PRIMITIVE_TYPEDEFS = frozenset({
        "u8", "u16", "u32", "u64",
        "s8", "s16", "s32", "s64",
        "f32", "f64",
        "size_t", "ssize_t",
        "uint_fast8_t", "int_fast8_t",
        "uint_fast16_t", "int_fast16_t",
        "uint_fast32_t", "int_fast32_t",
        "uint_fast64_t", "int_fast64_t",
        # Platform-specific types
        "uint8_t", "int8_t",
        "uint16_t", "int16_t",
        "uint32_t", "int32_t",
        "uint64_t", "int64_t",
        "uintptr_t", "intptr_t",
        "__uint64_t", "__int64_t",
        "__uint32_t", "__int32_t",
        "__uint16_t", "__int16_t",
        "__uint8_t", "__int8_t",
    })
    
    def __init__(self, dwarf_info: DWARFInfo, lazy_index: LazyDwarfIndexService):
        """Initialize lazy type resolver.
        
        Args:
            dwarf_info: DWARF information from pyelftools
            lazy_index: Lazy DWARF index for offset-based lookups
        """
        self.dwarf_info = dwarf_info
        self.index = lazy_index
        
        # Runtime caches (offset-based)
        self._typedef_cache: dict[int, str] = {}  # offset → resolved typedef
        self._type_name_cache: dict[int, str] = {}  # offset → resolved type name
        self._typedef_chains: dict[str, str] = {}  # name → final resolved type
        
        # Recursion tracking
        self._types_in_progress: set[str] = set()
        
        # Add instance attribute for test compatibility
        self._primitive_typedefs: set[str] = set(self.PRIMITIVE_TYPEDEFS)
        
        logger.info("Initialized LazyTypeResolver with offset-based caching")
    
    def expand_primitive_search(self, full_hierarchy: bool = False) -> None:
        """Expand the set of primitive types to search for.
        
        Args:
            full_hierarchy: If True, include additional platform-specific types
        """
        if full_hierarchy:
            additional_types = {
                "ptrdiff_t", "wchar_t", "char16_t", "char32_t",
                "long long", "unsigned long long",
                "long double", "bool", "char", "wchar",
                "std::size_t", "std::ptrdiff_t"
            }
            self._primitive_typedefs.update(additional_types)
    
    def resolve_type_name(self, die: DIE, type_attr_name: str = "DW_AT_type") -> str:
        """Resolve type name using offset-based caching.
        
        Args:
            die: DIE to resolve type from
            type_attr_name: Attribute name containing type reference
            
        Returns:
            Resolved type name as string
        """
        try:
            # Check if the DIE has the type attribute
            if type_attr_name not in die.attributes:
                logger.debug(f"DIE {die.tag} has no {type_attr_name} attribute")
                return "void"
            
            # Use pyelftools' efficient offset resolution
            type_die = die.get_DIE_from_attribute(type_attr_name)
            if not type_die:
                logger.debug(f"Could not resolve {type_attr_name} reference")
                return "unknown_type"
            
            # Check cache first
            if type_die.offset in self._type_name_cache:
                return self._type_name_cache[type_die.offset]
            
            # Resolve type name
            resolved_name = self._resolve_die_type_name(type_die)
            
            # Cache the result
            self._type_name_cache[type_die.offset] = resolved_name
            
            return resolved_name
            
        except Exception as e:
            logger.warning(f"Failed to resolve type reference for {die.tag}: {e}")
            return "unknown_type"
    
    def _resolve_die_type_name(self, type_die: DIE) -> str:
        """Resolve type name from a type DIE.
        
        Args:
            type_die: DIE representing a type
            
        Returns:
            Resolved type name
        """
        # Get the type name if available
        name_attr = type_die.attributes.get("DW_AT_name")
        if name_attr:
            if isinstance(name_attr.value, bytes):
                return name_attr.value.decode("utf-8")
            return str(name_attr.value)
        
        # Handle different type tags without names
        if type_die.tag == "DW_TAG_pointer_type":
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
            # Simplified array handling for now
            element_type = self.resolve_type_name(type_die)
            return f"{element_type}[]"
        
        if type_die.tag == "DW_TAG_base_type":
            return str(type_die.tag).replace("DW_TAG_", "")
        
        # For unnamed types, use the tag name
        logger.debug(f"Unnamed type with tag: {type_die.tag}")
        return str(type_die.tag).replace("DW_TAG_", "")
    
    def find_typedef(self, typedef_name: str) -> tuple[str, str] | None:
        """Find typedef using lazy loading and caching.
        
        Args:
            typedef_name: Name of typedef to find
            
        Returns:
            Tuple of (typedef_name, underlying_type) or None if not found
        """
        # Check if this is a known primitive
        if typedef_name in self._primitive_typedefs:
            return typedef_name, typedef_name
        
        # Check persistent cache first
        offset = self.index.find_symbol_offset(typedef_name, "typedef")
        if offset is not None:
            # Get cached typedef
            if offset in self._typedef_cache:
                underlying = self._typedef_cache[offset]
                logger.debug(f"Found cached typedef: {typedef_name} -> {underlying}")
                return typedef_name, underlying
            
            # Resolve typedef from DIE
            die = self.index.get_die_by_offset(offset)
            if die and die.tag == "DW_TAG_typedef":
                underlying = self.resolve_type_name(die)
                self._typedef_cache[offset] = underlying
                logger.debug(f"Resolved typedef: {typedef_name} -> {underlying}")
                return typedef_name, underlying
        
        # Check persistent cache first, then fallback to targeted search
        offset = self.index.find_symbol_offset(typedef_name, "typedef")
        if offset is None:
            offset = self.index.targeted_symbol_search(typedef_name, "typedef")
        if offset is not None:
            die = self.index.get_die_by_offset(offset)
            if die and die.tag == "DW_TAG_typedef":
                underlying = self.resolve_type_name(die)
                self._typedef_cache[offset] = underlying
                logger.debug(f"Found and cached typedef: {typedef_name} -> {underlying}")
                return typedef_name, underlying
        
        logger.debug(f"Typedef not found: {typedef_name}")
        return None
    
    def resolve_typedef_chain(self, typedef_name: str) -> str:
        """Recursively resolve typedef to its final underlying type.
        
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
            # Find the typedef
            typedef_result = self.find_typedef(typedef_name)
            if typedef_result is None:
                # Not a typedef, return as-is
                result = typedef_name
            else:
                _, underlying = typedef_result
                
                # Check if the underlying type is itself a typedef
                underlying_result = self.find_typedef(underlying)
                if underlying_result is not None:
                    # Recursively resolve
                    result = self.resolve_typedef_chain(underlying)
                else:
                    # Final type reached
                    result = underlying
            
            # Cache the result
            self._typedef_chains[typedef_name] = result
            
            return result
            
        finally:
            self._types_in_progress.discard(typedef_name)
    
    def collect_typedefs_from_die(self, class_die: DIE) -> set[str]:
        """Collect typedefs used by a class DIE, resolving them lazily.
        
        Args:
            class_die: DIE representing a class/struct
            
        Returns:
            Set of resolved typedef names used by the class
        """
        used_typedefs = set()
        
        try:
            # Process all member DIEs
            for child_die in class_die.iter_children():
                if child_die.tag == "DW_TAG_member":
                    # Get member type
                    member_type = self.resolve_type_name(child_die)
                    
                    # Check if it's a typedef we should resolve
                    if self.find_typedef(member_type) is not None:
                        resolved_type = self.resolve_typedef_chain(member_type)
                        used_typedefs.add(resolved_type)
                        logger.debug(f"Found used typedef: {member_type} -> {resolved_type}")
        
        except Exception as e:
            logger.warning(f"Error collecting typedefs from class: {e}")
        
        return used_typedefs
    
    def get_cache_stats(self) -> dict[str, Any]:
        """Get statistics about cache usage and performance.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            "typedef_cache_size": len(self._typedef_cache),
            "type_name_cache_size": len(self._type_name_cache), 
            "typedef_chains_size": len(self._typedef_chains),
            "types_in_progress": len(self._types_in_progress),
            "primitive_typedefs": len(self._primitive_typedefs)
        }
    
    def clear_caches(self) -> None:
        """Clear all runtime caches."""
        self._typedef_cache.clear()
        self._type_name_cache.clear()
        self._typedef_chains.clear()
        self._types_in_progress.clear()
        logger.info("LazyTypeResolver caches cleared")

    def collect_used_typedefs(
        self, 
        members: list, 
        methods: list, 
        unions: list | None = None, 
        nested_structs: list | None = None
    ) -> dict[str, str]:
        """Collect typedefs used by members, methods, unions, and nested structs with lazy resolution.
        
        This method discovers and resolves primitive typedefs that are actually
        used in the class definition, providing compatibility with header generation.
        
        Args:
            members: List of MemberInfo objects
            methods: List of MethodInfo objects
            unions: Optional list of UnionInfo objects to examine for typedefs
            nested_structs: Optional list of StructInfo objects to examine for typedefs
            
        Returns:
            Dictionary mapping typedef names to their resolved types
        """
        found_typedefs: dict[str, str] = {}
        total_unions = len(unions) if unions else 0
        total_structs = len(nested_structs) if nested_structs else 0
        logger.debug(
            f"Collecting typedefs from {len(members)} members, {len(methods)} methods, "
            f"{total_unions} unions, {total_structs} nested structs"
        )
        
        # Collect type names from members using DWARF DIE traversal
        type_names = set()
        for member in members:
            if hasattr(member, 'type_name') and member.type_name:
                # Try to get base type via DWARF DIE traversal first
                base_type = self._get_base_type_from_typename(member.type_name)
                if base_type:
                    type_names.add(base_type)
                    logger.debug(f"Member {member.name}: {member.type_name} -> {base_type} (DWARF)")
                else:
                    # Fallback to string extraction if DIE traversal fails
                    base_type = self._extract_base_type(member.type_name)
                    type_names.add(base_type)
                    logger.debug(f"Member {member.name}: {member.type_name} -> {base_type} (string fallback)")
        
        # Collect type names from methods (parameters and return types)
        for method in methods:
            if hasattr(method, 'return_type') and method.return_type:
                # Try DWARF DIE traversal first for return type
                base_type = self._get_base_type_from_typename(method.return_type)
                if base_type:
                    type_names.add(base_type)
                    logger.debug(f"Method return type: {method.return_type} -> {base_type} (DWARF)")
                else:
                    # Fallback to string extraction
                    base_type = self._extract_base_type(method.return_type)
                    type_names.add(base_type)
                    logger.debug(
                        f"Method return type: {method.return_type} -> {base_type} (string fallback)"
                    )
            
            if hasattr(method, 'parameters'):
                for param in method.parameters:
                    if hasattr(param, 'type_name') and param.type_name:
                        # Try DWARF DIE traversal first for parameter type
                        base_type = self._get_base_type_from_typename(param.type_name)
                        if base_type:
                            type_names.add(base_type)
                            logger.debug(
                                f"Method param {param.name}: {param.type_name} -> {base_type} (DWARF)"
                            )
                        else:
                            # Fallback to string extraction
                            base_type = self._extract_base_type(param.type_name)
                            type_names.add(base_type)
                            logger.debug(
                                f"Method param {param.name}: {param.type_name} -> {base_type} (string fallback)"
                            )
        
        # Collect type names from union members
        if unions:
            for union in unions:
                logger.debug(f"Examining union {union.name} for typedefs")
                for member in union.members:
                    if hasattr(member, 'type_name') and member.type_name:
                        base_type = self._extract_base_type(member.type_name)
                        type_names.add(base_type)
                        logger.debug(f"Union member {member.name}: {member.type_name} -> {base_type}")
                
                # Check nested structs within unions
                if hasattr(union, 'nested_structs') and union.nested_structs:
                    for nested_struct in union.nested_structs:
                        for member in nested_struct.members:
                            if hasattr(member, 'type_name') and member.type_name:
                                base_type = self._extract_base_type(member.type_name)
                                type_names.add(base_type)
                                logger.debug(f"Nested struct member {member.name}: {member.type_name} -> {base_type}")
        
        # Collect type names from nested struct members  
        if nested_structs:
            for struct in nested_structs:
                logger.debug(f"Examining nested struct {struct.name} for typedefs")
                for member in struct.members:
                    if hasattr(member, 'type_name') and member.type_name:
                        base_type = self._extract_base_type(member.type_name)
                        type_names.add(base_type)
                        logger.debug(f"Nested struct member {member.name}: {member.type_name} -> {base_type}")
        
        # Look for primitive typedefs in the collected type names
        for type_name in type_names:
            if type_name in self._primitive_typedefs:
                resolved_type = self._resolve_primitive_typedef(type_name)
                if resolved_type and resolved_type != type_name:
                    # Only add if it's a real typedef (resolves to a different type)
                    # Skip base types that resolve to themselves (bool -> bool)
                    found_typedefs[type_name] = resolved_type
                    logger.debug(f"Resolved primitive typedef: {type_name} -> {resolved_type}")
                elif resolved_type == type_name:
                    logger.debug(f"Skipping base type {type_name} (not a typedef)")
        
        logger.debug(f"Collected {len(found_typedefs)} primitive typedefs")
        return found_typedefs

    def _resolve_primitive_typedef(self, typedef_name: str) -> str | None:
        """Resolve a primitive type (typedef or base type) using lazy search.
        
        Args:
            typedef_name: Name of the type to resolve (can be typedef or base type)
            
        Returns:
            Resolved type name, or None if not found
        """
        if not self.index:
            logger.debug(f"No index available for type resolution: {typedef_name}")
            return None
            
        try:
            # Check persistent cache first for both typedef and base_type
            offset = self.index.find_symbol_offset(typedef_name, "typedef")
            if offset is None:
                offset = self.index.find_symbol_offset(typedef_name, "base_type")
            
            # If not in cache, use targeted search for both typedef and base_type simultaneously
            if offset is None:
                offset = self.index.targeted_symbol_search(typedef_name, "primitive_type")
            if offset:
                logger.debug(f"Found {typedef_name} at offset 0x{offset:x}")
                # Get the DIE and determine how to resolve it
                die = self.index.get_die_by_offset(offset)
                logger.debug(f"get_die_by_offset returned: {die is not None}")
                if die:
                    logger.debug(f"Retrieved DIE for {typedef_name}: tag={die.tag}")
                    
                    # Handle base types directly - they are the final type
                    if die.tag == "DW_TAG_base_type":
                        logger.debug(f"Found base type {typedef_name}, returning as-is")
                        return typedef_name
                    
                    # Handle typedefs - resolve to underlying type
                    elif die.tag == "DW_TAG_typedef":
                        type_attr = die.attributes.get("DW_AT_type")
                        if type_attr:
                            logger.debug(f"Found DW_AT_type attribute for typedef {typedef_name}")
                            target_die = die.get_DIE_from_attribute("DW_AT_type")
                            if target_die:
                                logger.debug(f"Resolved target DIE: tag={target_die.tag}")
                                resolved_name = self._get_primitive_base_type_name(target_die)
                                logger.debug(f"Resolved typedef {typedef_name} -> {resolved_name}")
                                return resolved_name
                            else:
                                logger.debug(f"Could not get target DIE from DW_AT_type for {typedef_name}")
                        else:
                            logger.debug(f"No DW_AT_type attribute found for typedef {typedef_name}")
                else:
                    logger.debug(f"Could not retrieve DIE at offset 0x{offset:x} for {typedef_name}")
            else:
                logger.debug(f"No offset found for typedef: {typedef_name}")
            
            logger.debug(f"Could not resolve primitive typedef: {typedef_name}")
            return None
            
        except Exception as e:
            logger.warning(f"Error resolving primitive typedef {typedef_name}: {e}")
            return None
    
    def _get_primitive_base_type_name(self, type_die: DIE) -> str:
        """Get the name of a primitive base type from DIE with recursive resolution.
        
        Args:
            type_die: DIE representing the base type
            
        Returns:
            String representation of the base type
        """
        # Handle base types directly
        if type_die.tag == "DW_TAG_base_type":
            name_attr = type_die.attributes.get("DW_AT_name")
            if name_attr:
                if isinstance(name_attr.value, bytes):
                    return name_attr.value.decode("utf-8")
                return str(name_attr.value)
        
        # Handle typedefs by recursively resolving
        if type_die.tag == "DW_TAG_typedef":
            type_attr = type_die.attributes.get("DW_AT_type")
            if type_attr:
                target_die = type_die.get_DIE_from_attribute("DW_AT_type")
                if target_die:
                    # Recursively resolve the typedef chain
                    return self._get_primitive_base_type_name(target_die)
        
        # Handle const/volatile/pointer/reference types by following their type
        if type_die.tag in ("DW_TAG_const_type", "DW_TAG_volatile_type", "DW_TAG_pointer_type", "DW_TAG_reference_type"):
            type_attr = type_die.attributes.get("DW_AT_type")
            if type_attr:
                target_die = type_die.get_DIE_from_attribute("DW_AT_type")
                if target_die:
                    return self._get_primitive_base_type_name(target_die)
        
        # Fallback to tag name without DW_TAG_ prefix
        return str(type_die.tag).replace("DW_TAG_", "")

    def _extract_base_type(self, type_name: str) -> str:
        """Extract base type name from complex type declarations.

        Removes const, volatile, pointers, references, and array notation.
        Handles DWARF-generated type strings properly.

        Args:
            type_name: Full type name with qualifiers

        Returns:
            Base type name without qualifiers
        """
        logger.debug(f"Extracting base type from: {type_name}")
        original_name = type_name

        # Remove const/volatile prefixes (can appear multiple times)
        while type_name.startswith("const ") or type_name.startswith("volatile "):
            if type_name.startswith("const "):
                type_name = type_name[6:].strip()
            elif type_name.startswith("volatile "):
                type_name = type_name[9:].strip()

        # Remove rvalue reference suffix first (&&), then lvalue reference (&), then pointers (*)
        while (type_name.endswith("&&") or type_name.endswith("&") or type_name.endswith("*")):
            if type_name.endswith("&&"):
                type_name = type_name[:-2].strip()
            elif type_name.endswith("&"):
                type_name = type_name[:-1].strip()
            elif type_name.endswith("*"):
                type_name = type_name[:-1].strip()

        # Handle array types with dimensions [N] or []
        if "[" in type_name and "]" in type_name:
            base_type = type_name.split("[")[0].strip()
            logger.debug(f"Extracted base type from array: {base_type}")
            type_name = base_type

        logger.debug(f"Type extraction: '{original_name}' -> '{type_name}'")
        return type_name

    def _get_base_type_from_typename(self, type_name: str) -> str | None:
        """Get base type by traversing DWARF DIE chain for a given type name.

        This method attempts to find the DIE for the given type name and then
        properly traverses the DWARF DIE chain (const_type -> reference_type -> base_type)
        to find the actual base type, avoiding string parsing issues.

        Args:
            type_name: Type name to resolve (e.g., "const MtVector3&")

        Returns:
            Base type name if found via DWARF traversal, None if not found
        """
        if not self.index:
            return None

        try:
            # The type_name might be qualified (const Type&), but we need to search
            # for the actual type. For now, let's try a few strategies to find the DIE

            # Strategy 1: Try to find a class/struct with this exact name
            for symbol_type in ["class", "struct", "union", "typedef", "base_type"]:
                offset = self.index.find_symbol_offset(type_name, symbol_type)
                if offset is not None:
                    die = self.index.get_die_by_offset(offset)
                    if die:
                        # Use the existing DWARF traversal logic
                        base_type = self._get_primitive_base_type_name(die)
                        logger.debug(f"DWARF traversal: {type_name} -> {base_type}")
                        return base_type

            # Strategy 2: For complex qualified types, we'd need more
            # sophisticated parsing. This would involve parsing the qualified
            # type name and finding the base type
            # For now, return None to fall back to string parsing

            logger.debug(f"Could not find DWARF DIE for type: {type_name}")
            return None

        except Exception as e:
            logger.debug(f"Error in DWARF DIE traversal for {type_name}: {e}")
            return None
