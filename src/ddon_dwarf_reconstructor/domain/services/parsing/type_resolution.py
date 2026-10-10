"""Type-resolution operations for lazy DWARF lookup."""

from __future__ import annotations

from ....core.dwarf import DwarfEntry
from ....core.observability import get_logger
from ...models.dwarf import TypeReference
from ..search_result import SearchStatus
from .type_resolver_context import TypeResolverContext
from .type_scope import die_key, qualified_die_name

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
        """Render a reference through the canonical structured type parser."""
        try:
            if type_attr_name not in die.attributes:
                if type_attr_name == "DW_AT_type" and die.tag in _NAMED_TYPE_TAGS:
                    return self.resolve_die_type(die)
                return "void"
            return self._referenced_type_name(die, type_attr_name)
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
            logger.warning("Failed to resolve type reference for %s", die.tag, exc_info=error)
            return "unknown_type"

    def _referenced_type_name(
        self: TypeResolverContext, die: DwarfEntry, type_attr_name: str
    ) -> str:
        unit, offset = die_key(die)
        source_key = (
            (unit, offset, type_attr_name) if unit is not None and offset is not None else None
        )
        target_key = self._reference_target_cache.get(source_key) if source_key else None
        if target_key is not None and target_key in self._type_name_cache:
            return self._type_name_cache[target_key]
        target = die.get_DIE_from_attribute(type_attr_name)
        if target is not None and source_key is not None:
            if len(self._reference_target_cache) >= 65536:
                self._reference_target_cache.clear()
            self._reference_target_cache[source_key] = die_key(target)
        return self.resolve_die_type(target) if target is not None else "unknown_type"

    def resolve_type_reference(self: TypeResolverContext, type_die: DwarfEntry) -> TypeReference:
        """Return source-bound declarator, alias and scope evidence."""
        return self._reference_parser.parse(type_die)

    def anonymous_typedef_die(self: TypeResolverContext, die: DwarfEntry) -> DwarfEntry | None:
        """Reuse the request-owned index of aliases within an aggregate scope."""
        return self._reference_parser.anonymous_typedefs.find(die)

    def resolve_reference(self: TypeResolverContext, die: DwarfEntry) -> TypeReference:
        """Return a declaration's immediate typed reference."""
        return self._reference_parser.reference(die)

    def resolve_die_type(self: TypeResolverContext, type_die: DwarfEntry) -> str:
        """Resolve a type DIE without conflating equal offsets from different CUs."""
        key = die_key(type_die)
        cacheable = key[0] is not None and key[1] is not None
        if cacheable and key in self._type_name_cache:
            return self._type_name_cache[key]
        try:
            name = self.resolve_type_reference(type_die).name
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
            logger.warning("Failed to resolve type DIE %s", type_die.tag, exc_info=error)
            return "unknown_type"
        if cacheable:
            if len(self._type_name_cache) >= 65536:
                self._type_name_cache.clear()
            self._type_name_cache[key] = name
        return name

    def _resolve_die_type_name(self: TypeResolverContext, type_die: DwarfEntry) -> str:
        return self.resolve_type_reference(type_die).name

    @staticmethod
    def _named_type_name(type_die: DwarfEntry) -> str | None:
        return qualified_die_name(type_die)

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
