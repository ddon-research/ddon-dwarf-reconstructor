"""Member-type recovery operations for the class-parser façade."""

from __future__ import annotations

from collections.abc import Mapping

from ....core.dwarf import DwarfEntry
from ....core.observability import get_logger
from ...models.dwarf import StructInfo, TypeDeclarator, TypeReference
from ...ports.type_resolution import TypeNameResolver
from .class_parser_context import ClassParserContext
from .type_chain_traverser import TypeChainTraverser

logger = get_logger(__name__)


class ClassParserMemberTypesMixin:
    """Recover inline aggregates and safe storage fallbacks for members."""

    @staticmethod
    def _member_type_die(member_die: DwarfEntry) -> DwarfEntry | None:
        if "DW_AT_type" not in member_die.attributes:
            return None
        return member_die.get_DIE_from_attribute("DW_AT_type")

    def _inline_struct_type(
        self: ClassParserContext, type_die: DwarfEntry | None
    ) -> StructInfo | None:
        if type_die is None or type_die.tag not in {"DW_TAG_class_type", "DW_TAG_structure_type"}:
            return None
        if "DW_AT_name" in type_die.attributes:
            return None
        return self.parse_nested_structure(type_die)

    @staticmethod
    def _opaque_storage_size(
        member_die: DwarfEntry,
        type_die: DwarfEntry | None,
        type_name: str | None = None,
    ) -> int | None:
        """Use byte storage when flattening would make an alternate type recursive."""
        aggregate = ClassParserMemberTypesMixin._named_aggregate(type_die)
        handled, size = ClassParserMemberTypesMixin._recursive_aggregate_storage(
            member_die, aggregate
        )
        if handled:
            return size

        terminal_type = (
            TypeChainTraverser.follow_to_terminal_type(type_die) if type_die is not None else None
        )
        if ClassParserMemberTypesMixin._needs_terminal_storage(member_die, terminal_type):
            return ClassParserMemberTypesMixin._byte_size(type_die)

        return ClassParserMemberTypesMixin._unresolved_storage_size(member_die, type_die, type_name)

    @staticmethod
    def _recursive_aggregate_storage(
        member_die: DwarfEntry, aggregate: DwarfEntry | None
    ) -> tuple[bool, int | None]:
        if aggregate is None:
            return False, None
        try:
            parent = member_die.get_parent()
        except AttributeError, RuntimeError:
            return True, None
        if ClassParserMemberTypesMixin._has_same_name(parent, aggregate):
            return True, ClassParserMemberTypesMixin._byte_size(aggregate)
        return False, None

    @staticmethod
    def _needs_terminal_storage(member_die: DwarfEntry, terminal_type: DwarfEntry | None) -> bool:
        if terminal_type is None:
            return False
        if ClassParserMemberTypesMixin._named_aggregate(terminal_type) is None:
            return False
        return ClassParserMemberTypesMixin._is_declaration_only(
            terminal_type
        ) or ClassParserMemberTypesMixin._same_named_parent(member_die, terminal_type)

    @staticmethod
    def _unresolved_storage_size(
        member_die: DwarfEntry, type_die: DwarfEntry | None, type_name: str | None
    ) -> int | None:
        if not ClassParserMemberTypesMixin._is_unresolved_type_name(type_name):
            return None
        return ClassParserMemberTypesMixin._byte_size(type_die) or (
            ClassParserMemberTypesMixin._byte_size(member_die)
        )

    @staticmethod
    def _byte_size(die: DwarfEntry | None) -> int | None:
        if die is None:
            return None
        size_attr = die.attributes.get("DW_AT_byte_size")
        size = getattr(size_attr, "value", None)
        return size if isinstance(size, int) and size > 0 else None

    @staticmethod
    def _is_unresolved_type_name(type_name: str | None) -> bool:
        if type_name is None:
            return True
        clean_name = type_name.strip()
        return clean_name in {"void", "unknown_type"} or clean_name.startswith(
            ("void[", "unknown_type[")
        )

    @staticmethod
    def _is_declaration_only(type_die: DwarfEntry) -> bool:
        """Return whether a named aggregate has no recoverable definition."""
        declaration = type_die.attributes.get("DW_AT_declaration")
        if declaration is not None and bool(getattr(declaration, "value", declaration)):
            return True
        try:
            return not any(type_die.iter_children())
        except AttributeError, RuntimeError, TypeError:
            return True

    @staticmethod
    def _same_named_parent(member_die: DwarfEntry, type_die: DwarfEntry) -> bool:
        try:
            parent = member_die.get_parent()
        except AttributeError, RuntimeError:
            return False
        return ClassParserMemberTypesMixin._has_same_name(parent, type_die)

    def _template_argument_references(
        self: ClassParserContext, type_die: DwarfEntry | None
    ) -> tuple[TypeReference, ...]:
        return ClassParserMemberTypesMixin._template_argument_references_from_die(
            self.type_resolver, type_die, set()
        )

    @staticmethod
    def _template_argument_references_from_die(
        type_resolver: TypeNameResolver,
        type_die: DwarfEntry | None,
        visited_offsets: set[int],
    ) -> tuple[TypeReference, ...]:
        terminal_die = (
            TypeChainTraverser.follow_to_terminal_type(type_die) if type_die is not None else None
        )
        if terminal_die is None:
            return ()
        if terminal_die.offset in visited_offsets:
            return ()
        visited_offsets = visited_offsets | {terminal_die.offset}

        references: list[TypeReference] = []
        try:
            for child in terminal_die.iter_children():
                if child.tag != "DW_TAG_template_type_param":
                    continue
                argument_name = type_resolver.resolve_type_name(child)
                if not argument_name:
                    continue
                argument_offset = TypeChainTraverser.get_terminal_type_offset(child)
                argument_type_die = child.get_DIE_from_attribute("DW_AT_type")
                references.append(
                    TypeReference(
                        declarator=TypeDeclarator(
                            base_name=argument_name,
                            unresolved=argument_name in {"void", "unknown_type"},
                        ),
                        die_offset=argument_offset,
                        template_arguments=ClassParserMemberTypesMixin._template_argument_references_from_die(
                            type_resolver, argument_type_die, visited_offsets
                        ),
                    )
                )
        except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
            logger.debug("Failed to resolve template arguments: %s", error, exc_info=error)
        return tuple(references)

    @staticmethod
    def _named_aggregate(type_die: DwarfEntry | None) -> DwarfEntry | None:
        if type_die is None or type_die.tag not in {
            "DW_TAG_class_type",
            "DW_TAG_structure_type",
            "DW_TAG_union_type",
        }:
            return None
        return type_die if "DW_AT_name" in type_die.attributes else None

    @staticmethod
    def _has_same_name(parent: object, type_die: DwarfEntry) -> bool:
        if not isinstance(getattr(parent, "tag", None), str):
            return False
        attributes = getattr(parent, "attributes", None)
        if not isinstance(attributes, Mapping):
            return False
        parent_name = attributes.get("DW_AT_name")
        type_name = type_die.attributes.get("DW_AT_name")
        if parent_name is None or type_name is None:
            return False
        if parent_name.value != type_name.value:
            return False
        return getattr(parent, "offset", None) != type_die.offset
