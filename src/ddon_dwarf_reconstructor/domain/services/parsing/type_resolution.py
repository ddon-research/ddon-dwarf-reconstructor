"""Type-resolution operations for lazy DWARF lookup."""

from __future__ import annotations

from ....core.dwarf import DwarfEntry, decode_dwarf_string
from ....core.observability import get_logger
from ..search_result import SearchStatus
from .array_parser import parse_array_type
from .type_resolver_context import TypeResolverContext

logger = get_logger(__name__)
_NAMED_TYPE_TAGS = frozenset(
    {
        "DW_TAG_base_type",
        "DW_TAG_class_type",
        "DW_TAG_enumeration_type",
        "DW_TAG_structure_type",
        "DW_TAG_typedef",
        "DW_TAG_union_type",
    }
)


class TypeResolutionMixin:
    def expand_primitive_search(self: TypeResolverContext, full_hierarchy: bool = False) -> None:
        """Expand the set of primitive types to search for.

        Args:
            full_hierarchy: If True, include additional platform-specific types
        """
        if full_hierarchy:
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

    def resolve_type_name(
        self: TypeResolverContext, die: DwarfEntry, type_attr_name: str = "DW_AT_type"
    ) -> str:
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
                if type_attr_name == "DW_AT_type" and die.tag in _NAMED_TYPE_TAGS:
                    direct_name = self._named_type_name(die)
                    if direct_name is not None:
                        return direct_name
                logger.debug(f"DIE {die.tag} has no {type_attr_name} attribute")
                return "void"

            # Use pyelftools' efficient offset resolution
            type_die = die.get_DIE_from_attribute(type_attr_name)
            if type_die is None:
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

        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
            logger.warning(
                "Failed to resolve type reference for %s: %s", die.tag, error, exc_info=error
            )
            return "unknown_type"

    def _resolve_die_type_name(self: TypeResolverContext, type_die: DwarfEntry) -> str:
        named_type = self._named_type_name(type_die)
        if named_type is not None:
            return named_type
        if type_die.tag in {
            "DW_TAG_pointer_type",
            "DW_TAG_const_type",
            "DW_TAG_volatile_type",
            "DW_TAG_restrict_type",
            "DW_TAG_reference_type",
            "DW_TAG_rvalue_reference_type",
        }:
            return self._resolve_qualified_type(type_die)
        if type_die.tag == "DW_TAG_array_type":
            return self._resolve_array_type(type_die)
        if type_die.tag == "DW_TAG_subroutine_type":
            return "void"
        if type_die.tag == "DW_TAG_ptr_to_member_type":
            return "void*"
        if type_die.tag == "DW_TAG_base_type":
            return "base_type"
        logger.debug("Unnamed type with tag: %s", type_die.tag)
        return str(type_die.tag).replace("DW_TAG_", "")

    @staticmethod
    def _named_type_name(type_die: DwarfEntry) -> str | None:
        name_attr = type_die.attributes.get("DW_AT_name")
        if name_attr is None:
            return None
        return decode_dwarf_string(name_attr.value)

    def _resolve_qualified_type(self: TypeResolverContext, type_die: DwarfEntry) -> str:
        base_type = self.resolve_type_name(type_die)
        if type_die.tag == "DW_TAG_pointer_type" and base_type == "unknown_type":
            return "void*"
        suffixes = {
            "DW_TAG_pointer_type": "*",
            "DW_TAG_const_type": "",
            "DW_TAG_volatile_type": "",
            "DW_TAG_restrict_type": "",
            "DW_TAG_reference_type": "&",
            "DW_TAG_rvalue_reference_type": "&&",
        }
        if type_die.tag == "DW_TAG_const_type":
            return f"const {base_type}"
        if type_die.tag == "DW_TAG_volatile_type":
            return f"volatile {base_type}"
        if type_die.tag == "DW_TAG_restrict_type":
            return f"restrict {base_type}"
        suffix = suffixes.get(str(type_die.tag))
        return f"{base_type}{suffix or ''}"

    def _resolve_array_type(self: TypeResolverContext, type_die: DwarfEntry) -> str:
        try:
            array_info = parse_array_type(type_die, self)
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            logger.debug("Error in array parsing: %s", error, exc_info=error)
        else:
            if array_info:
                return array_info.name
        element_type = self.resolve_type_name(type_die)
        return f"{element_type}[]"

    def find_typedef(self: TypeResolverContext, typedef_name: str) -> tuple[str, str] | None:
        """Find typedef using lazy loading and caching.

        Args:
            typedef_name: Name of typedef to find

        Returns:
            Tuple of (typedef_name, underlying_type) or None if not found
        """
        # Check if this is a known primitive
        if typedef_name in self._primitive_typedefs:
            return typedef_name, typedef_name

        # Check the persistent index once, then perform one targeted fallback.
        offset = self.index.find_symbol_offset(typedef_name)
        if offset is None:
            search = self.index.targeted_symbol_search(typedef_name)
            if search.status is not SearchStatus.COMPLETE:
                logger.debug(
                    "Typedef search for %s ended as %s: %s",
                    typedef_name,
                    search.status.value,
                    "; ".join(search.diagnostics),
                )
                return None
            offset = search.die_offset
        if offset is None:
            logger.debug(f"Typedef not found: {typedef_name}")
            return None

        if offset in self._typedef_cache:
            underlying = self._typedef_cache[offset]
            logger.debug(f"Found cached typedef: {typedef_name} -> {underlying}")
            return typedef_name, underlying

        die = self.index.get_die_by_offset(offset)
        if die and die.tag == "DW_TAG_typedef":
            underlying = self.resolve_type_name(die)
            self._typedef_cache[offset] = underlying
            logger.debug(f"Resolved typedef: {typedef_name} -> {underlying}")
            return typedef_name, underlying

        logger.debug(f"Typedef not found: {typedef_name}")
        return None

    def resolve_typedef_chain(self: TypeResolverContext, typedef_name: str) -> str:
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

    def collect_typedefs_from_die(self: TypeResolverContext, class_die: DwarfEntry) -> set[str]:
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

        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
            logger.warning("Error collecting typedefs from class: %s", error, exc_info=error)

        return used_typedefs
