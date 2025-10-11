#!/usr/bin/env python3

"""C++ header generation from DWARF ClassInfo structures - ENHANCED VERSION.

This module generates C++ header files from parsed ClassInfo objects,
handling formatting, forward declarations, and proper C++ syntax with
correct array declaration handling.
"""

import re
from ...models.dwarf import ClassInfo, EnumInfo, MethodInfo, StructInfo, UnionInfo, MemberInfo
from ....infrastructure.logging import get_logger, log_timing
from ....utils.path_utils import sanitize_for_filesystem

logger = get_logger(__name__)


class HeaderGenerator:
    """Generates C++ headers from ClassInfo objects.

    This class handles:
    - C++ header formatting with include guards
    - Forward declarations
    - Class definitions with proper inheritance
    - Member and method declarations with correct array syntax
    - Enum, struct, and union definitions
    - Metadata comments
    """

    def __init__(self) -> None:
        """Initialize header generator."""
        pass

    @log_timing
    def generate_header(
        self,
        class_info: ClassInfo,
        typedefs: dict[str, str] | None = None,
        cu_offset: int | None = None,
        include_metadata: bool = True,
    ) -> str:
        """Generate C++ header for a single class.

        Args:
            class_info: ClassInfo object to generate header for
            typedefs: Dictionary of typedef name -> underlying type
            cu_offset: Compilation unit offset for metadata
            include_metadata: Whether to include DWARF metadata comments

        Returns:
            Complete C++ header file as string
        """
        class_name = class_info.name
        sanitized_name = sanitize_for_filesystem(class_name).upper()
        lines = [
            f"#ifndef {sanitized_name}_H",
            f"#define {sanitized_name}_H",
            "",
            "#include <cstdint>",
            "",
        ]

        # Add typedefs if provided
        if typedefs:
            lines.append("// Type definitions from DWARF")
            for typedef_name, underlying_type in sorted(typedefs.items()):
                lines.append(f"typedef {underlying_type} {typedef_name};")
            lines.append("")

        if include_metadata:
            lines.extend(self._generate_metadata_header(class_info, cu_offset))

        # Add forward declarations
        forward_decls = self._collect_forward_declarations(class_info, typedefs or {})
        if forward_decls:
            lines.append("")
            lines.append("// Forward declarations")
            for decl in sorted(forward_decls):
                lines.append(f"struct {decl};")

        # Generate class definition
        class_lines = self._generate_single_class(class_info, include_metadata)
        lines.extend([""] + class_lines)

        lines.extend(["", f"#endif // {sanitized_name}_H"])

        return "\n".join(lines)

    @log_timing
    def generate_hierarchy_header(
        self,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        target_class: str,
        typedefs: dict[str, str] | None = None,
        include_metadata: bool = True,
    ) -> str:
        """Generate C++ header with complete inheritance hierarchy.

        Args:
            class_infos: Dictionary of class name -> ClassInfo
            hierarchy_order: List of class names in base-to-derived order
            target_class: Primary target class name
            typedefs: Dictionary of typedef name -> underlying type
            include_metadata: Whether to include DWARF metadata comments

        Returns:
            Complete C++ header file as string
        """
        sanitized_target = sanitize_for_filesystem(target_class).upper()
        lines = [
            f"#ifndef {sanitized_target}_HIERARCHY_H",
            f"#define {sanitized_target}_HIERARCHY_H",
            "",
            "#include <cstdint>",
            "",
        ]

        # Add typedefs if provided
        if typedefs:
            lines.append("// Type definitions from DWARF")
            for typedef_name, underlying_type in sorted(typedefs.items()):
                lines.append(f"typedef {underlying_type} {typedef_name};")
            lines.append("")

        lines.append("// Generated complete inheritance hierarchy for: " + target_class)

        # Add metadata for the main class
        if target_class in class_infos and include_metadata:
            main_class = class_infos[target_class]
            lines.extend(
                [
                    "",
                    f"// Target Class: {target_class}",
                    f"// - Size: {main_class.byte_size} bytes",
                    f"// - DIE Offset: 0x{main_class.die_offset:08x}",
                ]
            )

            if main_class.packing_info:
                packing = main_class.packing_info
                lines.append(f"// - Suggested Packing: {packing['suggested_packing']} bytes")

            if len(hierarchy_order) > 1:
                hierarchy_chain = " -> ".join(hierarchy_order)
                lines.append(f"// - Full Inheritance Chain: {hierarchy_chain}")

        # Collect forward declarations from all classes
        forward_decls = set()
        for class_info in class_infos.values():
            forward_decls.update(self._collect_forward_declarations(class_info, {}))

        # Remove classes that are in the hierarchy
        forward_decls = {decl for decl in forward_decls if decl not in hierarchy_order}

        if forward_decls:
            lines.append("")
            lines.append("// Forward declarations")
            for decl in sorted(forward_decls):
                lines.append(f"struct {decl};")

        # Generate all classes in hierarchy order (base to derived)
        for cls_name in hierarchy_order:
            if cls_name in class_infos:
                class_lines = self._generate_single_class(class_infos[cls_name], include_metadata)
                lines.extend([""] + class_lines)

        lines.extend(["", f"#endif // {sanitized_target}_HIERARCHY_H"])

        return "\n".join(lines)

    def _generate_metadata_header(self, class_info: ClassInfo, cu_offset: int | None) -> list[str]:
        """Generate metadata comment block for class."""
        lines = [
            "// Generated from DWARF debug information using pyelftools",
            f"// Target symbol: {class_info.name}",
            "",
            "// DWARF Debug Information:",
            f"// - Size: {class_info.byte_size} bytes",
            f"// - DIE Offset: 0x{class_info.die_offset:08x}",
        ]

        if cu_offset is not None:
            lines.append(f"// - Source CU: 0x{cu_offset:08x}")

        if class_info.alignment:
            lines.append(f"// - Alignment: {class_info.alignment} bytes")

        if class_info.packing_info:
            packing = class_info.packing_info
            lines.append(f"// - Suggested Packing: {packing['suggested_packing']} bytes")
            if packing["total_padding"] > 0:
                lines.append(f"// - Total Padding: {packing['total_padding']} bytes")

        if class_info.declaration_file:
            lines.append(f"// - Declaration: {class_info.declaration_file}")
            if class_info.declaration_line:
                lines.append(f"// - Line: {class_info.declaration_line}")

        if class_info.base_classes:
            inheritance_chain = " -> ".join(class_info.base_classes) + f" -> {class_info.name}"
            lines.append(f"// - Direct Inheritance: {inheritance_chain}")

        lines.append("")
        return lines

    def _collect_forward_declarations(
        self,
        class_info: ClassInfo,
        typedefs: dict[str, str],
    ) -> set[str]:
        """Collect forward declarations needed for this class."""
        forward_decls = set()

        # Get names to exclude
        enum_names = {enum.name for enum in class_info.enums}
        struct_names = {struct.name for struct in class_info.nested_structs}
        union_names = {union.name for union in class_info.unions if union.name}
        typedef_names = set(typedefs.keys())

        # Primitive types to exclude
        primitives = {
            "int", "char", "float", "double", "void", "bool",
            "unknown_type", "unsigned", "signed", "short", "long",
            "u8", "u16", "u32", "u64",
            "s8", "s16", "s32", "s64",
            "f32", "f64",
        }

        # Process class members
        for member in class_info.members:
            # Extract clean type name
            clean_type = self._extract_base_type(member.type_name)
            
            # Skip primitives and known types
            if (
                clean_type in primitives
                or clean_type in enum_names
                or clean_type in struct_names
                or clean_type in union_names
                or clean_type in typedef_names
            ):
                continue

            forward_decls.add(clean_type)

        # Process method parameters and return types
        for method in class_info.methods:
            # Check return type
            if hasattr(method, 'return_type') and method.return_type:
                clean_type = self._extract_base_type(method.return_type)
                if (
                    clean_type not in primitives
                    and clean_type not in enum_names
                    and clean_type not in struct_names
                    and clean_type not in union_names
                    and clean_type not in typedef_names
                ):
                    forward_decls.add(clean_type)
            
            # Check method parameters
            if hasattr(method, 'parameters') and method.parameters:
                for param in method.parameters:
                    if hasattr(param, 'type_name') and param.type_name:
                        clean_type = self._extract_base_type(param.type_name)
                        if (
                            clean_type not in primitives
                            and clean_type not in enum_names
                            and clean_type not in struct_names
                            and clean_type not in union_names
                            and clean_type not in typedef_names
                        ):
                            forward_decls.add(clean_type)

        return forward_decls

    def _extract_base_type(self, type_name: str) -> str:
        """Extract base type name from complex type declarations."""
        # Remove const prefix
        if type_name.startswith("const "):
            type_name = type_name[6:].strip()
        
        # Remove pointer/reference suffixes
        while type_name.endswith("*") or type_name.endswith("&"):
            type_name = type_name[:-1].strip()
        
        # Handle array types - extract base type
        if "[" in type_name and "]" in type_name:
            type_name = type_name.split("[")[0].strip()
        
        return type_name

    def _format_member_declaration(self, member: MemberInfo) -> str:
        """Format a member declaration with proper C++ syntax.
        
        Handles special cases like arrays and static members.
        
        Args:
            member: MemberInfo object to format
            
        Returns:
            Properly formatted C++ member declaration
        """
        type_name = member.type_name
        member_name = member.name
        
        # Handle array types - need to reformat for C++ syntax
        if "[" in type_name and "]" in type_name:
            # Parse array declaration
            match = re.match(r'^(.+?)(\[.+\])$', type_name)
            if match:
                base_type = match.group(1).strip()
                dimensions = match.group(2)
                
                # Handle static arrays
                if member.is_static:
                    # Static array: static type name[dimensions];
                    type_with_const = base_type
                    if member.is_const and not base_type.startswith("const "):
                        type_with_const = f"const {base_type}"
                    
                    return f"static {type_with_const} {member_name}{dimensions}"
                else:
                    # Regular array: type name[dimensions];
                    return f"{base_type} {member_name}{dimensions}"
        
        # Handle static non-array members
        if member.is_static:
            type_with_const = type_name
            if member.is_const and not type_name.startswith("const "):
                type_with_const = f"const {type_name}"
            
            value_part = f" = {member.const_value}" if member.const_value is not None else ""
            return f"static {type_with_const} {member_name}{value_part}"
        
        # Handle anonymous union/struct
        if member_name == "":
            return type_name
        
        # Regular member
        return f"{type_name} {member_name}"

    def _generate_single_class(self, class_info: ClassInfo, include_metadata: bool) -> list[str]:
        """Generate a single class definition."""
        lines = []
        class_name = class_info.name

        if include_metadata:
            # Add class-specific metadata
            lines.extend(
                [
                    f"// {class_name} - DWARF Information:",
                    f"// - Size: {class_info.byte_size} bytes",
                    f"// - DIE Offset: 0x{class_info.die_offset:08x}",
                ]
            )

            if class_info.packing_info:
                packing = class_info.packing_info
                lines.append(f"// - Suggested Packing: {packing['suggested_packing']} bytes")
                if packing["total_padding"] > 0:
                    lines.append(f"// - Total Padding: {packing['total_padding']} bytes")

            if class_info.declaration_file:
                lines.append(f"// - Declaration: {class_info.declaration_file}")
                if class_info.declaration_line:
                    lines.append(f"//   Line: {class_info.declaration_line}")

            if class_info.base_classes:
                lines.append(f"// - Inherits from: {', '.join(class_info.base_classes)}")

        # Add inheritance
        inheritance_part = ""
        if class_info.base_classes:
            inheritance_part = f" : public {', public '.join(class_info.base_classes)}"

        # Add alignment attribute
        alignment_attr = ""
        if class_info.alignment and class_info.alignment > 1:
            alignment_attr = f" __attribute__((aligned({class_info.alignment})))"
            if include_metadata:
                lines.append(f"// - Alignment: {class_info.alignment} bytes")

        # Class declaration
        lines.append(f"class{alignment_attr} {class_name}{inheritance_part}")
        lines.append("{")

        # Add enums
        if class_info.enums:
            lines.append("public:")
            for enum in class_info.enums:
                lines.extend(self._generate_enum_definition(enum, include_metadata))

        # Add nested structs
        if class_info.nested_structs:
            lines.append("public:")
            for struct in class_info.nested_structs:
                lines.extend(self._generate_struct_definition(struct))

        # Add unions
        if class_info.unions:
            lines.append("public:")
            for union in class_info.unions:
                lines.extend(self._generate_union_definition(union))

        # Add virtual methods
        virtual_methods = [m for m in class_info.methods if m.is_virtual]
        if virtual_methods:
            lines.append("public:")
            lines.extend(self._generate_methods(virtual_methods, class_name))

        # Add non-virtual methods
        non_virtual_methods = [m for m in class_info.methods if not m.is_virtual]
        if non_virtual_methods:
            lines.append("public:")
            lines.extend(self._generate_methods(non_virtual_methods, class_name))

        # Add data members
        if class_info.members:
            lines.append("public:")

            # Regular members
            regular_members = [m for m in class_info.members if not m.is_static]
            for member in regular_members:
                declaration = self._format_member_declaration(member)
                offset_comment = (
                    f"  // offset: 0x{member.offset:x}" if member.offset is not None else ""
                )
                lines.append(f"    {declaration};{offset_comment}")

            # Static members
            static_members = [m for m in class_info.members if m.is_static]
            if static_members:
                lines.append("")
                lines.append("    // Static members")
                for member in static_members:
                    declaration = self._format_member_declaration(member)
                    lines.append(f"    {declaration};")

        lines.append("};")
        return lines

    def _generate_enum_definition(self, enum: "EnumInfo", include_metadata: bool) -> list[str]:
        """Generate enum definition."""
        lines = []

        if include_metadata:
            lines.append(f"    // Enum {enum.name} ({enum.byte_size} bytes)")
            if hasattr(enum, 'declaration_file') and enum.declaration_file:
                lines.append(f"    // Declared in: {enum.declaration_file}")
                if hasattr(enum, 'declaration_line') and enum.declaration_line:
                    lines.append(f"    //   Line: {enum.declaration_line}")

        lines.append(f"    enum class {enum.name}")
        lines.append("    {")

        for i, enumerator in enumerate(enum.enumerators):
            comma = "," if i < len(enum.enumerators) - 1 else ""
            lines.append(f"        {enumerator.name} = {enumerator.value}{comma}")

        lines.append("    };")
        lines.append("")
        return lines

    def _generate_struct_definition(self, struct: StructInfo) -> list[str]:
        """Generate struct definition."""
        struct_name = struct.name if struct.name else "anonymous_struct"
        lines = [
            f"    // Struct {struct_name} ({struct.byte_size} bytes)",
            f"    struct {struct_name}",
            "    {",
        ]

        # Sort members by offset
        sorted_members = sorted(
            [m for m in struct.members if m.offset is not None],
            key=lambda m: m.offset or 0,
        )

        for member in sorted_members:
            declaration = self._format_member_declaration(member)
            offset_comment = f"  // offset {member.offset}" if member.offset is not None else ""
            lines.append(f"        {declaration};{offset_comment}")

        lines.extend(["    };", ""])
        return lines

    def _generate_union_definition(self, union: UnionInfo) -> list[str]:
        """Generate union definition."""
        lines = []

        union_name = union.name if union.name else ""
        lines.append(f"    // Union {union_name} ({union.byte_size} bytes)")

        if union_name:
            lines.append(f"    union {union_name}")
        else:
            lines.append("    union")
        lines.append("    {")

        # Add nested structs
        for struct in union.nested_structs:
            if not struct.name:  # Anonymous
                lines.append("        struct")
                lines.append("        {")
                for member in struct.members:
                    declaration = self._format_member_declaration(member)
                    offset_comment = (
                        f"  // offset {member.offset}" if member.offset is not None else ""
                    )
                    lines.append(f"            {declaration};{offset_comment}")
                lines.append("        };")
            else:
                lines.append(f"        struct {struct.name}")
                lines.append("        {")
                for member in struct.members:
                    declaration = self._format_member_declaration(member)
                    offset_comment = (
                        f"  // offset {member.offset}" if member.offset is not None else ""
                    )
                    lines.append(f"            {declaration};{offset_comment}")
                lines.append(f"        }} {struct.name};")

        # Add regular members
        for member in union.members:
            if member.name:  # Skip anonymous placeholders
                declaration = self._format_member_declaration(member)
                offset_comment = f"  // offset {member.offset}" if member.offset is not None else ""
                lines.append(f"        {declaration};{offset_comment}")

        lines.extend(["    };", ""])
        return lines

    def _generate_methods(self, methods: list[MethodInfo], class_name: str) -> list[str]:
        """Generate method declarations."""
        lines = []

        # Group methods
        constructors = [m for m in methods if m.is_constructor]
        destructors = [m for m in methods if m.is_destructor]
        operators = [
            m
            for m in methods
            if not m.is_constructor and not m.is_destructor and m.name.startswith("operator")
        ]
        other_methods = [
            m
            for m in methods
            if not m.is_constructor and not m.is_destructor and not m.name.startswith("operator")
        ]

        # Constructors
        for method in constructors:
            params = self._format_parameters(method)
            lines.append(f"    {method.name}({params});")

        # Destructors
        for method in destructors:
            prefix = "virtual " if method.is_virtual else ""
            lines.append(f"    {prefix}{method.name}();")

        # Regular methods
        for method in other_methods:
            params = self._format_parameters(method)
            prefix = "virtual " if method.is_virtual else ""
            lines.append(f"    {prefix}{method.return_type} {method.name}({params});")

        # Operators
        for method in operators:
            params = self._format_parameters(method)
            prefix = "virtual " if method.is_virtual else ""
            if method.return_type and method.return_type != "void":
                lines.append(f"    {prefix}{method.return_type} {method.name}({params});")
            else:
                lines.append(f"    {prefix}void {method.name}({params});")

        return lines

    def _format_parameters(self, method: MethodInfo) -> str:
        """Format method parameters, filtering artificial ones."""
        if not method.parameters:
            return ""

        param_list = []
        for param in method.parameters:
            # Skip artificial parameters (like 'this')
            if param.name == "__artificial__":
                continue

            param_str = f"{param.type_name} {param.name}"
            if param.default_value:
                param_str += f" = {param.default_value}"
            param_list.append(param_str)

        return ", ".join(param_list)
