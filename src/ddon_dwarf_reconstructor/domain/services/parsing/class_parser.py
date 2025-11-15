#!/usr/bin/env python3

"""Class parsing logic for DWARF debug information.

This module handles parsing of DWARF class/struct types into ClassInfo objects,
including members, methods, enums, and nested types.
"""

import time
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
    TemplateTypeParam,
    TemplateValueParam,
    UnionInfo,
)
from ddon_dwarf_reconstructor.generators.utils.dwarf_location_parser import parse_location_offset
from .type_chain_traverser import TypeChainTraverser

if TYPE_CHECKING:
    from ....core.lazy_type_resolver import LazyTypeResolver
    from ..lazy_dwarf_index_service import LazyDwarfIndexService

logger = get_logger(__name__)

# Blacklist of known external/system types that typically lack debug info
# These types will skip expensive full DWARF scans to prevent long search times
TYPE_BLACKLIST = {
    # POSIX/pthread types
    "pthread_mutex",
    "pthread_mutex_t",
    "pthread_cond",
    "pthread_cond_t",
    "pthread_rwlock_t",
    "pthread_attr_t",
    # Standard C library types
    "FILE",
    "_IO_FILE",
    # Compiler builtins
    "__va_list_tag",
    "__builtin_va_list",
}


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
        full_scan_timeout: float = 180.0,
    ):
        """Initialize class parser with lazy type resolver and lazy index.

        Args:
            type_resolver: LazyTypeResolver instance for memory-efficient type name resolution
            dwarf_info: DWARF information structure
            lazy_index: Optional LazyDwarfIndex for memory-efficient lookups
            full_scan_timeout: Maximum seconds for full DWARF scan (default: 180s)
        """
        self.type_resolver = type_resolver
        self.dwarf_info = dwarf_info
        self.lazy_index = lazy_index
        self.full_scan_timeout = full_scan_timeout
        self.timed_out_symbols: set[str] = set()  # Track symbols that timed out

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
        # Check blacklist first to avoid expensive scans for known unresolvable types
        if class_name in TYPE_BLACKLIST:
            logger.warning(
                f"Type '{class_name}' is blacklisted (known external/system type). "
                f"Skipping search to avoid performance issues."
            )
            return None
        
        # Try lazy loading first (memory efficient)
        if self.lazy_index:
            result = self._find_class_lazy(class_name)
            if result:
                return result

        # Fall back to full iteration (memory intensive)
        return self._find_class_full_scan(class_name)

    def _find_class_full_scan(self, class_name: str) -> tuple[CompileUnit, DIE] | None:
        """Find class using full DWARF iteration (memory intensive fallback).
        
        Searches all compilation units for the best match, preferring complete definitions
        over forward declarations. Uses scoring algorithm based on DWARF4 spec:
        - Forward declarations (DW_AT_declaration): heavily penalized
        - Has members (has_children): strongly preferred
        - Has byte_size: preferred, scaled by size
        - Early exit optimization: returns immediately if perfect match found
          (has_children + size>0 + no declaration)
        - Timeout protection: aborts after full_scan_timeout seconds
        """
        target_name = class_name.encode("utf-8")
        fallback_candidate = None
        best_candidate = None
        best_score = -1
        best_cu = None
        
        # Track time to prevent indefinite searches
        start_time = time.time()
        timed_out = False
        candidates_found = 0

        # Look for best definition across all CUs
        cu: CompileUnit
        for cu in self.dwarf_info.iter_CUs():  # type: ignore
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > self.full_scan_timeout:
                timed_out = True
                logger.error(
                    f"Full DWARF scan for '{class_name}' timed out after {elapsed:.1f}s. "
                    f"Searched {candidates_found} candidates. This type may lack debug information. "
                    f"Consider adding to blacklist if issue persists."
                )
                self.timed_out_symbols.add(class_name)
                break
            
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
                        candidates_found += 1
                        
                        # Check for forward declaration (DWARF4 spec: incomplete types
                        # have DW_AT_declaration attribute and no byte_size)
                        decl_attr = die.attributes.get("DW_AT_declaration")
                        is_declaration = decl_attr is not None
                        
                        # Evaluate completeness
                        size_attr = die.attributes.get("DW_AT_byte_size")
                        has_size = size_attr and size_attr.value > 0
                        has_members = die.has_children
                        
                        # Calculate completeness score with type-specific handling:
                        # - Typedefs, base types, enums: complete if not declarations
                        # - Classes/structs: prefer those with members and size
                        score = 0
                        
                        if is_declaration:
                            score = -1000  # Forward declaration
                        elif die.tag == "DW_TAG_typedef":
                            # Typedefs are complete if they have a DW_AT_type attribute
                            type_attr = die.attributes.get("DW_AT_type")
                            if type_attr:
                                score = 5000  # Complete typedef
                            else:
                                score = -500  # Incomplete typedef
                        elif die.tag == "DW_TAG_base_type":
                            # Base types are always complete
                            score = 8000  # High priority
                        elif die.tag == "DW_TAG_enumeration_type":
                            # Enums are complete if they have size
                            if has_size:
                                score = 6000  # Complete enum
                            else:
                                score = -500  # Incomplete enum
                        else:
                            # Classes/structs/unions: use member-based scoring
                            if has_size:
                                score += size_attr.value if size_attr else 0
                            if has_members:
                                score += 10000
                        
                        logger.debug(
                            f"Found candidate {class_name} at DIE 0x{die.offset:x} "
                            f"(CU 0x{cu.cu_offset:x}): score={score}, "
                            f"size={size_attr.value if size_attr else 0}, "
                            f"has_children={has_members}, is_declaration={is_declaration}, "
                            f"tag={die.tag}"
                        )
                        
                        if score > best_score:
                            best_score = score
                            best_candidate = die
                            best_cu = cu
                        
                        # Keep first match as ultimate fallback
                        if fallback_candidate is None:
                            fallback_candidate = (cu, die)
                        
                        # Early exit optimization: if we found a perfect match
                        # (classes with members, typedefs, base types, or enums)
                        if (has_members and has_size and not is_declaration) or score >= 5000:
                            size_str = f"{size_attr.value} bytes" if size_attr else "no size"
                            logger.info(
                                f"Found {class_name} in CU at offset 0x{cu.cu_offset:x} "
                                f"(perfect match: size={size_str}, has_children={has_members}, "
                                f"score={score})"
                            )
                            return cu, die

        # Return best candidate if found
        if best_candidate and best_score > 0:
            size_attr = best_candidate.attributes.get("DW_AT_byte_size")
            size_value = size_attr.value if size_attr else 0
            has_members = best_candidate.has_children
            
            # MTFramework heuristic: warn if class has no members
            # Most MT classes have at least a vtable pointer
            if not has_members and size_value > 0:
                logger.warning(
                    f"Found {class_name} with size={size_value} bytes but no members. "
                    f"This is unusual for MTFramework classes. Possible edge case of "
                    f"parent->child inheritance with no new members added."
                )
            
            logger.info(
                f"Found {class_name} in CU at offset 0x{best_cu.cu_offset:x} "
                f"(best match: size={size_value} bytes, has_children={has_members}, "
                f"score={best_score})"
            )
            return best_cu, best_candidate
        
        # If timed out, return best candidate found so far (even if incomplete)
        if timed_out and fallback_candidate:
            cu, die = fallback_candidate
            logger.warning(
                f"Returning partial result for {class_name} after timeout. "
                f"Best candidate at CU 0x{cu.cu_offset:x} with score={best_score}. "
                f"Result may be incomplete."
            )
            return cu, die
        
        # Warn if only forward declaration found
        if fallback_candidate:
            cu, die = fallback_candidate
            logger.warning(
                f"Found {class_name} in CU at offset 0x{cu.cu_offset:x} "
                f"but only as forward declaration (score={best_score}). "
                f"This may indicate missing debug information."
            )
            return cu, die

        logger.warning(f"Class {class_name} not found in DWARF info")
        return None
        if fallback_candidate:
            cu, die = fallback_candidate
            logger.warning(
                f"Found {class_name} in CU at offset 0x{cu.cu_offset:x} "
                f"but only as forward declaration (score={best_score}). "
                f"This may indicate missing debug information."
            )
            return cu, die

        logger.warning(f"Class {class_name} not found in DWARF info")
        return None

    def _find_class_lazy(self, class_name: str) -> tuple[CompileUnit, DIE] | None:
        """Find class using lazy loading for memory efficiency with CU optimization.
        
        Validates cached results to ensure they point to complete definitions,
        not forward declarations. Falls back to targeted search, then full scan
        if cached entry is invalid.
        """
        if not self.lazy_index:
            return None

        try:
            # Try cache first - simple symbol name lookup
            offset = self.lazy_index.find_symbol_offset(class_name)
            if offset:
                # Found in cache, retrieve it
                die_cu_result = self._find_die_and_cu_by_offset(offset)
                if die_cu_result:
                    cu, die = die_cu_result
                    
                    # Validate that cached entry is not a forward declaration
                    # (DWARF4 spec: incomplete types have DW_AT_declaration attribute)
                    decl_attr = die.attributes.get("DW_AT_declaration")
                    is_declaration = decl_attr is not None
                    
                    if is_declaration:
                        logger.warning(
                            f"Cached entry for {class_name} at offset 0x{offset:x} "
                            f"is a forward declaration. Trying targeted search for complete definition."
                        )
                        # Don't fall back to full scan yet - try targeted search first
                        # (targeted search will check all CUs with timeout protection)
                    else:
                        # Log cache hit with completeness info
                        size_attr = die.attributes.get("DW_AT_byte_size")
                        has_members = die.has_children
                        logger.info(
                            f"Found {class_name} via cache at offset 0x{offset:x} "
                            f"(size={size_attr.value if size_attr else 0}, "
                            f"has_children={has_members})"
                        )
                        return cu, die

            # Not in cache or cache had forward declaration - do targeted search
            # This searches through CUs with scoring and timeout protection
            offset = self.lazy_index.targeted_symbol_search(class_name)
            if offset:
                die_cu_result = self._find_die_and_cu_by_offset(offset)
                if die_cu_result:
                    cu, die = die_cu_result
                    
                    # Validate targeted search result
                    decl_attr = die.attributes.get("DW_AT_declaration")
                    is_declaration = decl_attr is not None
                    
                    if is_declaration:
                        logger.warning(
                            f"Targeted search found forward declaration for {class_name} "
                            f"at offset 0x{offset:x}. This likely means no complete definition exists."
                        )
                        # Return the forward declaration - it's better than nothing
                        # The full scan would also time out finding the same thing
                        return cu, die
                    
                    # Determine what type we actually found
                    tag = str(die.tag) if die.tag else "unknown"
                    if tag == "DW_TAG_namespace":
                        symbol_type = "namespace"
                    elif tag in ("DW_TAG_class_type", "DW_TAG_structure_type"):
                        symbol_type = "class"
                    elif tag == "DW_TAG_typedef":
                        symbol_type = "typedef"
                    else:
                        symbol_type = "type"

                    size_attr = die.attributes.get("DW_AT_byte_size")
                    logger.info(
                        f"Found {class_name} via lazy loading at offset 0x{offset:x} "
                        f"(type: {symbol_type}, size={size_attr.value if size_attr else 0})"
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
        template_type_params = []
        template_value_params = []
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

            elif child.tag == "DW_TAG_template_type_param":
                template_type_param = self.parse_template_type_param(child)
                if template_type_param:
                    template_type_params.append(template_type_param)

            elif child.tag == "DW_TAG_template_value_param":
                template_value_param = self.parse_template_value_param(child)
                if template_value_param:
                    template_value_params.append(template_value_param)

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
            cu_offset=cu.cu_offset,
            packing_info=None,  # Will be calculated later
            template_type_params=template_type_params,
            template_value_params=template_value_params,
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
        # Resolve member type first (for display)
        type_name = self.type_resolver.resolve_type_name(member_die)

        # Capture terminal type offset for dependency resolution
        type_offset = TypeChainTraverser.get_terminal_type_offset(member_die)
        if type_offset:
            logger.debug(
                f"Captured type offset 0x{type_offset:x} for member type '{type_name}'"
            )

        # Get member name (handle anonymous members)
        name_attr = member_die.attributes.get("DW_AT_name")
        if name_attr:
            member_name = name_attr.value.decode("utf-8")
        elif "union_type" in type_name or "structure_type" in type_name:
            # Skip unnamed unions/structs - they should be handled by _parse_member_or_anonymous
            logger.debug(f"Skipping unnamed union/struct member: {type_name}")
            return None
        elif "union" in type_name.lower() or "struct" in type_name.lower():
            member_name = ""  # Anonymous member with a proper type name
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
            offset = parse_location_offset(offset_attr.value)

        # Special handling for vtable pointers
        if member_name.startswith("_vptr$") and (
            type_name == "unknown_type" or "__vtbl_ptr_type" in type_name
        ):
            logger.info(f"Applying vtable pointer fallback for {member_name}")
            type_name = "void*"

        return MemberInfo(
            name=member_name,
            type_name=type_name,
            type_offset=type_offset,  # NEW: Store terminal type offset
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

        # Get return type (for display)
        return_type = self.type_resolver.resolve_type_name(method_die)

        # Capture terminal return type offset for dependency resolution
        return_type_offset = TypeChainTraverser.get_terminal_type_offset(method_die)
        if return_type_offset:
            logger.debug(
                f"Captured return type offset 0x{return_type_offset:x} for method "
                f"'{method_name}' returning '{return_type}'"
            )

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
            return_type_offset=return_type_offset,  # Store terminal type offset
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

        # Get parameter type (for display)
        param_type = self.type_resolver.resolve_type_name(param_die)

        # Capture terminal type offset for dependency resolution
        type_offset = TypeChainTraverser.get_terminal_type_offset(param_die)
        if type_offset:
            logger.debug(
                f"Captured type offset 0x{type_offset:x} for parameter '{param_name}': "
                f"'{param_type}'"
            )

        # Get default value if present
        default_value = None
        const_attr = param_die.attributes.get("DW_AT_default_value")
        if const_attr:
            default_value = str(const_attr.value)

        # Mark artificial parameters for filtering
        if is_artificial:
            param_name = "__artificial__"

        return ParameterInfo(
            name=param_name,
            type_name=param_type,
            type_offset=type_offset,  # Store terminal type offset
            default_value=default_value,
        )

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

    def parse_template_type_param(self, param_die: DIE) -> TemplateTypeParam | None:
        """Parse template type parameter (typename T or class T).

        Args:
            param_die: DIE representing the template type parameter

        Returns:
            TemplateTypeParam object if valid, None otherwise

        Examples:
            template <typename T>        -> TemplateTypeParam(name='T')
            template <class U = int>     -> TemplateTypeParam(name='U', default_type='int')
        """
        # Get parameter name
        name_attr = param_die.attributes.get("DW_AT_name")
        if not name_attr:
            logger.debug(f"Template type parameter at 0x{param_die.offset:x} has no name")
            return None

        param_name = (
            name_attr.value.decode("utf-8")
            if isinstance(name_attr.value, bytes)
            else str(name_attr.value)
        )

        # Check for default type
        default_type = None
        if "DW_AT_type" in param_die.attributes:
            default_type = self.type_resolver.resolve_type_name(param_die)
            logger.debug(
                f"Template type parameter '{param_name}' has default type: {default_type}"
            )

        logger.debug(f"Parsed template type parameter: {param_name}")
        return TemplateTypeParam(name=param_name, default_type=default_type)

    def parse_template_value_param(self, param_die: DIE) -> TemplateValueParam | None:
        """Parse template value parameter (non-type template parameter).

        Args:
            param_die: DIE representing the template value parameter

        Returns:
            TemplateValueParam object if valid, None otherwise

        Examples:
            template <int N>             -> TemplateValueParam(name='N', type_name='int')
            template <size_t Size = 10>  -> TemplateValueParam(name='Size', type_name='size_t', default_value=10)
        """
        # Get parameter name
        name_attr = param_die.attributes.get("DW_AT_name")
        if not name_attr:
            logger.debug(f"Template value parameter at 0x{param_die.offset:x} has no name")
            return None

        param_name = (
            name_attr.value.decode("utf-8")
            if isinstance(name_attr.value, bytes)
            else str(name_attr.value)
        )

        # Get parameter type
        param_type = self.type_resolver.resolve_type_name(param_die)
        if param_type == "unknown_type":
            param_type = "int"  # Fallback to int

        # Check for default value
        default_value = None
        const_attr = param_die.attributes.get("DW_AT_const_value")
        if const_attr:
            default_value = const_attr.value
            logger.debug(
                f"Template value parameter '{param_name}' has default value: {default_value}"
            )

        logger.debug(f"Parsed template value parameter: {param_name} ({param_type})")
        return TemplateValueParam(
            name=param_name, type_name=param_type, default_value=default_value
        )
