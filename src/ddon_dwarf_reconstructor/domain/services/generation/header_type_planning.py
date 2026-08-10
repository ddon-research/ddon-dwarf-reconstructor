"""Header type-planning operations."""

from __future__ import annotations

import re

from ....core.observability import get_logger
from ...models.dwarf import ClassInfo, StructInfo
from ...ports.dwarf_lookup import DwarfLookupPort

logger = get_logger(__name__)


class HeaderTypePlanningMixin:
    dwarf_index: DwarfLookupPort

    def _forward_declaration_kind(self, name: str) -> str | None:
        """Resolve the aggregate kind for an opaque name through the DWARF index."""
        clean_name = self._unqualify_type_expression(name).strip()
        cache = getattr(self, "_forward_declaration_kind_cache", {})
        if clean_name in cache:
            return cache[clean_name]

        kind: str | None = None
        offset = self.dwarf_index.find_symbol_offset(clean_name)
        die = self.dwarf_index.get_die_by_offset(offset) if offset is not None else None
        tag_kind = {
            "DW_TAG_class_type": "class",
            "DW_TAG_structure_type": "struct",
            "DW_TAG_union_type": "union",
        }
        if die is not None:
            kind = tag_kind.get(die.tag)
        cache[clean_name] = kind
        self._forward_declaration_kind_cache = cache
        return kind

    @staticmethod
    def _unqualify_type_expression(type_name: str) -> str:
        """Render flattened hierarchy types without unavailable enclosing scopes."""
        return re.sub(r"\b[A-Za-z_]\w*::(?=[A-Za-z_]\w*)", "", type_name)

    @classmethod
    def _template_forward_declaration(cls, type_name: str) -> str | None:
        """Build a forward declaration with one parameter per specialization argument."""
        opening = type_name.find("<")
        if opening <= 0 or not type_name.endswith(">"):
            return None
        primary = cls._unqualify_type_expression(type_name[:opening].strip())
        if not re.fullmatch(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", primary):
            return None
        arguments = cls._split_template_arguments(type_name[opening + 1 : -1])
        if not arguments:
            return None
        parameters = cls._template_parameter_declarations(arguments)
        return f"template <{', '.join(parameters)}> class {primary};"

    @classmethod
    def _template_parameter_declaration(cls, type_name: str) -> str | None:
        """Return the parameter list needed by a recovered template primary."""
        opening = type_name.find("<")
        if opening <= 0 or not type_name.endswith(">"):
            return None
        arguments = cls._split_template_arguments(type_name[opening + 1 : -1])
        if not arguments:
            return None
        return f"template <{', '.join(cls._template_parameter_declarations(arguments))}>"

    @staticmethod
    def _template_parameter_declarations(arguments: list[str]) -> list[str]:
        type_names = ("T", "U", "V", "W")
        return [
            f"auto N{index}"
            if re.fullmatch(r"[-+]?\d+|true|false", argument.strip())
            else f"typename {type_names[index] if index < len(type_names) else f'T{index}'}"
            for index, argument in enumerate(arguments)
        ]

    @classmethod
    def _template_expressions(cls, type_name: str) -> list[str]:
        """Extract nested template expressions from a declaration type."""
        expressions: list[str] = []
        for match in re.finditer(r"([A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)\s*<", type_name):
            opening = type_name.find("<", match.start())
            depth = 0
            for index in range(opening, len(type_name)):
                character = type_name[index]
                if character == "<":
                    depth += 1
                elif character == ">":
                    depth -= 1
                    if depth == 0:
                        expression = type_name[match.start() : index + 1].strip()
                        if expression not in expressions:
                            expressions.append(expression)
                        break
        return expressions

    @classmethod
    def _ordered_typedefs(cls, typedefs: dict[str, str]) -> list[tuple[str, str]]:
        """Emit typedefs after aliases used by their underlying expressions."""
        dependencies = cls._typedef_dependencies(typedefs)
        ordered = cls._topological_typedef_names(dependencies)
        return [(name, typedefs[name]) for name in ordered]

    @staticmethod
    def _typedef_dependencies(typedefs: dict[str, str]) -> dict[str, set[str]]:
        names = set(typedefs)
        return {
            name: {
                token
                for token in re.findall(r"[A-Za-z_]\w*", underlying_type)
                if token in names and token != name
            }
            for name, underlying_type in typedefs.items()
        }

    @staticmethod
    def _topological_typedef_names(dependencies: dict[str, set[str]]) -> list[str]:
        remaining = dict(dependencies)
        ordered: list[str] = []
        while remaining:
            ready = sorted(name for name, required in remaining.items() if not required)
            if not ready:
                ready = [min(remaining)]
            for name in ready:
                if name not in remaining:
                    continue
                ordered.append(name)
                del remaining[name]
                for required in remaining.values():
                    required.discard(name)
        return ordered

    @classmethod
    def _ordered_structs(cls, structs: list[StructInfo]) -> list[StructInfo]:
        """Order nested structs so complete by-value members precede their users."""
        named = cls._named_structs(structs)
        names, original_order = cls._struct_names_and_order(named)
        dependencies = cls._empty_struct_dependencies(names)
        cls._populate_struct_dependencies(named, names, dependencies)
        ordered_names = cls._topological_struct_names(dependencies, original_order)
        return cls._ordered_struct_results(ordered_names, named, structs)

    @staticmethod
    def _named_structs(structs: list[StructInfo]) -> list[StructInfo]:
        return [struct for struct in structs if struct.name]

    @staticmethod
    def _struct_names_and_order(structs: list[StructInfo]) -> tuple[set[str], list[str]]:
        original_order = [struct.name for struct in structs if struct.name is not None]
        return set(original_order), original_order

    @staticmethod
    def _empty_struct_dependencies(names: set[str]) -> dict[str, set[str]]:
        return {name: set() for name in names}

    @staticmethod
    def _ordered_struct_results(
        ordered_names: list[str], named: list[StructInfo], structs: list[StructInfo]
    ) -> list[StructInfo]:
        by_name = {struct.name: struct for struct in named if struct.name is not None}
        ordered = [by_name[name] for name in ordered_names]
        return ordered + [struct for struct in structs if not struct.name]

    @classmethod
    def _populate_struct_dependencies(
        cls,
        structs: list[StructInfo],
        names: set[str],
        dependencies: dict[str, set[str]],
    ) -> None:
        for struct in structs:
            assert struct.name is not None
            dependencies[struct.name].update(
                dependency
                for member in struct.members
                if "*" not in member.type_name
                and "&" not in member.type_name
                and (dependency := cls._referenced_class_name(member.type_name, names))
                and dependency != struct.name
            )

    @classmethod
    def _topological_struct_names(
        cls, dependencies: dict[str, set[str]], original_order: list[str]
    ) -> list[str]:
        remaining = {name: set(required) for name, required in dependencies.items()}
        ordered_names: list[str] = []
        while remaining:
            ready = cls._ready_struct_names(remaining, original_order)
            if not ready:
                ready = [name for name in original_order if name in remaining][:1]
            cls._consume_struct_names(ready, remaining, ordered_names)
        return ordered_names

    @staticmethod
    def _ready_struct_names(remaining: dict[str, set[str]], original_order: list[str]) -> list[str]:
        return [name for name in original_order if name in remaining and not remaining[name]]

    @staticmethod
    def _consume_struct_names(
        ready: list[str], remaining: dict[str, set[str]], ordered_names: list[str]
    ) -> None:
        for name in ready:
            ordered_names.append(name)
            del remaining[name]
            for required in remaining.values():
                required.discard(name)

    @staticmethod
    def _split_template_arguments(arguments: str) -> list[str]:
        parts: list[str] = []
        start = 0
        depth = 0
        for index, character in enumerate(arguments):
            if character == "<":
                depth += 1
            elif character == ">":
                depth -= 1
            elif character == "," and depth == 0:
                parts.append(arguments[start:index].strip())
                start = index + 1
        final = arguments[start:].strip()
        if final:
            parts.append(final)
        return parts

    @staticmethod
    def _forward_declaration_name(declaration: str) -> str:
        """Extract the declared type name from a C++ forward declaration."""
        match = re.search(
            r"(?:class|struct|union)\s+([A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)\s*;",
            declaration,
        )
        return match.group(1) if match else declaration

    @staticmethod
    def _normalize_type_name(type_name: str) -> str:
        """Remove qualifiers and indirection from a referenced type name."""
        clean_name = HeaderTypePlanningMixin._unqualify_type_expression(type_name.strip())
        clean_name = re.sub(r"\b(?:const|volatile|restrict)\b\s*", "", clean_name)
        clean_name = re.sub(r"\b(?:class|struct|union|enum)\b\s*", "", clean_name)
        clean_name = re.sub(r"\s*[*&]+\s*$", "", clean_name)
        clean_name = re.sub(r"\s*\[[^\]]*\]\s*$", "", clean_name)
        return clean_name.strip()

    @classmethod
    def _collect_typedef_forward_declarations(
        cls,
        typedefs: dict[str, str],
    ) -> set[str]:
        """Collect opaque declarations required before typedef aliases."""
        declarations: set[str] = set()
        typedef_names = set(typedefs)

        for typedef_name, underlying_type in typedefs.items():
            clean_name = cls._normalize_type_name(underlying_type)
            if not clean_name:
                continue

            if typedef_name == clean_name:
                if re.fullmatch(r"[A-Za-z_]\w*", typedef_name):
                    declarations.add(f"class {typedef_name};")
                continue

            declarations.update(cls._template_forward_declarations(clean_name, typedef_names))

            if clean_name in typedef_names:
                continue

            candidate_match = re.match(r"([A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)", clean_name)
            if not candidate_match:
                continue

            candidate = candidate_match.group(1)
            if cls._is_builtin_type(clean_name) or candidate.startswith("std::"):
                continue

            template_declaration = cls._template_forward_declaration(clean_name)
            if template_declaration is not None:
                declarations.add(template_declaration)
            else:
                declarations.add(f"class {candidate};")

        return declarations

    @classmethod
    def _template_forward_declarations(cls, clean_name: str, typedef_names: set[str]) -> set[str]:
        declarations: set[str] = set()
        for expression in cls._template_expressions(clean_name):
            primary = expression.split("<", 1)[0].strip()
            if primary.startswith("std::") or primary in typedef_names:
                continue
            declaration = cls._template_forward_declaration(expression)
            if declaration is not None:
                declarations.add(declaration)
            declarations.update(
                cls._template_argument_forward_declarations(expression, typedef_names)
            )
        return declarations

    @classmethod
    def _template_argument_forward_declarations(
        cls, expression: str, typedef_names: set[str]
    ) -> set[str]:
        opening = expression.find("<")
        if opening < 0:
            return set()
        declarations: set[str] = set()
        arguments = cls._split_template_arguments(expression[opening + 1 : -1])
        for argument in arguments:
            candidate = cls._normalize_type_name(argument)
            match = re.match(r"[A-Za-z_]\w*", candidate)
            if not match:
                continue
            candidate_name = match.group(0)
            if (
                candidate_name in typedef_names
                or candidate_name in {"false", "true", "nullptr"}
                or cls._is_builtin_type(candidate_name)
                or "(" in argument
                or ")" in argument
            ):
                continue
            nested_template = cls._template_forward_declaration(candidate)
            if nested_template is not None:
                declarations.add(nested_template)
                declarations.update(
                    cls._template_argument_forward_declarations(candidate, typedef_names)
                )
            else:
                declarations.add(f"class {candidate_name};")
        return declarations

    @staticmethod
    def _is_builtin_type(type_name: str) -> bool:
        """Return whether a type expression contains only built-in type words."""
        builtin_words = {
            "bool",
            "char",
            "double",
            "float",
            "int",
            "long",
            "short",
            "signed",
            "unsigned",
            "void",
            "wchar_t",
            "size_t",
            "uint8_t",
            "uint16_t",
            "uint32_t",
            "uint64_t",
            "int8_t",
            "int16_t",
            "int32_t",
            "int64_t",
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
        }
        words = set(re.findall(r"[A-Za-z_]\w*", type_name))
        return bool(words) and words <= builtin_words

    @staticmethod
    def _referenced_class_name(type_name: str, class_names: set[str]) -> str | None:
        """Match a member's value type to a resolved class or template name."""
        clean_name = HeaderTypePlanningMixin._normalize_type_name(type_name)
        if clean_name in class_names:
            return clean_name
        template_match = re.match(r"([A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)\s*<", clean_name)
        candidate = (
            template_match.group(1) if template_match else re.split(r"[\s\[]", clean_name)[0]
        )
        if candidate in class_names:
            return candidate
        matching_specializations = sorted(
            class_name for class_name in class_names if class_name.startswith(f"{candidate}<")
        )
        return matching_specializations[0] if len(matching_specializations) == 1 else None

    @staticmethod
    def _iter_nested_classes(class_info: ClassInfo) -> list[ClassInfo]:
        """Return nested classes recursively in declaration order."""
        nested_classes: list[ClassInfo] = []
        for nested_class in class_info.nested_classes:
            nested_classes.append(nested_class)
            nested_classes.extend(HeaderTypePlanningMixin._iter_nested_classes(nested_class))
        return nested_classes
