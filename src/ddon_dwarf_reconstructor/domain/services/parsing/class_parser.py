#!/usr/bin/env python3

"""Class parsing logic for DWARF debug information.

This module handles parsing of DWARF class/struct types into ClassInfo objects,
including members, methods, enums, and nested types.
"""

from typing import TYPE_CHECKING

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE
from elftools.dwarf.dwarfinfo import DWARFInfo

from ....infrastructure.logging import get_logger, log_timing
from ...models.dwarf import (
    ClassInfo,
    EnumeratorInfo,
    EnumInfo,
    MemberInfo,
    MethodInfo,
    ParameterInfo,
    StructInfo,
    UnionInfo,
)

if TYPE_CHECKING:
    from ....core.lazy_type_resolver import LazyTypeResolver
    from ..lazy_dwarf_index_service import LazyDwarfIndexService

logger = get_logger(__name__)


class ClassParser:
    """Parses DWARF class information into structured ClassInfo objects.

    This class handles:
    - Class/struct definitions
    - Member variables (including anonymous unions)
    - Methods and parameters
    - Nested types (enums, structs, unions)
    - Inheritance relationships
    """

    def __init__(
        self,
        type_resolver: "LazyTypeResolver",
        dwarf_info: "DWARFInfo",
        lazy_index: "LazyDwarfIndexService | None" = None,
    ):
        """Initialize class parser with lazy type resolver and lazy index.

        Args:
            type_resolver: LazyTypeResolver instance for memory-efficient type name resolution
            dwarf_info: DWARF information structure
            lazy_index: Optional LazyDwarfIndex for memory-efficient lookups
        """
        self.type_resolver = type_resolver
        self.dwarf_info = dwarf_info
        self.lazy_index = lazy_index

    @log_timing
    def find_class(self, class_name: str) -> tuple[CompileUnit, DIE] | None:
        """Find a type DIE by name using lazy loading or full iteration.

        When lazy_index is available, uses memory-efficient offset-based lookups.
        Falls back to full DWARF iteration if lazy loading is unavailable.

        Supports classes, structs, unions, enums, typedefs, and arrays.
        Returns the first complete definition (with size > 0) found.
        Falls back to forward declaration if no complete definition exists.

        Args:
            class_name: Name of the class to find

        Returns:
            Tuple of (CompileUnit, DIE) if found, None otherwise
        """
        # Try lazy loading first (memory efficient)
        if self.lazy_index:
            result = self._find_class_lazy(class_name)
            if result:
                return result

        # Fall back to full iteration (memory intensive)
        return self._find_class_full_scan(class_name)

    def _find_class_full_scan(self, class_name: str) -> tuple[CompileUnit, DIE] | None:
        """Find class using full DWARF iteration (memory intensive fallback)."""
        target_name = class_name.encode("utf-8")
        fallback_candidate = None

        # Look for complete definition first (early exit on match)
        cu: CompileUnit
        for cu in self.dwarf_info.iter_CUs():  # type: ignore
            die: DIE
            for die in cu.iter_DIEs():  # type: ignore
                if die.is_null():  # type: ignore
                    continue

                if die.tag in (
                    "DW_TAG_class_type",
                    "DW_TAG_structure_type",
                    "DW_TAG_union_type",
                    "DW_TAG_enumeration_type",
                    "DW_TAG_typedef",
                    "DW_TAG_array_type",
                ):
                    name_attr = die.attributes.get("DW_AT_name")
                    if name_attr and name_attr.value == target_name:
                        # Check if this is a complete definition
                        size_attr = die.attributes.get("DW_AT_byte_size")
                        if size_attr and size_attr.value > 0:
                            logger.info(
                                f"Found {class_name} in CU at offset 0x{cu.cu_offset:x} "
                                f"(size: {size_attr.value} bytes)",
                            )
                            return cu, die
                        if die.has_children:
                            logger.info(
                                f"Found {class_name} in CU at offset 0x{cu.cu_offset:x} "
                                f"(has members)",
                            )
                            return cu, die
                        # Keep first forward declaration as fallback
                        if fallback_candidate is None:
                            fallback_candidate = (cu, die)

        # Return fallback if found
        if fallback_candidate:
            cu, die = fallback_candidate
            logger.info(
                f"Found {class_name} in CU at offset 0x{cu.cu_offset:x} (forward declaration)",
            )
            return cu, die

        logger.warning(f"Class {class_name} not found in DWARF info")
        return None

    def _find_class_lazy(self, class_name: str) -> tuple[CompileUnit, DIE] | None:
        """Find class using lazy loading for memory efficiency with CU optimization."""
        if not self.lazy_index:
            return None

        try:
            # Look for different type categories, checking cache first
            for symbol_type in ["class", "struct", "union", "enum", "typedef"]:
                # Check persistent cache first
                offset = self.lazy_index.find_symbol_offset(class_name, symbol_type)
                if offset is None:
                    # Fallback to targeted search if not in cache
                    offset = self.lazy_index.targeted_symbol_search(class_name, symbol_type)
                if offset:
                    # Find both DIE and CU in one search
                    die_cu_result = self._find_die_and_cu_by_offset(offset)
                    if die_cu_result:
                        cu, die = die_cu_result
                        logger.info(
                            f"Found {class_name} via lazy loading at offset 0x{offset:x} "
                            f"(type: {symbol_type})"
                        )
                        return cu, die

            logger.warning(f"Class {class_name} not found via lazy loading")
            return None

        except Exception as e:
            logger.warning(f"Lazy loading failed for {class_name}: {e}")
            return None

    def _find_die_and_cu_by_offset(self, offset: int) -> tuple[CompileUnit, DIE] | None:
        """Find both DIE and its containing CU by offset."""
        try:
            # Search for the CU containing this offset
            for cu in self.dwarf_info.iter_CUs():  # type: ignore
                cu_start = cu.cu_offset
                # Use header length instead of cu_length
                cu_end = cu_start + cu["unit_length"] + 4  # +4 for length field itself

                if cu_start <= offset < cu_end:
                    # Found the right CU, now find the DIE
                    for die in cu.iter_DIEs():  # type: ignore
                        if die.offset == offset:
                            return cu, die
                    break

            logger.warning(f"DIE not found at offset 0x{offset:x}")
            return None

        except Exception as e:
            logger.error(f"Error finding DIE and CU at offset 0x{offset:x}: {e}")
            return None

    @log_timing
    def parse_class_info(self, cu: CompileUnit, class_die: DIE) -> ClassInfo:
        """Parse class information using pyelftools methods.

        Args:
            cu: Compilation unit containing the class
            class_die: DIE representing the class

        Returns:
            ClassInfo object with all parsed information
        """
        # Get class name
        name_attr = class_die.attributes.get("DW_AT_name")
        class_name = name_attr.value.decode("utf-8") if name_attr else "unknown_class"

        logger.debug(f"Parsing class: {class_name}")

        # Get class size
        size_attr = class_die.attributes.get("DW_AT_byte_size")
        byte_size = size_attr.value if size_attr else 0

        # Get alignment information
        alignment_attr = class_die.attributes.get("DW_AT_alignment")
        alignment = alignment_attr.value if alignment_attr else None

        # Get declaration information
        declaration_file = self._get_declaration_file(cu, class_die)
        decl_line_attr = class_die.attributes.get("DW_AT_decl_line")
        declaration_line = decl_line_attr.value if decl_line_attr else None
        die_offset = class_die.offset

        members = []
        methods = []
        base_classes = []
        enums = []
        nested_structs = []
        unions = []
        processed_union_offsets: set[int] = (
            set()
        )  # Track anonymous unions to avoid double processing

        # Process class children
        child: DIE
        for child in class_die.iter_children():  # type: ignore
            if child.tag == "DW_TAG_member":
                # Check for anonymous union/struct
                member_result = self._parse_member_or_anonymous(
                    child,
                    class_name,
                    processed_union_offsets,
                )
                if isinstance(member_result, MemberInfo):
                    members.append(member_result)
                elif isinstance(member_result, UnionInfo):
                    unions.append(member_result)

            elif child.tag == "DW_TAG_subprogram":
                method = self.parse_method(child)
                if method:
                    methods.append(method)

            elif child.tag == "DW_TAG_inheritance":
                base_type = self.type_resolver.resolve_type_name(child)
                if base_type != "unknown_type":
                    base_classes.append(base_type)

            elif child.tag == "DW_TAG_enumeration_type":
                enum = self.parse_enum(child)
                if enum:
                    enums.append(enum)

            elif child.tag == "DW_TAG_structure_type":
                struct_info = self.parse_nested_structure(child)
                if struct_info:
                    nested_structs.append(struct_info)

            elif child.tag == "DW_TAG_union_type":
                # Skip unions already processed as anonymous members
                if child.offset not in processed_union_offsets:
                    union_info = self.parse_union(child)
                    if union_info:
                        unions.append(union_info)

            elif child.tag not in ["DW_TAG_typedef", "DW_TAG_class_type", "DW_TAG_array_type"]:
                # Log warning for unhandled tags
                child_name = child.attributes.get("DW_AT_name")
                child_name_str = child_name.value.decode("utf-8") if child_name else "unnamed"
                logger.warning(
                    f"Unhandled DWARF tag in class {class_name}: {child.tag} "
                    f"(name: {child_name_str}) at offset 0x{child.offset:x}",
                )

        return ClassInfo(
            name=class_name,
            byte_size=byte_size,
            members=members,
            methods=methods,
            base_classes=base_classes,
            enums=enums,
            nested_structs=nested_structs,
            unions=unions,
            alignment=alignment,
            declaration_file=declaration_file,
            declaration_line=declaration_line,
            die_offset=die_offset,
            packing_info=None,  # Will be calculated later
        )

    def _parse_member_or_anonymous(
        self,
        member_die: DIE,
        class_name: str,
        processed_offsets: set[int],
    ) -> MemberInfo | UnionInfo | None:
        """Parse member, detecting and handling anonymous unions.

        Args:
            member_die: DIE representing the member
            class_name: Name of containing class (for logging)
            processed_offsets: Set of already-processed union offsets

        Returns:
            MemberInfo for regular members, UnionInfo for anonymous unions, None to skip
        """
        name_attr = member_die.attributes.get("DW_AT_name")
        type_attr = member_die.attributes.get("DW_AT_type")

        # Check for anonymous union/struct
        if not name_attr and type_attr:
            try:
                type_die = member_die.get_DIE_from_attribute("DW_AT_type")
                if type_die and type_die.tag == "DW_TAG_union_type":
                    # Anonymous union
                    union_info = self.parse_union(type_die)
                    if union_info:
                        processed_offsets.add(type_die.offset)
                        logger.debug(
                            f"Found anonymous union in {class_name}: "
                            f"({union_info.byte_size} bytes)",
                        )
                        return union_info
            except Exception as e:
                logger.debug(f"Failed to resolve anonymous member type: {e}")

        # Regular member
        return self.parse_member(member_die)

    def parse_member(self, member_die: DIE) -> MemberInfo | None:
        """Parse a class member using pyelftools.

        Args:
            member_die: DIE representing the member

        Returns:
            MemberInfo object if valid, None otherwise
        """
        # Resolve member type first
        type_name = self.type_resolver.resolve_type_name(member_die)

        # Get member name (handle anonymous members)
        name_attr = member_die.attributes.get("DW_AT_name")
        if name_attr:
            member_name = name_attr.value.decode("utf-8")
        elif "union" in type_name.lower() or "struct" in type_name.lower():
            member_name = ""  # Anonymous member
        else:
            return None

        # Check if static/external
        is_external = member_die.attributes.get("DW_AT_external") is not None
        is_declaration = member_die.attributes.get("DW_AT_declaration") is not None
        is_static = is_external and is_declaration

        # Get const value if present
        const_value = None
        const_attr = member_die.attributes.get("DW_AT_const_value")
        if const_attr:
            const_value = const_attr.value

        # Get member offset
        offset = None
        offset_attr = member_die.attributes.get("DW_AT_data_member_location")
        if offset_attr:
            offset = offset_attr.value

        # Special handling for vtable pointers
        if member_name.startswith("_vptr$") and (
            type_name == "unknown_type" or "__vtbl_ptr_type" in type_name
        ):
            logger.info(f"Applying vtable pointer fallback for {member_name}")
            type_name = "void*"

        return MemberInfo(
            name=member_name,
            type_name=type_name,
            offset=offset,
            is_static=is_static,
            is_const=const_value is not None,
            const_value=const_value,
        )

    def parse_method(self, method_die: DIE) -> MethodInfo | None:
        """Parse a class method using pyelftools.

        Args:
            method_die: DIE representing the method

        Returns:
            MethodInfo object if valid, None otherwise
        """
        # Get method name
        name_attr = method_die.attributes.get("DW_AT_name")
        if not name_attr:
            return None
        method_name = name_attr.value.decode("utf-8")

        # Get return type
        return_type = self.type_resolver.resolve_type_name(method_die)

        # Check if virtual
        is_virtual = method_die.attributes.get("DW_AT_virtuality") is not None

        # Get vtable index if virtual
        vtable_index = None
        if is_virtual:
            vtable_attr = method_die.attributes.get("DW_AT_vtable_elem_location")
            if vtable_attr:
                vtable_index = 0  # Simplified - full implementation would parse expression

        # Check if constructor/destructor
        parent_die = method_die.get_parent()
        parent_name = ""
        if parent_die and "DW_AT_name" in parent_die.attributes:
            parent_name_attr = parent_die.attributes["DW_AT_name"]
            if isinstance(parent_name_attr.value, bytes):
                parent_name = parent_name_attr.value.decode("utf-8", errors="ignore")
            else:
                parent_name = str(parent_name_attr.value)

        is_constructor = method_name == parent_name
        is_destructor = method_name.startswith("~")

        # Parse parameters
        parameters = []
        for child in method_die.iter_children():
            if child.tag == "DW_TAG_formal_parameter":
                param = self.parse_parameter(child)
                if param:
                    parameters.append(param)

        return MethodInfo(
            name=method_name,
            return_type=return_type,
            parameters=parameters,
            is_virtual=is_virtual,
            vtable_index=vtable_index,
            is_constructor=is_constructor,
            is_destructor=is_destructor,
        )

    def parse_parameter(self, param_die: DIE) -> ParameterInfo | None:
        """Parse a function parameter using pyelftools.

        Args:
            param_die: DIE representing the parameter

        Returns:
            ParameterInfo object
        """
        # Check if artificial (like 'this' pointer)
        is_artificial = param_die.attributes.get("DW_AT_artificial") is not None

        # Get parameter name
        name_attr = param_die.attributes.get("DW_AT_name")
        param_name = name_attr.value.decode("utf-8") if name_attr else "param"

        # Get parameter type
        param_type = self.type_resolver.resolve_type_name(param_die)

        # Get default value if present
        default_value = None
        const_attr = param_die.attributes.get("DW_AT_default_value")
        if const_attr:
            default_value = str(const_attr.value)

        # Mark artificial parameters for filtering
        if is_artificial:
            param_name = "__artificial__"

        return ParameterInfo(name=param_name, type_name=param_type, default_value=default_value)

    def parse_enum(self, enum_die: DIE) -> EnumInfo | None:
        """Parse an enumeration using pyelftools.

        Args:
            enum_die: DIE representing the enum

        Returns:
            EnumInfo object if valid, None otherwise
        """
        # Get enum name
        name_attr = enum_die.attributes.get("DW_AT_name")
        enum_name = name_attr.value.decode("utf-8") if name_attr else "unknown_enum"

        # Get enum size
        size_attr = enum_die.attributes.get("DW_AT_byte_size")
        byte_size = size_attr.value if size_attr else 4

        # Parse enumerators
        enumerators = []
        for child in enum_die.iter_children():
            if child.tag == "DW_TAG_enumerator":
                enumerator = self._parse_enumerator(child)
                if enumerator:
                    enumerators.append(enumerator)

        return EnumInfo(
            name=enum_name,
            byte_size=byte_size,
            enumerators=enumerators,
        )

    def _parse_enumerator(self, enumerator_die: DIE) -> EnumeratorInfo | None:
        """Parse an enumerator value."""
        name_attr = enumerator_die.attributes.get("DW_AT_name")
        if not name_attr:
            return None
        enumerator_name = name_attr.value.decode("utf-8")

        value_attr = enumerator_die.attributes.get("DW_AT_const_value")
        if not value_attr:
            return None

        value = value_attr.value
        if isinstance(value, bytes):
            value = int.from_bytes(value, byteorder="little", signed=True) if len(value) <= 8 else 0
        elif not isinstance(value, int):
            try:
                value = int(value)
            except (ValueError, TypeError):
                value = 0

        return EnumeratorInfo(name=enumerator_name, value=value)

    def parse_nested_structure(self, struct_die: DIE) -> StructInfo | None:
        """Parse a nested structure definition.

        Args:
            struct_die: DIE representing the struct

        Returns:
            StructInfo object if valid, None otherwise
        """
        # Get structure name (can be None for anonymous structs)
        name_attr = struct_die.attributes.get("DW_AT_name")
        struct_name = None
        if name_attr:
            struct_name = (
                name_attr.value.decode("utf-8")
                if isinstance(name_attr.value, bytes)
                else str(name_attr.value)
            )

        # Get structure size
        size_attr = struct_die.attributes.get("DW_AT_byte_size")
        struct_size = size_attr.value if size_attr else 0

        # Parse members
        members = []
        for child in struct_die.iter_children():
            if child.tag == "DW_TAG_member":
                member = self.parse_member(child)
                if member:
                    members.append(member)

        return StructInfo(
            name=struct_name,
            byte_size=struct_size,
            members=members,
            die_offset=struct_die.offset,
        )

    def parse_union(self, union_die: DIE) -> UnionInfo | None:
        """Parse a union definition.

        Args:
            union_die: DIE representing the union

        Returns:
            UnionInfo object if valid, None otherwise
        """
        # Get union name (might be None for anonymous unions)
        name_attr = union_die.attributes.get("DW_AT_name")
        union_name = name_attr.value.decode("utf-8") if name_attr else ""

        # Get union size
        size_attr = union_die.attributes.get("DW_AT_byte_size")
        union_size = size_attr.value if size_attr else 0

        # Parse members and nested structs
        members = []
        nested_structs = []

        for child in union_die.iter_children():
            if child.tag == "DW_TAG_member":
                member = self.parse_member(child)
                if member:
                    members.append(member)

            elif child.tag == "DW_TAG_structure_type":
                # Handle anonymous structs within unions
                struct_info = self.parse_nested_structure(child)
                if struct_info:
                    nested_structs.append(struct_info)

        return UnionInfo(
            name=union_name,
            byte_size=union_size,
            members=members,
            nested_structs=nested_structs,
            die_offset=union_die.offset,
        )

    def _get_declaration_file(self, cu: CompileUnit, die: DIE) -> str | None:
        """Get declaration file name from line program."""
        decl_file_attr = die.attributes.get("DW_AT_decl_file")
        if not decl_file_attr:
            return None

        try:
            line_program = self.dwarf_info.line_program_for_CU(cu)
            if line_program and decl_file_attr.value < len(line_program.header.file_entry):
                file_entry = line_program.header.file_entry[decl_file_attr.value - 1]
                return (
                    file_entry.name.decode("utf-8")
                    if hasattr(file_entry.name, "decode")
                    else str(file_entry.name)
                )
        except Exception:
            pass

        return None

    def build_inheritance_hierarchy(self, class_name: str) -> list[str]:
        """Build complete inheritance hierarchy for a class.

        Args:
            class_name: Name of the class to build hierarchy for

        Returns:
            List of base class names from root to derived
        """
        hierarchy = []
        current_class = class_name
        visited = set()  # Prevent infinite loops

        while current_class and current_class not in visited:
            visited.add(current_class)
            result = self.find_class(current_class)
            if not result:
                break

            cu, class_die = result
            # Look for inheritance
            for child in class_die.iter_children():
                if child.tag == "DW_TAG_inheritance":
                    base_type = self.type_resolver.resolve_type_name(child)
                    if base_type != "unknown_type":
                        hierarchy.append(base_type)
                        current_class = base_type
                        break
            else:
                # No inheritance found
                break

        return list(reversed(hierarchy))  # Return from base to derived
