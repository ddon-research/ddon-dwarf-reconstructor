"""Header type-planning operations."""

from __future__ import annotations

import re

from ....core.observability import get_logger
from ...models.analytical_dwarf import QueryStatus
from ...models.dwarf import ClassInfo, StructInfo
from ...ports.dwarf_lookup import DwarfLookupPort
from ..parsing.template_argument_parser import split_template_arguments
from .rendering.type_policy import TypeExpressionPolicy
from .scoped_declarations import scoped_declaration

logger = get_logger(__name__)


class HeaderTypePlanningService:
    dwarf_index: DwarfLookupPort

    def _forward_declaration_kind(self, name: str) -> str | None:
        """Resolve the aggregate kind for an opaque name through the DWARF index."""
        clean_name = self._unqualify_type_expression(name).strip()
        cache = self._forward_declaration_kind_cache
        if clean_name in cache:
            return cache[clean_name]

        kind: str | None = None
        tag_result = self.dwarf_index.find_definition_tag(clean_name)
        if tag_result.status is QueryStatus.COMPLETE and tag_result.items:
            kind = {
                "DW_TAG_class_type": "class",
                "DW_TAG_structure_type": "struct",
                "DW_TAG_union_type": "union",
            }.get(str(tag_result.items[0]))
            if kind is not None:
                cache[clean_name] = kind
                return kind
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
                for token in re.findall(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", underlying_type)
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
                raise ValueError(
                    f"Cannot order cyclic typedef dependencies: {', '.join(sorted(remaining))}"
                )
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
                raise ValueError(
                    f"Cannot order cyclic nested struct dependencies: {', '.join(sorted(remaining))}"
                )
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
        return split_template_arguments(arguments)

    @staticmethod
    def _forward_declaration_name(declaration: str) -> str:
        """Extract the declared type name from a C++ forward declaration."""
        match = re.search(
            r"(?:(?:enum\s+)?class|struct|union)\s+([A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)(?:\s*:\s*\w+)?\s*;",
            declaration,
        )
        if match is None:
            return declaration
        namespace = re.match(r"namespace\s+([A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)\s*\{", declaration)
        return f"{namespace.group(1)}::{match.group(1)}" if namespace else match.group(1)

    @staticmethod
    def _forward_declaration_order(declaration: str) -> tuple[int, str]:
        """Emit template primaries before dependent explicit specializations."""
        stripped = declaration.lstrip()
        if stripped.startswith("template "):
            return 0, declaration
        if stripped.startswith("enum "):
            return 1, declaration
        return 2, declaration

    @staticmethod
    def _normalize_type_name(type_name: str) -> str:
        """Remove qualifiers and indirection from a referenced type name."""
        clean_name = HeaderTypePlanningService._unqualify_type_expression(type_name.strip())
        clean_name = re.sub(r"\b(?:const|volatile|restrict)\b\s*", "", clean_name)
        clean_name = re.sub(r"\b(?:class|struct|union|enum)\b\s*", "", clean_name)
        clean_name = re.sub(r"\s*[*&]+\s*$", "", clean_name)
        clean_name = re.sub(r"\s*\[[^\]]*\]\s*$", "", clean_name)
        return clean_name.strip()

    @staticmethod
    def _lookup_type_name(type_name: str) -> str:
        """Normalize a type for identity lookup while retaining C++ scopes."""
        clean_name = type_name.strip()
        clean_name = re.sub(r"\b(?:const|volatile|restrict)\b\s*", "", clean_name)
        clean_name = re.sub(r"\b(?:class|struct|union|enum)\b\s*", "", clean_name)
        clean_name = re.sub(r"\s*[*&]+\s*$", "", clean_name)
        clean_name = re.sub(r"\s*\[[^\]]*\]\s*$", "", clean_name)
        return re.sub(r"\s+", " ", clean_name).strip()

    @classmethod
    def _is_opaque_candidate(cls, name: str) -> bool:
        """Return whether a name is eligible for opaque class forward declaration."""
        return (
            bool(name)
            and not cls._is_template_placeholder(name)
            and not cls._is_builtin_type(name)
            and name not in TypeExpressionPolicy.primitive_names()
            and not name.startswith("std::")
            and name not in {"false", "true", "nullptr"}
        )

    @staticmethod
    def _is_template_placeholder(name: str) -> bool:
        """Reject synthetic template parameter tokens as declarations.

        Generic projections use conventional names (``T``, ``U``, ``N`` and
        ``P0``) for parameters that have no standalone C++ type.  Treating a
        projected occurrence as ``class T;`` leaves an invalid placeholder in
        otherwise valid headers and can collide with a real declaration.
        """
        return re.fullmatch(r"(?:T|U|V|W|N\d*|P\d+)", name.strip()) is not None

    @classmethod
    def _member_pointer_scope(cls, clean_name: str) -> str | None:
        """Extract the class scope from a pointer-to-member type expression."""
        match = re.search(r"([A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)::\*", clean_name)
        if not match:
            return None
        scope = match.group(1)
        return scope if cls._is_opaque_candidate(scope) else None

    @classmethod
    def _collect_typedef_forward_declarations(
        cls,
        typedefs: dict[str, str],
    ) -> set[str]:
        """Collect opaque declarations required before typedef aliases."""
        declarations: set[str] = set()
        typedef_names = set(typedefs)

        for typedef_name, underlying_type in typedefs.items():
            # Keep qualified owners and arguments intact while inspecting the
            # declarator.  The rendering normalizer intentionally flattens
            # scopes for unavailable enclosing definitions, which would turn
            # ``ns::Owner::*`` into a global ``Owner::*`` here.
            clean_name = cls._lookup_type_name(underlying_type)
            if not clean_name:
                continue

            if typedef_name == clean_name:
                if re.fullmatch(r"[A-Za-z_]\w*", typedef_name) and cls._is_opaque_candidate(
                    typedef_name
                ):
                    declarations.add(f"class {typedef_name};")
                continue

            declarations.update(cls._template_forward_declarations(clean_name, typedef_names))

            if clean_name not in typedef_names:
                decl = cls._candidate_typedef_forward_declaration(clean_name)
                if decl is not None:
                    declarations.add(decl)

        return declarations

    @classmethod
    def _candidate_typedef_forward_declaration(cls, clean_name: str) -> str | None:
        scope = cls._member_pointer_scope(clean_name)
        if scope is not None:
            return cls._scoped_forward_declaration(scope)
        candidate_match = re.match(r"([A-Za-z_]\w*(?:::[A-Za-z_]\w*)*)", clean_name)
        if not candidate_match or not cls._is_opaque_candidate(candidate_match.group(1)):
            return None
        candidate = candidate_match.group(1)
        # A specialization's spelling supplies neither the primary's signature
        # nor evidence that the primary is a non-template aggregate.
        return None if "<" in clean_name else scoped_declaration(candidate)

    @classmethod
    def _scoped_forward_declaration(cls, name: str) -> str | None:
        """Render an owner forward without erasing a namespace qualification."""
        if not cls._is_opaque_candidate(name):
            return None
        return scoped_declaration(name)

    @classmethod
    def _template_forward_declarations(cls, clean_name: str, typedef_names: set[str]) -> set[str]:
        declarations: set[str] = set()
        for expression in cls._template_expressions(clean_name):
            primary = expression.split("<", 1)[0].strip()
            if primary.startswith("std::") or primary in typedef_names:
                continue
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
            declarations.update(cls._template_argument_forward(argument, typedef_names))
        return declarations

    @classmethod
    def _template_argument_forward(cls, argument: str, typedef_names: set[str]) -> set[str]:
        """Forward-declare one template argument while preserving its scope."""
        if "(" in argument or ")" in argument:
            return set()
        candidate = cls._lookup_type_name(argument)
        match = re.match(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", candidate)
        if match is None:
            return set()
        candidate_name = match.group(0)
        if (
            candidate_name in typedef_names
            or candidate_name.startswith("std::")
            or not cls._is_opaque_candidate(candidate_name)
        ):
            return set()
        if "<" in candidate:
            return cls._template_argument_forward_declarations(candidate, typedef_names)
        declaration = scoped_declaration(candidate_name)
        return {declaration} if declaration is not None else set()

    @staticmethod
    def _is_builtin_type(type_name: str) -> bool:
        """Return whether a type expression contains only built-in type words."""
        return TypeExpressionPolicy.is_builtin(type_name)

    @staticmethod
    def _referenced_class_name(type_name: str, class_names: set[str]) -> str | None:
        """Match a member's value type to a resolved class or template name."""
        lookup_name = HeaderTypePlanningService._lookup_type_name(type_name)
        if lookup_name in class_names:
            return lookup_name
        clean_name = HeaderTypePlanningService._normalize_type_name(type_name)
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
            nested_classes.extend(HeaderTypePlanningService._iter_nested_classes(nested_class))
        return nested_classes
