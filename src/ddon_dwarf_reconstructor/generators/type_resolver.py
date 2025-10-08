#!/usr/bin/env python3

"""Type resolution and typedef handling for DWARF parsing.

This module provides type resolution logic for DWARF DIEs, handling:
- Primitive type resolution (u8, u16, u32, etc.)
- Typedef chains
- Type qualifiers (const, pointer, reference)
- Caching for performance optimization
"""

from typing import TYPE_CHECKING

from elftools.dwarf.die import DIE
from elftools.dwarf.dwarfinfo import DWARFInfo

if TYPE_CHECKING:
    from ..models import MemberInfo, MethodInfo

from ..utils.logger import get_logger

logger = get_logger(__name__)


class TypeResolver:
    """Handles all type resolution logic for DWARF parsing.

    This class resolves type names from DWARF DIEs, following reference chains,
    resolving typedefs, and applying type qualifiers. Includes caching for
    performance optimization.

    Attributes:
        dwarf_info: DWARF information structure from pyelftools
        _typedef_cache: Cache of resolved typedefs for performance
        _primitive_typedefs: Set of primitive typedef names to resolve
    """

    # Primitive typedefs commonly used in game engines
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
        }
    )

    def __init__(self, dwarf_info: DWARFInfo):
        """Initialize type resolver with DWARF information.

        Args:
            dwarf_info: DWARF information structure from pyelftools
        """
        self.dwarf_info = dwarf_info
        self._typedef_cache: dict[str, tuple[str, str] | None] = {}
        self._primitive_typedefs = set(self.PRIMITIVE_TYPEDEFS)  # Convert to mutable set

    def expand_primitive_search(self, full_hierarchy: bool = False) -> None:
        """Expand the set of primitive types to search for.

        Args:
            full_hierarchy: If True, include additional platform-specific types
        """
        if full_hierarchy:
            self._primitive_typedefs.update(
                {
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
                }
            )

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
                from .utils.array_parser import parse_array_type

                array_info = parse_array_type(type_die, self)
                if array_info:
                    return str(array_info["name"])
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

    def find_typedef(self, typedef_name: str, deep_search: bool = False) -> tuple[str, str] | None:
        """Find a typedef definition by name for primitive types only.

        Returns (typedef_name, underlying_type) if found, None otherwise.
        Uses caching to avoid repeated searches.

        Args:
            typedef_name: Name of typedef to search for
            deep_search: If True, expand search to more types (for full hierarchy mode)

        Returns:
            Tuple of (typedef_name, underlying_type) if found, None otherwise
        """
        # Check cache first
        cache_key = f"{typedef_name}_{deep_search}"
        if cache_key in self._typedef_cache:
            return self._typedef_cache[cache_key]

        # Determine search set based on mode
        search_types = self._primitive_typedefs if deep_search else self.PRIMITIVE_TYPEDEFS

        # Only search for types in the search set
        if typedef_name not in search_types:
            logger.debug(f"Skipping typedef lookup for non-primitive type: {typedef_name}")
            self._typedef_cache[cache_key] = None
            return None

        logger.debug(f"Searching for typedef: {typedef_name} (deep_search={deep_search})")
        target_name = typedef_name.encode("utf-8")

        cu_count = 0
        die_count = 0

        for cu in self.dwarf_info.iter_CUs():
            cu_count += 1
            logger.debug(
                f"Searching CU #{cu_count} at offset 0x{cu.cu_offset:x} for typedef {typedef_name}",
            )

            for die in cu.iter_DIEs():
                die_count += 1
                if die.tag == "DW_TAG_typedef":
                    name_attr = die.attributes.get("DW_AT_name")
                    if name_attr and name_attr.value == target_name:
                        logger.debug(
                            f"Found typedef {typedef_name} at DIE offset 0x{die.offset:x} "
                            f"in CU #{cu_count}",
                        )
                        # Get the underlying type
                        underlying_type = self.resolve_type_name(die)
                        logger.debug(f"Typedef {typedef_name} resolves to: {underlying_type}")

                        result = (typedef_name, underlying_type)
                        self._typedef_cache[cache_key] = result
                        return result

        logger.debug(
            f"Typedef {typedef_name} not found after searching {cu_count} CUs and {die_count} DIEs",
        )
        self._typedef_cache[cache_key] = None
        return None

    def collect_used_typedefs(
        self, members: list["MemberInfo"], methods: list["MethodInfo"]
    ) -> dict[str, str]:
        """Collect only the typedefs that are actually used by members and methods.

        Args:
            members: List of MemberInfo objects
            methods: List of MethodInfo objects

        Returns:
            Dictionary mapping typedef names to their underlying types
        """
        logger.debug(
            f"Collecting used typedefs from {len(members)} members and {len(methods)} methods"
        )
        used_typedefs = {}

        # Check all member types
        logger.debug(f"Checking {len(members)} members for typedef usage")
        for member in members:
            # Extract base type name from complex types
            type_name = self._extract_base_type(member.type_name)
            logger.debug(f"Member {member.name} has cleaned type: {type_name}")

            # Try to find as typedef
            result = self.find_typedef(type_name)
            if result:
                typedef_name, underlying_type = result
                used_typedefs[typedef_name] = underlying_type
                logger.debug(
                    f"Found typedef for member {member.name}: {typedef_name} -> {underlying_type}",
                )

        # Check method return types and parameters
        logger.debug(f"Checking {len(methods)} methods for typedef usage")
        for method in methods:
            # Check return type
            return_type = self._extract_base_type(method.return_type)
            logger.debug(f"Method {method.name} has cleaned return type: {return_type}")

            result = self.find_typedef(return_type)
            if result:
                typedef_name, underlying_type = result
                used_typedefs[typedef_name] = underlying_type
                logger.debug(f"Found typedef for return type: {typedef_name} -> {underlying_type}")

            # Check parameter types
            if method.parameters:
                logger.debug(f"Method {method.name} has {len(method.parameters)} parameters")
                for param in method.parameters:
                    param_type = self._extract_base_type(param.type_name)
                    logger.debug(f"Parameter {param.name} has cleaned type: {param_type}")

                    result = self.find_typedef(param_type)
                    if result:
                        typedef_name, underlying_type = result
                        used_typedefs[typedef_name] = underlying_type
                        logger.debug(
                            f"Found typedef for parameter {param.name}: "
                            f"{typedef_name} -> {underlying_type}",
                        )

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
        if type_name.endswith("*"):
            type_name = type_name[:-1].strip()
        if type_name.endswith("&"):
            type_name = type_name[:-1].strip()

        # Handle array types - extract base type from array notation
        if "[" in type_name and "]" in type_name:
            base_type = type_name.split("[")[0].strip()
            logger.debug(f"Extracted base type from array: {base_type}")
            type_name = base_type

        logger.debug(f"Cleaned type: {type_name}")
        return type_name

    def clear_cache(self) -> None:
        """Clear the typedef cache.

        Useful for testing or when processing multiple ELF files.
        """
        self._typedef_cache.clear()
        logger.debug("Typedef cache cleared")
