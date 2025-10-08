#!/usr/bin/env python3

"""DWARF-to-C++ header generator using pyelftools.

This module uses pyelftools directly, reusing their proven API and data structures
without reinventing DWARF parsing. It generates C++ headers from DWARF debug information.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.die import DIE
from elftools.elf.elffile import ELFFile

from ..utils.elf_patches import patch_pyelftools_for_ps4

# Apply PS4 ELF patches
patch_pyelftools_for_ps4()

logger = logging.getLogger(__name__)


@dataclass
class MemberInfo:
    """Information about a class member."""

    name: str
    type_name: str
    offset: int | None = None
    is_static: bool = False
    is_const: bool = False
    const_value: int | None = None


@dataclass
class ParameterInfo:
    """Information about a method parameter."""

    name: str
    type_name: str
    default_value: str | None = None


@dataclass
class EnumeratorInfo:
    """Information about an enum value."""

    name: str
    value: int


@dataclass
class EnumInfo:
    """Information about an enumeration."""

    name: str
    byte_size: int
    enumerators: list[EnumeratorInfo]
    declaration_file: str | None = None
    declaration_line: int | None = None


@dataclass
class MethodInfo:
    """Information about a class method."""

    name: str
    return_type: str
    parameters: list[ParameterInfo] | None = None
    is_virtual: bool = False
    vtable_index: int | None = None
    is_constructor: bool = False
    is_destructor: bool = False

    def __post_init__(self) -> None:
        if self.parameters is None:
            self.parameters = []


@dataclass
class StructInfo:
    """Information about a nested structure."""

    name: str
    byte_size: int
    members: list[MemberInfo]
    die_offset: int | None = None


@dataclass
class UnionInfo:
    """Information about a union."""

    name: str
    byte_size: int
    members: list[MemberInfo]
    nested_structs: list["StructInfo"]
    die_offset: int | None = None


@dataclass
class ClassInfo:
    """Information about a class or struct."""

    name: str
    byte_size: int
    members: list[MemberInfo]
    methods: list[MethodInfo]
    base_classes: list[str]
    enums: list[EnumInfo]
    nested_structs: list[StructInfo]
    unions: list[UnionInfo]
    alignment: int | None = None
    declaration_file: str | None = None
    declaration_line: int | None = None
    die_offset: int | None = None
    packing_info: dict[str, int] | None = None  # packing, padding, alignment hints


class DwarfGenerator:
    """DWARF-to-C++ header generator using pyelftools."""

    def __init__(self, elf_path: Path):
        """Initialize with ELF file path."""
        self.elf_path = elf_path
        self.elf_file: ELFFile | None = None
        self.dwarf_info = None

    def __enter__(self) -> "DwarfGenerator":
        """Context manager entry."""
        self.file_handle = open(self.elf_path, "rb")
        self.elf_file = ELFFile(self.file_handle)

        if not self.elf_file.has_dwarf_info():
            raise ValueError(f"No DWARF info found in {self.elf_path}")

        self.dwarf_info = self.elf_file.get_dwarf_info()
        return self

    def __exit__(self, exc_type: type, exc_val: Exception, exc_tb: object) -> None:
        """Context manager exit."""
        if hasattr(self, "file_handle"):
            self.file_handle.close()

    def find_class(self, class_name: str) -> tuple[CompileUnit, DIE] | None:
        """Find a type DIE by name using pyelftools iteration.

        Supports classes, structs, unions, enums, typedefs, and arrays.
        Returns the first complete definition (with size > 0) found.
        Falls back to forward declaration if no complete definition exists.
        """
        target_name = class_name.encode("utf-8")
        fallback_candidate = None

        if self.dwarf_info is None:
            raise ValueError("DWARF info not initialized. Use within context manager.")

        # Look for complete definition first (early exit on match)
        for cu in self.dwarf_info.iter_CUs():
            for die in cu.iter_DIEs():
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

        return None

    def build_inheritance_hierarchy(self, class_name: str) -> list[str]:
        """Build complete inheritance hierarchy for a class."""
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
                    base_type = self.resolve_type_name(child)
                    if base_type != "unknown_type":
                        hierarchy.append(base_type)
                        current_class = base_type
                        break
            else:
                # No inheritance found
                break

        return list(reversed(hierarchy))  # Return from base to derived

    def calculate_packing_info(self, class_info: ClassInfo) -> dict[str, int]:
        """Calculate packing and alignment information from member layout."""
        packing_info = {
            "suggested_packing": 1,  # Default to byte-aligned
            "total_padding": 0,
            "natural_size": 0,
            "actual_size": class_info.byte_size,
        }

        if not class_info.members:
            return packing_info

        # Sort members by offset
        sorted_members = sorted(
            [m for m in class_info.members if m.offset is not None], key=lambda m: m.offset or 0,
        )

        if not sorted_members:
            return packing_info

        # Calculate natural size and padding
        natural_size = 0
        total_padding = 0
        last_offset: int | None = 0
        last_size = 0

        # Estimate member sizes based on common C++ types
        type_sizes = {
            "bool": 1,
            "char": 1,
            "u8": 1,
            "s8": 1,
            "u16": 2,
            "s16": 2,
            "short": 2,
            "u32": 4,
            "s32": 4,
            "int": 4,
            "float": 4,
            "u64": 8,
            "s64": 8,
            "long": 8,
            "double": 8,
            "void*": 8,
            "ptr": 8,  # Assume 64-bit pointers
        }

        for i, member in enumerate(sorted_members):
            # Estimate member size
            lookup_size = type_sizes.get(member.type_name.replace("*", "ptr"))
            member_size: int = lookup_size if lookup_size is not None else 8
            if "*" in member.type_name:
                member_size = 8  # Pointer
            elif member.type_name.startswith("Mt"):
                member_size = 8  # Assume objects are at least pointer-sized

            if i > 0 and last_offset is not None and member.offset is not None:
                expected_offset = last_offset + last_size
                actual_offset = member.offset
                padding = actual_offset - expected_offset
                if padding > 0:
                    total_padding += padding

            natural_size += member_size
            last_offset = member.offset
            last_size = member_size

        # Calculate final padding (tail padding)
        if sorted_members:
            last_member = sorted_members[-1]
            if last_member.offset is not None:
                last_member_end = last_member.offset + last_size
            tail_padding = class_info.byte_size - last_member_end
            if tail_padding > 0:
                total_padding += tail_padding

        packing_info["natural_size"] = natural_size
        packing_info["total_padding"] = total_padding

        # Determine suggested packing
        if total_padding == 0:
            packing_info["suggested_packing"] = 1  # Maximally packed
        elif total_padding <= class_info.byte_size * 0.1:  # Less than 10% padding
            packing_info["suggested_packing"] = 4  # 4-byte aligned
        else:
            packing_info["suggested_packing"] = 8  # 8-byte aligned (default)

        return packing_info

    def find_typedef(self, typedef_name: str) -> tuple[str, str] | None:
        """Find a typedef definition by name for primitive types only.

        Returns (typedef_name, underlying_type) if found, None otherwise.
        Only searches for common primitive typedefs to avoid performance issues.
        """
        # Only search for commonly used primitive typedefs
        primitive_typedefs = {"u8", "u16", "u32", "u64", "s8", "s16", "s32", "s64", "f32", "f64"}

        if typedef_name not in primitive_typedefs:
            logging.debug(f"Skipping typedef lookup for non-primitive type: {typedef_name}")
            return None

        logging.debug(f"Searching for typedef: {typedef_name}")
        target_name = typedef_name.encode("utf-8")

        if self.dwarf_info is None:
            raise ValueError("DWARF info not initialized. Use within context manager.")

        cu_count = 0
        die_count = 0

        for cu in self.dwarf_info.iter_CUs():
            cu_count += 1
            logging.debug(
                f"Searching CU #{cu_count} at offset 0x{cu.cu_offset:x} for typedef {typedef_name}",
            )

            for die in cu.iter_DIEs():
                die_count += 1
                if die.tag == "DW_TAG_typedef":
                    name_attr = die.attributes.get("DW_AT_name")
                    if name_attr and name_attr.value == target_name:
                        logging.debug(
                            f"Found typedef {typedef_name} at DIE offset 0x{die.offset:x} "
                            f"in CU #{cu_count}",
                        )
                        # Get the underlying type
                        underlying_type = self.resolve_type_name(die)
                        logging.debug(f"Typedef {typedef_name} resolves to: {underlying_type}")
                        return typedef_name, underlying_type

        logging.debug(
            f"Typedef {typedef_name} not found after searching {cu_count} CUs and {die_count} DIEs",
        )
        return None

    def collect_used_typedefs(self, class_info: ClassInfo) -> dict[str, str]:
        """Collect only the typedefs that are actually used by this class."""
        logging.debug(f"Collecting used typedefs for class: {class_info.name}")
        used_typedefs = {}

        # Check all member types
        logging.debug(f"Checking {len(class_info.members)} members for typedef usage")
        for member in class_info.members:
            # Extract base type name from complex types
            type_name = member.type_name
            logging.debug(f"Member {member.name} has raw type: {type_name}")
            if type_name.startswith("const "):
                type_name = type_name[6:].strip()
            if type_name.endswith("*"):
                type_name = type_name[:-1].strip()
            if type_name.endswith("&"):
                type_name = type_name[:-1].strip()

            # Handle array types - extract base type from array notation
            if "[" in type_name and "]" in type_name:
                base_type = type_name.split("[")[0].strip()
                logging.debug(f"Extracted base type from array: {base_type}")
                type_name = base_type

            logging.debug(f"Cleaned member type: {type_name}")

            # Try to find as typedef
            result = self.find_typedef(type_name)
            if result:
                typedef_name, underlying_type = result
                used_typedefs[typedef_name] = underlying_type
                logging.debug(
                    f"Found typedef for member {member.name}: {typedef_name} -> {underlying_type}",
                )

        # Check method return types and parameters
        logging.debug(f"Checking {len(class_info.methods)} methods for typedef usage")
        for method in class_info.methods:
            # Check return type
            return_type = method.return_type
            logging.debug(f"Method {method.name} has return type: {return_type}")
            if return_type.startswith("const "):
                return_type = return_type[6:].strip()
            if return_type.endswith("*"):
                return_type = return_type[:-1].strip()
            if return_type.endswith("&"):
                return_type = return_type[:-1].strip()
            logging.debug(f"Cleaned return type: {return_type}")

            result = self.find_typedef(return_type)
            if result:
                typedef_name, underlying_type = result
                used_typedefs[typedef_name] = underlying_type
                logging.debug(f"Found typedef for return type: {typedef_name} -> {underlying_type}")

            # Check parameter types
            if method.parameters:
                logging.debug(f"Method {method.name} has {len(method.parameters)} parameters")
                for param in method.parameters:
                    param_type = param.type_name
                    logging.debug(f"Parameter {param.name} has type: {param_type}")
                    if param_type.startswith("const "):
                        param_type = param_type[6:].strip()
                    if param_type.endswith("*"):
                        param_type = param_type[:-1].strip()
                    if param_type.endswith("&"):
                        param_type = param_type[:-1].strip()
                    logging.debug(f"Cleaned parameter type: {param_type}")

                    result = self.find_typedef(param_type)
                    if result:
                        typedef_name, underlying_type = result
                        used_typedefs[typedef_name] = underlying_type
                        logging.debug(
                            f"Found typedef for parameter {param.name}: "
                            f"{typedef_name} -> {underlying_type}",
                        )

        logging.debug(f"Collected {len(used_typedefs)} total typedefs: {used_typedefs}")
        return used_typedefs

    def resolve_type_name(self, die: DIE, type_attr_name: str = "DW_AT_type") -> str:
        """Resolve type name using pyelftools DIE reference resolution."""
        try:
            # First check if the DIE has the type attribute
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
            if type_die.tag == "DW_TAG_typedef":
                # For typedefs, return the typedef name directly
                typedef_name = (
                    name_attr.value.decode("utf-8")
                    if isinstance(name_attr.value, bytes)
                    else str(name_attr.value)
                )
                return typedef_name
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
            if type_die.tag == "DW_TAG_array_type":
                # Parse array type with dimensions
                array_info = self.parse_array_type(type_die)
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

    def parse_class_info(self, cu: CompileUnit, class_die: DIE) -> ClassInfo:
        """Parse class information using pyelftools methods."""
        # Get class name
        name_attr = class_die.attributes.get("DW_AT_name")
        class_name = name_attr.value.decode("utf-8") if name_attr else "unknown_class"

        # Get class size
        size_attr = class_die.attributes.get("DW_AT_byte_size")
        byte_size = size_attr.value if size_attr else 0

        # Get alignment information
        alignment_attr = class_die.attributes.get("DW_AT_alignment")
        alignment = alignment_attr.value if alignment_attr else None

        # Get declaration information
        decl_file_attr = class_die.attributes.get("DW_AT_decl_file")
        decl_line_attr = class_die.attributes.get("DW_AT_decl_line")

        declaration_file = None
        if decl_file_attr:
            # Get file name from line program if available
            if cu.get_top_DIE().get_full_path() and self.dwarf_info is not None:
                try:
                    line_program = self.dwarf_info.line_program_for_CU(cu)
                    if line_program and decl_file_attr.value < len(line_program.header.file_entry):
                        file_entry = line_program.header.file_entry[decl_file_attr.value - 1]
                        declaration_file = (
                            file_entry.name.decode("utf-8")
                            if hasattr(file_entry.name, "decode")
                            else str(file_entry.name)
                        )
                except Exception:
                    pass

        declaration_line = decl_line_attr.value if decl_line_attr else None
        die_offset = class_die.offset

        members = []
        methods = []
        base_classes = []
        enums = []
        nested_structs = []
        unions = []
        processed_union_offsets = set()  # Track anonymous unions to avoid double processing

        # Process class children
        for child in class_die.iter_children():
            if child.tag == "DW_TAG_member":
                # Check if this is an anonymous union member
                name_attr = child.attributes.get("DW_AT_name")
                type_attr = child.attributes.get("DW_AT_type")

                if not name_attr and type_attr:
                    # This might be an anonymous union/struct member
                    try:
                        # Get the actual DIE that this type references
                        type_die = child.get_DIE_from_attribute("DW_AT_type")
                        if type_die and type_die.tag == "DW_TAG_union_type":
                            # This is an anonymous union member, parse the union directly
                            union_info = self.parse_union(type_die)
                            if union_info:
                                unions.append(union_info)
                                processed_union_offsets.add(type_die.offset)
                                logging.debug(
                                    f"Found anonymous union in {class_name}: "
                                    f"({union_info.byte_size} bytes)",
                                )
                            continue
                    except Exception as e:
                        logging.debug(f"Failed to resolve anonymous member type: {e}")

                # Regular member processing
                member = self.parse_member(child)
                if member:
                    members.append(member)
            elif child.tag == "DW_TAG_subprogram":
                method = self.parse_method(child)
                if method:
                    methods.append(method)
            elif child.tag == "DW_TAG_inheritance":
                base_type = self.resolve_type_name(child)
                if base_type != "unknown_type":
                    base_classes.append(base_type)
            elif child.tag == "DW_TAG_enumeration_type":
                enum = self.parse_enum(child)
                if enum:
                    enums.append(enum)
            elif child.tag == "DW_TAG_structure_type":
                # Parse nested structures
                struct_info = self.parse_nested_structure(child)
                if struct_info:
                    struct_obj = StructInfo(
                        name=struct_info["name"],
                        byte_size=struct_info["size"],
                        members=struct_info["members"],
                        die_offset=struct_info["die_offset"],
                    )
                    nested_structs.append(struct_obj)
                    logging.debug(
                        f"Found nested structure in {class_name}: {struct_info['name']} "
                        f"({struct_info['size']} bytes)",
                    )
            elif child.tag == "DW_TAG_union_type":
                # Skip unions that were already processed as anonymous members
                if child.offset not in processed_union_offsets:
                    # Parse nested unions
                    union_info = self.parse_union(child)
                    if union_info:
                        unions.append(union_info)
                        logging.debug(
                            f"Found union in {class_name}: {union_info.name} "
                            f"({union_info.byte_size} bytes)",
                        )
            elif child.tag == "DW_TAG_array_type":
                # Parse array type with size information
                array_info = self.parse_array_type(child)
                if array_info:
                    logging.debug(
                        f"Found array type in {class_name}: {array_info['name']} "
                        f"(size: {array_info['total_elements']})",
                    )
            elif child.tag in ["DW_TAG_typedef", "DW_TAG_class_type"]:
                # These are known nested types - log but don't warn
                child_name = child.attributes.get("DW_AT_name")
                child_name_str = child_name.value.decode("utf-8") if child_name else "unnamed"
                logging.debug(
                    f"Found nested type in {class_name}: {child.tag} (name: {child_name_str})",
                )
            else:
                # Log warning for unhandled tags
                child_name = child.attributes.get("DW_AT_name")
                child_name_str = child_name.value.decode("utf-8") if child_name else "unnamed"
                logging.warning(
                    f"Unhandled DWARF tag in class {class_name}: {child.tag} "
                    f"(name: {child_name_str}) at offset 0x{child.offset:x}",
                )

        class_info_temp = ClassInfo(
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
            packing_info=None,
        )

        # Calculate packing information
        packing_info = self.calculate_packing_info(class_info_temp)
        class_info_temp.packing_info = packing_info

        return class_info_temp

    def parse_member(self, member_die: DIE) -> MemberInfo | None:
        """Parse a class member using pyelftools."""
        # Resolve member type first to determine if it's anonymous
        type_name = self.resolve_type_name(member_die)

        # Get member name (handle anonymous members)
        name_attr = member_die.attributes.get("DW_AT_name")
        if name_attr:
            member_name = name_attr.value.decode("utf-8")
        # Check if this is an anonymous union/struct member
        elif "union" in type_name.lower() or "struct" in type_name.lower():
            member_name = ""  # Anonymous member
        else:
            return None  # Skip if not an anonymous aggregate type

        # Check if it's static/external
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
        if member_name.startswith("_vptr$"):
            if type_name == "unknown_type" or "__vtbl_ptr_type" in type_name:
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
        """Parse a class method using pyelftools."""
        # Get method name
        name_attr = method_die.attributes.get("DW_AT_name")
        if not name_attr:
            return None
        method_name = name_attr.value.decode("utf-8")

        # Get return type
        return_type = self.resolve_type_name(method_die)

        # Check if virtual
        is_virtual = method_die.attributes.get("DW_AT_virtuality") is not None

        # Get vtable index if virtual
        vtable_index = None
        if is_virtual:
            vtable_attr = method_die.attributes.get("DW_AT_vtable_elem_location")
            if vtable_attr:
                # Parse vtable location expression to get index
                # This is a simplified version - full implementation would parse the expression
                vtable_index = 0  # Placeholder

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
        """Parse a function parameter using pyelftools."""
        # Check if artificial (like 'this' pointer)
        is_artificial = param_die.attributes.get("DW_AT_artificial") is not None

        # Get parameter name
        name_attr = param_die.attributes.get("DW_AT_name")
        param_name = name_attr.value.decode("utf-8") if name_attr else "param"

        # Get parameter type
        param_type = self.resolve_type_name(param_die)

        # Get default value if present
        default_value = None
        const_attr = param_die.attributes.get("DW_AT_default_value")
        if const_attr:
            default_value = str(const_attr.value)

        # Create parameter info with artificial flag stored in name for filtering
        if is_artificial:
            param_name = "__artificial__"

        return ParameterInfo(name=param_name, type_name=param_type, default_value=default_value)

    def parse_enum(self, enum_die: DIE) -> EnumInfo | None:
        """Parse an enumeration using pyelftools."""
        # Get enum name
        name_attr = enum_die.attributes.get("DW_AT_name")
        enum_name = name_attr.value.decode("utf-8") if name_attr else "unknown_enum"

        # Get enum size
        size_attr = enum_die.attributes.get("DW_AT_byte_size")
        byte_size = size_attr.value if size_attr else 4  # Default to int size

        # Get declaration information
        decl_file_attr = enum_die.attributes.get("DW_AT_decl_file")
        decl_line_attr = enum_die.attributes.get("DW_AT_decl_line")

        declaration_file = None
        if decl_file_attr:
            # Try to resolve file name from line program
            try:
                # This is a simplified approach - could be enhanced with proper line program parsing
                declaration_file = f"file_{decl_file_attr.value}"
            except Exception:
                pass

        declaration_line = decl_line_attr.value if decl_line_attr else None

        # Parse enumerators
        enumerators = []
        for child in enum_die.iter_children():
            if child.tag == "DW_TAG_enumerator":
                enumerator = self.parse_enumerator(child)
                if enumerator:
                    enumerators.append(enumerator)

        return EnumInfo(
            name=enum_name,
            byte_size=byte_size,
            enumerators=enumerators,
            declaration_file=declaration_file,
            declaration_line=declaration_line,
        )

    def parse_enumerator(self, enumerator_die: DIE) -> EnumeratorInfo | None:
        """Parse an enumerator value using pyelftools."""
        # Get enumerator name
        name_attr = enumerator_die.attributes.get("DW_AT_name")
        if not name_attr:
            return None
        enumerator_name = name_attr.value.decode("utf-8")

        # Get enumerator value
        value_attr = enumerator_die.attributes.get("DW_AT_const_value")
        if not value_attr:
            return None

        # Handle different value formats
        value = value_attr.value
        if isinstance(value, bytes):
            # Convert bytes to signed integer
            if len(value) <= 8:
                value = int.from_bytes(value, byteorder="little", signed=True)
            else:
                value = 0
        elif not isinstance(value, int):
            try:
                value = int(value)
            except (ValueError, TypeError):
                value = 0

        return EnumeratorInfo(name=enumerator_name, value=value)

    def parse_nested_structure(self, struct_die: DIE) -> dict | None:
        """Parse a nested structure definition."""
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

        return {
            "name": struct_name,
            "size": struct_size,
            "members": members,
            "die_offset": struct_die.offset,
        }

    def parse_union(self, union_die: DIE) -> UnionInfo | None:
        """Parse a union definition."""
        # Get union name (might be None for anonymous unions)
        name_attr = union_die.attributes.get("DW_AT_name")
        union_name = name_attr.value.decode("utf-8") if name_attr else None

        # Get union size
        size_attr = union_die.attributes.get("DW_AT_byte_size")
        union_size = size_attr.value if size_attr else 0

        # Parse members
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
                    struct_obj = StructInfo(
                        name=struct_info["name"] if struct_info["name"] else "",
                        byte_size=struct_info["size"],
                        members=struct_info["members"],
                        die_offset=struct_info["die_offset"],
                    )
                    nested_structs.append(struct_obj)

                    # If anonymous struct, add as a special member
                    if not struct_info["name"]:
                        # Create a member representing the anonymous struct
                        struct_member = MemberInfo(
                            name="",  # Anonymous
                            type_name="struct",
                            offset=0,  # Unions start at offset 0
                        )
                        members.append(struct_member)

        return UnionInfo(
            name=union_name if union_name else "",
            byte_size=union_size,
            members=members,
            nested_structs=nested_structs,
            die_offset=union_die.offset,
        )

    def parse_array_type(self, array_die: DIE) -> dict | None:
        """Parse array type with size calculation from DW_TAG_subrange_type children."""
        logging.debug(f"Parsing array type at DIE offset 0x{array_die.offset:x}")

        # Get the element type
        element_type = self.resolve_type_name(array_die)
        logging.debug(f"Array element type: {element_type}")

        # Calculate total array size from subrange children
        dimensions = []
        total_elements = 1

        for child in array_die.iter_children():
            if child.tag == "DW_TAG_subrange_type":
                logging.debug(f"Found subrange at offset 0x{child.offset:x}")

                # Get bounds
                upper_bound_attr = child.attributes.get("DW_AT_upper_bound")
                lower_bound_attr = child.attributes.get("DW_AT_lower_bound")
                count_attr = child.attributes.get("DW_AT_count")

                if count_attr:
                    # Direct count attribute
                    dimension_size = count_attr.value
                    logging.debug(f"Subrange has count: {dimension_size}")
                elif upper_bound_attr:
                    # Calculate from bounds: (upper - lower) + 1
                    upper_bound = upper_bound_attr.value
                    lower_bound = lower_bound_attr.value if lower_bound_attr else 0
                    dimension_size = (upper_bound - lower_bound) + 1
                    logging.debug(
                        f"Subrange bounds: {lower_bound} to {upper_bound}, size: {dimension_size}",
                    )
                else:
                    # Unknown size
                    dimension_size = 0
                    logging.debug("Subrange has unknown size")

                dimensions.append(dimension_size)
                if dimension_size > 0:
                    total_elements *= dimension_size

        # Generate array name/type description
        if dimensions:
            dimension_str = "][".join(str(d) if d > 0 else "" for d in dimensions)
            array_name = f"{element_type}[{dimension_str}]"
        else:
            array_name = f"{element_type}[]"

        logging.debug(f"Parsed array: {array_name} (total elements: {total_elements})")

        return {
            "name": array_name,
            "element_type": element_type,
            "dimensions": dimensions,
            "total_elements": total_elements,
            "die_offset": array_die.offset,
        }

    def generate_struct_definition(self, struct_info: StructInfo) -> list[str]:
        """Generate C++ struct definition with proper padding analysis."""
        lines = []

        # Struct header with metadata
        lines.append(f"    // Struct {struct_info.name} ({struct_info.byte_size} bytes)")
        lines.append(f"    struct {struct_info.name}")
        lines.append("    {")

        # Sort members by offset for proper layout analysis
        sorted_members = sorted(
            [m for m in struct_info.members if m.offset is not None], key=lambda m: m.offset or 0,
        )

        current_offset = 0

        for i, member in enumerate(sorted_members):
            member_offset = member.offset or 0

            # Add padding if there's a gap
            if member_offset > current_offset:
                padding_size = member_offset - current_offset
                lines.append("        // padding for alignment")
                lines.append(f"        std::uint8_t _pad{i}[{padding_size}];")

            # Add the member
            offset_comment = f"  // offset {member_offset}"
            lines.append(f"        {member.type_name} {member.name};{offset_comment}")

            # Estimate member size (simplified)
            member_size = self._estimate_member_size(member.type_name)
            current_offset = member_offset + member_size

        # Add final padding if struct size is larger than last member
        if current_offset < struct_info.byte_size:
            final_padding = struct_info.byte_size - current_offset
            lines.append("        // final padding")
            lines.append(f"        std::uint8_t _final_pad[{final_padding}];")

        lines.append("    };")
        lines.append("")

        return lines

    def _estimate_member_size(self, type_name: str) -> int:
        """Estimate the size of a member type."""
        # Remove const and pointer/reference decorations
        clean_type = type_name.replace("const ", "").strip()
        if clean_type.endswith("*") or clean_type.endswith("&"):
            return 8  # Pointer/reference size on x64

        # Basic type sizes
        type_sizes = {
            "bool": 1,
            "char": 1,
            "u8": 1,
            "s8": 1,
            "u16": 2,
            "s16": 2,
            "short": 2,
            "u32": 4,
            "s32": 4,
            "int": 4,
            "float": 4,
            "f32": 4,
            "u64": 8,
            "s64": 8,
            "long": 8,
            "double": 8,
            "f64": 8,
        }

        return type_sizes.get(clean_type, 8)  # Default to pointer size for unknown types

    def _is_artificial_param(self, param: ParameterInfo) -> bool:
        """Check if a parameter is artificial (like 'this' pointer)."""
        # We marked artificial parameters with a special name during parsing
        return param.name == "__artificial__"

    def generate_union_definition(self, union_info: UnionInfo) -> list[str]:
        """Generate C++ union definition."""
        lines = []

        # Union header with metadata
        union_name = union_info.name if union_info.name else ""
        lines.append(f"    // Union {union_name} ({union_info.byte_size} bytes)")

        # Handle anonymous unions
        if union_name:
            lines.append(f"    union {union_name}")
        else:
            lines.append("    union")
        lines.append("    {")

        # Add nested structs first (like anonymous struct inside union)
        for struct in union_info.nested_structs:
            if not struct.name:  # Anonymous struct
                lines.append("        struct")
                lines.append("        {")
                for member in struct.members:
                    offset_comment = (
                        f"  // offset {member.offset}" if member.offset is not None else ""
                    )
                    lines.append(f"            {member.type_name} {member.name};{offset_comment}")
                lines.append("        };")
            else:
                # Named nested struct
                lines.append(f"        struct {struct.name}")
                lines.append("        {")
                for member in struct.members:
                    offset_comment = (
                        f"  // offset {member.offset}" if member.offset is not None else ""
                    )
                    lines.append(f"            {member.type_name} {member.name};{offset_comment}")
                lines.append(f"        }} {struct.name};")

        # Add regular union members
        for member in union_info.members:
            if member.name:  # Skip anonymous struct placeholder members
                offset_comment = f"  // offset {member.offset}" if member.offset is not None else ""
                lines.append(f"        {member.type_name} {member.name};{offset_comment}")

        lines.append("    };")
        lines.append("")

        return lines

    def generate_complete_hierarchy_header(self, class_name: str) -> str:
        """Generate C++ header with complete inheritance hierarchy."""
        # Build full hierarchy and collect class info in one pass
        all_class_infos = {}
        hierarchy_order: list[str] = []

        # Start with target class and work backwards through inheritance
        current_class: str | None = class_name
        visited = set()

        while current_class and current_class not in visited:
            visited.add(current_class)
            result = self.find_class(current_class)
            if not result:
                break

            cu, class_die = result
            class_info = self.parse_class_info(cu, class_die)
            all_class_infos[current_class] = class_info
            hierarchy_order.insert(0, current_class)  # Insert at beginning for base->derived order

            # Find base class
            next_class: str | None = None
            for child in class_die.iter_children():
                if child.tag == "DW_TAG_inheritance":
                    base_type = self.resolve_type_name(child)
                    if base_type != "unknown_type":
                        next_class = base_type
                        break
            current_class = next_class

        # Generate header with all classes
        lines = [
            f"#ifndef {class_name.upper()}_HIERARCHY_H",
            f"#define {class_name.upper()}_HIERARCHY_H",
            "",
            "#include <cstdint>",
            "",
        ]

        lines.extend(
            [
                "// Generated complete inheritance hierarchy for: " + class_name,
            ],
        )

        # Add metadata for the main class
        if class_name in all_class_infos:
            main_class = all_class_infos[class_name]
            lines.extend(
                [
                    "",
                    f"// Target Class: {class_name}",
                    f"// - Size: {main_class.byte_size} bytes",
                    f"// - DIE Offset: 0x{main_class.die_offset:08x}",
                ],
            )

            if main_class.packing_info:
                packing = main_class.packing_info
                lines.append(f"// - Suggested Packing: {packing['suggested_packing']} bytes")

            if len(hierarchy_order) > 1:
                hierarchy_chain = " -> ".join(hierarchy_order)
                lines.append(f"// - Full Inheritance Chain: {hierarchy_chain}")

        # Collect and resolve dependencies from all classes
        forward_decls = set()
        additional_types = {}  # Types we can resolve and include

        for class_info in all_class_infos.values():
            for member in class_info.members:
                if not member.type_name.endswith("*") and member.type_name not in (
                    "int",
                    "char",
                    "float",
                    "double",
                    "void",
                    "bool",
                ):
                    if member.type_name.startswith("const "):
                        clean_type = member.type_name[6:].strip()
                    else:
                        clean_type = member.type_name
                    if not clean_type.endswith("*") and clean_type not in (
                        "unknown_type",
                        "s8",
                        "s16",
                        "s32",
                        "s64",
                        "u8",
                        "u16",
                        "u32",
                        "u64",
                    ):
                        # Don't forward declare classes we're already generating
                        if clean_type not in hierarchy_order:
                            # Try to resolve basic Mt types (MtFloat3, MtString, etc.)
                            if (
                                clean_type.startswith("Mt") and len(clean_type) < 20
                            ):  # Basic Mt types
                                type_result = self.find_class(clean_type)
                                if type_result:
                                    cu, type_die = type_result
                                    type_info = self.parse_class_info(cu, type_die)
                                    # Include if it's a simple type (small size, few members)
                                    if type_info.byte_size <= 64 and len(type_info.members) <= 10:
                                        additional_types[clean_type] = type_info
                                        continue
                            # Otherwise, forward declare
                            forward_decls.add(clean_type)

        if forward_decls:
            lines.append("")
            lines.append("// Forward declarations")
            for decl in sorted(forward_decls):
                lines.append(f"struct {decl};")

        # Add resolved basic types first
        if additional_types:
            lines.append("")
            lines.append("// Basic Mt types")
            for type_name in sorted(additional_types.keys()):
                type_lines = self._generate_single_class(type_name, additional_types[type_name])
                lines.extend([""] + type_lines)

        # Generate all classes in hierarchy order (base to derived)
        for cls_name in hierarchy_order:
            if cls_name in all_class_infos:
                class_lines = self._generate_single_class(cls_name, all_class_infos[cls_name])
                lines.extend([""] + class_lines)

        lines.extend(["", f"#endif // {class_name.upper()}_HIERARCHY_H"])

        return "\n".join(lines)

    def _generate_single_class(self, class_name: str, class_info: ClassInfo) -> list[str]:
        """Generate a single class definition."""
        lines = []
        logging.debug(f"Generating class {class_name} with {len(class_info.methods)} methods")

        # Add class-specific metadata
        lines.extend(
            [
                f"// {class_name} - DWARF Information:",
                f"// - Size: {class_info.byte_size} bytes",
                f"// - DIE Offset: 0x{class_info.die_offset:08x}",
            ],
        )

        # Add packing information if available
        if class_info.packing_info:
            packing = class_info.packing_info
            lines.append(f"// - Suggested Packing: {packing['suggested_packing']} bytes")
            if packing["total_padding"] > 0:
                lines.append(f"// - Total Padding: {packing['total_padding']} bytes")

        # Add declaration info if available
        if class_info.declaration_file:
            lines.append(f"// - Declaration: {class_info.declaration_file}")
            if class_info.declaration_line:
                lines.append(f"//   Line: {class_info.declaration_line}")

        # Add inheritance information
        inheritance_part = ""
        if class_info.base_classes:
            inheritance_part = f" : public {', public '.join(class_info.base_classes)}"
            lines.append(f"// - Inherits from: {', '.join(class_info.base_classes)}")

        # Add alignment attribute if specified
        alignment_attr = ""
        if class_info.alignment and class_info.alignment > 1:
            alignment_attr = f" __attribute__((aligned({class_info.alignment})))"
            lines.append(f"// - Alignment: {class_info.alignment} bytes")

        # Class declaration
        lines.append(f"class{alignment_attr} {class_name}{inheritance_part}")
        lines.append("{")

        # Add enums
        if class_info.enums:
            lines.append("public:")
            for enum in class_info.enums:
                # Add enum metadata
                lines.append(f"    // Enum {enum.name} ({enum.byte_size} bytes)")
                if enum.declaration_file:
                    lines.append(f"    // Declared in: {enum.declaration_file}")
                    if enum.declaration_line:
                        lines.append(f"    //   Line: {enum.declaration_line}")

                # Start enum declaration
                lines.append(f"    enum class {enum.name}")
                lines.append("    {")

                # Add enumerators
                for i, enumerator in enumerate(enum.enumerators):
                    comma = "," if i < len(enum.enumerators) - 1 else ""
                    lines.append(f"        {enumerator.name} = {enumerator.value}{comma}")

                lines.append("    };")
                lines.append("")

        # Add virtual methods
        virtual_methods = [m for m in class_info.methods if m.is_virtual]
        if virtual_methods:
            lines.append("public:")
            for method in virtual_methods:
                if method.is_destructor:
                    lines.append(f"    virtual ~{class_name}();")
                else:
                    # Build parameter list
                    param_list = []
                    if method.parameters:
                        for param in method.parameters:
                            param_str = f"{param.type_name} {param.name}"
                            if param.default_value:
                                param_str += f" = {param.default_value}"
                            param_list.append(param_str)
                    params = ", ".join(param_list)
                    lines.append(f"    virtual {method.return_type} {method.name}({params});")

        # Add constructors, operators, and other non-virtual methods
        non_virtual_methods = [m for m in class_info.methods if not m.is_virtual]
        logging.debug(
            f"Total methods: {len(class_info.methods)}, "
            f"Non-virtual methods: {len(non_virtual_methods)}",
        )
        for i, method in enumerate(class_info.methods):
            logging.debug(
                f"Method {i + 1}: {method.name}, virtual={method.is_virtual}, "
                f"constructor={method.is_constructor}, destructor={method.is_destructor}",
            )
        if non_virtual_methods:
            lines.append("public:")

            # Group methods by type for better organization
            constructors = [m for m in non_virtual_methods if m.is_constructor]
            destructors = [m for m in non_virtual_methods if m.is_destructor]
            operators = [
                m
                for m in non_virtual_methods
                if not m.is_constructor and not m.is_destructor and m.name.startswith("operator")
            ]
            other_methods = [
                m
                for m in non_virtual_methods
                if not m.is_constructor
                and not m.is_destructor
                and not m.name.startswith("operator")
            ]

            # Generate constructors
            for method in constructors:
                param_list = []
                # Skip first parameter if it's 'this' pointer (DW_AT_artificial)
                if method.parameters:
                    actual_params = [
                        p for p in method.parameters if not self._is_artificial_param(p)
                    ]
                    for param in actual_params:
                        param_str = f"{param.type_name} {param.name}"
                        if param.default_value:
                            param_str += f" = {param.default_value}"
                        param_list.append(param_str)
                params = ", ".join(param_list)
                lines.append(f"    {method.name}({params});")

            # Generate destructors
            for method in destructors:
                lines.append(f"    {method.name}();")

            # Generate operators
            for method in operators:
                param_list = []
                # Skip first parameter if it's 'this' pointer (DW_AT_artificial)
                if method.parameters:
                    actual_params = [
                        p for p in method.parameters if not self._is_artificial_param(p)
                    ]
                    for param in actual_params:
                        param_str = f"{param.type_name} {param.name}"
                        if param.default_value:
                            param_str += f" = {param.default_value}"
                        param_list.append(param_str)
                params = ", ".join(param_list)

                # Handle return type for operators
                if method.return_type and method.return_type != "void":
                    lines.append(f"    {method.return_type} {method.name}({params});")
                # For operators without explicit return type, infer appropriate return type
                elif method.name in (
                    "operator+=",
                    "operator-=",
                    "operator*=",
                    "operator/=",
                    "operator=",
                ):
                    lines.append(f"    MtPoint& {method.name}({params});")
                elif method.name == "operator-" and len(param_list) == 0:  # Unary minus
                    lines.append(f"    MtPoint {method.name}();")
                else:
                    lines.append(f"    void {method.name}({params});")

            # Generate other methods
            for method in other_methods:
                param_list = []
                # Skip first parameter if it's 'this' pointer (DW_AT_artificial)
                if method.parameters:
                    actual_params = [
                        p for p in method.parameters if not self._is_artificial_param(p)
                    ]
                    for param in actual_params:
                        param_str = f"{param.type_name} {param.name}"
                        if param.default_value:
                            param_str += f" = {param.default_value}"
                        param_list.append(param_str)
                params = ", ".join(param_list)
                lines.append(f"    {method.return_type} {method.name}({params});")

        # Add public data members
        if class_info.members:
            lines.append("public:")

            # Regular members first
            regular_members = [m for m in class_info.members if not m.is_static]
            for member in regular_members:
                offset_comment = (
                    f"  // offset: 0x{member.offset:x}" if member.offset is not None else ""
                )
                if member.name == "":  # Anonymous union/struct member
                    lines.append(f"    {member.type_name};{offset_comment}")
                else:
                    lines.append(f"    {member.type_name} {member.name};{offset_comment}")

            # Static members
            static_members = [m for m in class_info.members if m.is_static]
            if static_members:
                lines.append("")
                lines.append("    // Static members")
                for member in static_members:
                    # Don't add const prefix if type already includes const
                    type_with_const = member.type_name
                    if member.is_const and not member.type_name.startswith("const "):
                        type_with_const = f"const {member.type_name}"

                    value_part = (
                        f" = {member.const_value}" if member.const_value is not None else ""
                    )
                    lines.append(f"    static {type_with_const} {member.name}{value_part};")

        lines.append("};")
        return lines

    def generate_header(self, class_name: str) -> str:
        """Generate C++ header for the specified class."""
        result = self.find_class(class_name)
        if not result:
            # Return empty header with a comment instead of throwing an error
            # This avoids the expensive full iteration through all CUs
            return f"""#ifndef {class_name.upper()}_H
#define {class_name.upper()}_H

// Class '{class_name}' not found in DWARF information
// Generated from DWARF debug information using pyelftools

#endif // {class_name.upper()}_H
"""

        cu, class_die = result
        class_info = self.parse_class_info(cu, class_die)

        # Collect typedefs used by this class
        used_typedefs = self.collect_used_typedefs(class_info)

        lines = [
            f"#ifndef {class_name.upper()}_H",
            f"#define {class_name.upper()}_H",
            "",
            "#include <cstdint>",
            "",
        ]

        # Add used typedefs
        if used_typedefs:
            lines.append("// Type definitions from DWARF")
            for typedef_name, underlying_type in sorted(used_typedefs.items()):
                lines.append(f"typedef {underlying_type} {typedef_name};")
            lines.append("")

        lines.extend(
            [
                "// Generated from DWARF debug information using pyelftools",
                f"// Target symbol: {class_name}",
                "",
                "// DWARF Debug Information:",
                f"// - Size: {class_info.byte_size} bytes",
                f"// - DIE Offset: 0x{class_info.die_offset:08x}",
                f"// - Source CU: 0x{cu.cu_offset:08x}",
            ],
        )

        # Add alignment information if available
        if class_info.alignment:
            lines.append(f"// - Alignment: {class_info.alignment} bytes")

        # Add packing information
        if class_info.packing_info:
            packing = class_info.packing_info
            lines.append(f"// - Suggested Packing: {packing['suggested_packing']} bytes")
            if packing["total_padding"] > 0:
                lines.append(f"// - Total Padding: {packing['total_padding']} bytes")
                lines.append(
                    f"// - Natural Size: {packing['natural_size']} "
                    f"vs Actual Size: {packing['actual_size']}",
                )

        # Add declaration information if available
        if class_info.declaration_file:
            lines.append(f"// - Declaration: {class_info.declaration_file}")
            if class_info.declaration_line:
                lines.append(f"// - Line: {class_info.declaration_line}")

        # Add complete inheritance hierarchy information
        full_hierarchy = self.build_inheritance_hierarchy(class_name)
        if full_hierarchy:
            hierarchy_chain = " -> ".join(full_hierarchy + [class_name])
            lines.append(f"// - Full Inheritance Chain: {hierarchy_chain}")
        elif class_info.base_classes:
            lines.append(
                f"// - Direct Inheritance: {' -> '.join(class_info.base_classes)} -> {class_name}",
            )

        lines.extend([""])

        # Add forward declarations for complex types
        forward_decls = set()

        # Get enum names defined within this class to exclude from forward declarations
        enum_names = {enum.name for enum in class_info.enums}

        # Get nested struct names to exclude from forward declarations
        struct_names = {struct.name for struct in class_info.nested_structs}

        # Get union names to exclude from forward declarations
        union_names = {union.name for union in class_info.unions if union.name}

        # Get typedef names to exclude from forward declarations
        typedef_names = set(used_typedefs.keys())

        for member in class_info.members:
            if not member.type_name.endswith("*") and member.type_name not in (
                "int",
                "char",
                "float",
                "double",
                "void",
                "bool",
            ):
                if member.type_name.startswith("const "):
                    clean_type = member.type_name[6:].strip()
                else:
                    clean_type = member.type_name
                # Skip array types (contain brackets) and other non-struct types
                if (
                    not clean_type.endswith("*")
                    and "[" not in clean_type
                    and "]" not in clean_type
                    and clean_type not in ("unknown_type")
                    and clean_type not in enum_names
                    and clean_type not in struct_names
                    and clean_type not in union_names
                    and clean_type not in typedef_names
                ):
                    forward_decls.add(clean_type)

        if forward_decls:
            lines.append("")
            lines.append("// Forward declarations")
            for decl in sorted(forward_decls):
                lines.append(f"struct {decl};")

        # Add inheritance information
        inheritance_part = ""
        if class_info.base_classes:
            inheritance_part = f" : {', '.join(class_info.base_classes)}"

        # Add alignment attribute if specified
        alignment_attr = ""
        if class_info.alignment and class_info.alignment > 1:
            alignment_attr = f" __attribute__((aligned({class_info.alignment})))"

        lines.extend(["", f"class{alignment_attr} {class_name}{inheritance_part}", "{"])

        # Add enums
        if class_info.enums:
            lines.append("public:")
            for enum in class_info.enums:
                # Add enum metadata
                lines.append(f"    // Enum {enum.name} ({enum.byte_size} bytes)")
                if enum.declaration_file:
                    lines.append(f"    // Declared in: {enum.declaration_file}")
                    if enum.declaration_line:
                        lines.append(f"    //   Line: {enum.declaration_line}")

                # Start enum declaration
                lines.append(f"    enum class {enum.name}")
                lines.append("    {")

                # Add enumerators
                for i, enumerator in enumerate(enum.enumerators):
                    comma = "," if i < len(enum.enumerators) - 1 else ""
                    lines.append(f"        {enumerator.name} = {enumerator.value}{comma}")

                lines.append("    };")
                lines.append("")

        # Add nested structs
        if class_info.nested_structs:
            lines.append("public:")
            for struct in class_info.nested_structs:
                struct_lines = self.generate_struct_definition(struct)
                lines.extend(struct_lines)

        # Add unions
        if class_info.unions:
            lines.append("public:")
            for union in class_info.unions:
                union_lines = self.generate_union_definition(union)
                lines.extend(union_lines)

        # Add public section with virtual methods
        virtual_methods = [m for m in class_info.methods if m.is_virtual]
        if virtual_methods:
            lines.append("public:")
            for method in virtual_methods:
                if method.is_destructor:
                    lines.append(f"    virtual ~{class_name}();")
                else:
                    # Build parameter list
                    param_list = []
                    if method.parameters:
                        for param in method.parameters:
                            param_str = f"{param.type_name} {param.name}"
                            if param.default_value:
                                param_str += f" = {param.default_value}"
                            param_list.append(param_str)
                    params = ", ".join(param_list)
                    lines.append(f"    virtual {method.return_type} {method.name}({params});")

        # Add constructors, operators, and other non-virtual methods
        non_virtual_methods = [m for m in class_info.methods if not m.is_virtual]
        if non_virtual_methods:
            lines.append("public:")

            # Group methods by type for better organization
            constructors = [m for m in non_virtual_methods if m.is_constructor]
            destructors = [m for m in non_virtual_methods if m.is_destructor]
            operators = [
                m
                for m in non_virtual_methods
                if not m.is_constructor and not m.is_destructor and m.name.startswith("operator")
            ]
            other_methods = [
                m
                for m in non_virtual_methods
                if not m.is_constructor
                and not m.is_destructor
                and not m.name.startswith("operator")
            ]

            # Generate constructors
            for method in constructors:
                param_list = []
                if method.parameters:
                    actual_params = [
                        p for p in method.parameters if not self._is_artificial_param(p)
                    ]
                    for param in actual_params:
                        param_str = f"{param.type_name} {param.name}"
                        if param.default_value:
                            param_str += f" = {param.default_value}"
                        param_list.append(param_str)
                params = ", ".join(param_list)
                lines.append(f"    {method.name}({params});")

            # Generate destructors
            for method in destructors:
                lines.append(f"    {method.name}();")

            # Generate operators
            for method in operators:
                param_list = []
                if method.parameters:
                    actual_params = [
                        p for p in method.parameters if not self._is_artificial_param(p)
                    ]
                    for param in actual_params:
                        param_str = f"{param.type_name} {param.name}"
                        if param.default_value:
                            param_str += f" = {param.default_value}"
                        param_list.append(param_str)
                params = ", ".join(param_list)

                # Handle return type for operators
                if method.return_type and method.return_type != "void":
                    lines.append(f"    {method.return_type} {method.name}({params});")
                # For operators without explicit return type, infer appropriate return type
                elif method.name in (
                    "operator+=",
                    "operator-=",
                    "operator*=",
                    "operator/=",
                    "operator=",
                ):
                    lines.append(f"    MtPoint& {method.name}({params});")
                elif method.name == "operator-" and len(param_list) == 0:  # Unary minus
                    lines.append(f"    MtPoint {method.name}();")
                else:
                    lines.append(f"    void {method.name}({params});")

            # Generate other methods
            for method in other_methods:
                param_list = []
                if method.parameters:
                    actual_params = [
                        p for p in method.parameters if not self._is_artificial_param(p)
                    ]
                    for param in actual_params:
                        param_str = f"{param.type_name} {param.name}"
                        if param.default_value:
                            param_str += f" = {param.default_value}"
                        param_list.append(param_str)
                params = ", ".join(param_list)
                lines.append(f"    {method.return_type} {method.name}({params});")

        # Add public data members section
        if class_info.members:
            lines.append("public:")

            # Regular members first
            regular_members = [m for m in class_info.members if not m.is_static]
            for member in regular_members:
                offset_comment = (
                    f"  // offset: 0x{member.offset:x}" if member.offset is not None else ""
                )
                lines.append(f"    {member.type_name} {member.name};{offset_comment}")

            # Static members
            static_members = [m for m in class_info.members if m.is_static]
            if static_members:
                lines.append("")
                lines.append("    // Static members")
                for member in static_members:
                    # Don't add const prefix if type already includes const
                    type_with_const = member.type_name
                    if member.is_const and not member.type_name.startswith("const "):
                        type_with_const = f"const {member.type_name}"

                    value_part = (
                        f" = {member.const_value}" if member.const_value is not None else ""
                    )
                    lines.append(f"    static {type_with_const} {member.name}{value_part};")

        lines.extend(["};", "", f"#endif // {class_name.upper()}_H"])

        return "\n".join(lines)
