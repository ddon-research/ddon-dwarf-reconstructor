#!/usr/bin/env python3

"""Dependency extraction using offset-based DWARF traversal.

This module extracts type dependencies from ClassInfo objects using
DIE offsets rather than string parsing. This eliminates bugs caused
by parsing type strings with qualifiers (const, *, &, etc.).
"""

from ....core.observability import get_logger
from ...models.dwarf import ClassInfo, MemberInfo, MethodInfo, StructInfo, UnionInfo
from ...ports.dwarf_index import DwarfIndexPort
from ..parsing.die_type_classifier import DIETypeClassifier

logger = get_logger(__name__)


class DependencyExtractor:
    """Extract type dependencies using offset-based DWARF traversal."""

    def __init__(self, dwarf_index: DwarfIndexPort):
        """Initialize dependency extractor.

        Args:
            dwarf_index: Lazy DWARF index service for offset lookups
        """
        self.dwarf_index = dwarf_index

    def extract_dependencies(
        self,
        class_info: ClassInfo,
        *,
        include_method_signatures: bool = True,
    ) -> set[int]:
        """Extract all type dependencies from a class.

        Collects DIE offsets of concrete layout types referenced by:
        - Member variables
        - Nested structs
        - Unions
        - Nested classes

        Method return and parameter types can be included for a complete
        signature closure or excluded for a bounded structural closure.

        Args:
            class_info: ClassInfo to extract dependencies from
            include_method_signatures: Include method return and parameter
                types in the transitive dependency set.

        Returns:
            Set of DIE offsets for dependent types
        """
        dependencies = self._direct_dependencies(class_info, include_method_signatures)
        self._nested_aggregate_dependencies(class_info, dependencies, include_method_signatures)

        logger.debug(
            f"Extracted {len(dependencies)} dependencies from {class_info.name}: "
            f"{[f'0x{off:x}' for off in sorted(dependencies)]}"
        )

        return dependencies

    def _direct_dependencies(
        self, class_info: ClassInfo, include_method_signatures: bool
    ) -> set[int]:
        dependencies: set[int] = set()
        for member in class_info.members:
            offset = self._get_member_type_offset(member)
            if offset is not None:
                dependencies.add(offset)
        if include_method_signatures:
            for method in class_info.methods:
                offset = self._get_method_return_type_offset(method)
                if offset is not None:
                    dependencies.add(offset)
                for parameter in method.parameters or []:
                    offset = self._get_parameter_type_offset(parameter)
                    if offset is not None:
                        dependencies.add(offset)
        return dependencies

    def _nested_aggregate_dependencies(
        self,
        class_info: ClassInfo,
        dependencies: set[int],
        include_method_signatures: bool,
    ) -> None:
        for nested_struct in class_info.nested_structs:
            self._extract_struct_dependencies(nested_struct, dependencies)
        for union in class_info.unions:
            self._extract_union_dependencies(union, dependencies)
        for nested_class in class_info.nested_classes:
            dependencies.update(
                self.extract_dependencies(
                    nested_class, include_method_signatures=include_method_signatures
                )
            )

    def filter_resolvable_types(self, offsets: set[int]) -> set[int]:
        """Filter offsets to only those that should be resolved as dependencies.

        Excludes:
        - Primitive types (int, float, etc.)
        - Enums (simple values, don't need full resolution)
        - Namespaces (not types)
        - Typedefs (aliases, resolved separately)
        - Forward declarations (incomplete types)

        Includes:
        - Classes (forward-declarable, need full resolution)
        - Structs (forward-declarable, need full resolution)
        - Unions (forward-declarable, need full resolution)

        Args:
            offsets: Set of DIE offsets to filter

        Returns:
            Filtered set of offsets that require resolution
        """
        resolvable: set[int] = set()

        for offset in offsets:
            die = self.dwarf_index.get_die_by_offset(offset)
            if die is None:
                logger.debug(f"Could not resolve DIE at offset 0x{offset:x}")
                continue

            # Check if this type requires dependency resolution
            if DIETypeClassifier.requires_resolution(die):
                resolvable.add(offset)
                type_name = DIETypeClassifier.get_type_name(die)
                logger.debug(f"Type at 0x{offset:x} ({type_name}, {die.tag}) requires resolution")
            else:
                type_name = DIETypeClassifier.get_type_name(die) or "<unnamed>"
                logger.debug(
                    f"Skipping type at 0x{offset:x} ({type_name}, {die.tag}) - "
                    f"doesn't require resolution"
                )

        return resolvable

    def get_type_name(self, offset: int) -> str | None:
        """Get type name for a DIE offset.

        Args:
            offset: DIE offset to look up

        Returns:
            Type name if found, None otherwise
        """
        die = self.dwarf_index.get_die_by_offset(offset)
        if die is None:
            return None

        return DIETypeClassifier.get_type_name(die)

    def is_simple_type(self, offset: int, class_info: ClassInfo) -> bool:
        """Check if a type is simple enough to include in hierarchy header.

        Simple types are small structures with few members that won't
        significantly bloat the header.

        Args:
            offset: DIE offset of the type
            class_info: ClassInfo for the type

        Returns:
            True if type is simple, False otherwise
        """
        # Small size and few members
        return class_info.byte_size <= 64 and len(class_info.members) <= 10

    # Private helper methods

    def _get_member_type_offset(self, member: MemberInfo) -> int | None:
        """Get type offset from a member.

        Args:
            member: MemberInfo to extract offset from

        Returns:
            Type offset if available, None otherwise
        """
        if member.opaque_storage_size is not None:
            return None
        if not hasattr(member, "type_offset") or member.type_offset is None:
            logger.debug(
                f"Member '{member.name}' has no type_offset (type_name: {member.type_name})"
            )
            return None

        return member.type_offset

    def _get_method_return_type_offset(self, method: MethodInfo) -> int | None:
        """Get return type offset from a method.

        Args:
            method: MethodInfo to extract offset from

        Returns:
            Return type offset if available, None otherwise
        """
        if not hasattr(method, "return_type_offset") or method.return_type_offset is None:
            # Constructors/destructors have no return type
            if not method.is_constructor and not method.is_destructor:
                logger.debug(
                    f"Method '{method.name}' has no return_type_offset "
                    f"(return_type: {method.return_type})"
                )
            return None

        return method.return_type_offset

    def _get_parameter_type_offset(self, param: object) -> int | None:
        """Get type offset from a parameter.

        Args:
            param: ParameterInfo to extract offset from

        Returns:
            Type offset if available, None otherwise
        """
        if not hasattr(param, "type_offset") or param.type_offset is None:
            param_name = getattr(param, "name", "<unknown>")
            param_type = getattr(param, "type_name", "<unknown>")
            logger.debug(f"Parameter '{param_name}' has no type_offset (type_name: {param_type})")
            return None

        # Cast to int to satisfy type checker
        return int(param.type_offset)

    def _extract_struct_dependencies(
        self, nested_struct: StructInfo, dependencies: set[int]
    ) -> None:
        """Extract dependencies from a nested struct.

        Args:
            nested_struct: StructInfo to extract from
            dependencies: Set to add offsets to
        """
        for member in nested_struct.members:
            offset = self._get_member_type_offset(member)
            if offset is not None:
                dependencies.add(offset)

    def _extract_union_dependencies(self, union: UnionInfo, dependencies: set[int]) -> None:
        """Extract dependencies from a union.

        Args:
            union: UnionInfo to extract from
            dependencies: Set to add offsets to
        """
        # Extract from union members
        for member in union.members:
            offset = self._get_member_type_offset(member)
            if offset is not None:
                dependencies.add(offset)

        # Extract from nested structs within union
        if hasattr(union, "nested_structs") and union.nested_structs:
            for nested_struct in union.nested_structs:
                self._extract_struct_dependencies(nested_struct, dependencies)
