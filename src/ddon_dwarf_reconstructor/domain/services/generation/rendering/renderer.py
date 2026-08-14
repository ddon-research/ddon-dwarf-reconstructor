"""Public, typed facade for deterministic header rendering."""

from __future__ import annotations

from typing import ClassVar

from ....models.dwarf import ClassInfo
from ....ports.class_parser import ClassParserPort
from ....ports.dwarf_lookup import DwarfLookupPort
from .context import HeaderRenderContext
from .engine import HeaderRenderingEngine


class HeaderRenderer:
    """Render headers through one explicit composition boundary.

    The underlying collaborators retain the established deterministic
    algorithms.  This facade owns their lifetime and exposes only the
    application-facing operations instead of leaking a multiple-inheritance
    context protocol to callers.
    """

    _engine_type: ClassVar[type[HeaderRenderingEngine]] = HeaderRenderingEngine

    def __init__(
        self, dwarf_index: DwarfLookupPort, class_parser: ClassParserPort | None = None
    ) -> None:
        self.context = HeaderRenderContext(dwarf_index=dwarf_index, class_parser=class_parser)
        self._engine = self._engine_type(self.context)

    @property
    def dwarf_index(self) -> DwarfLookupPort:
        """Expose the read-only lookup dependency for diagnostics and tests."""
        return self.context.dwarf_index

    @property
    def class_parser(self) -> ClassParserPort | None:
        """Expose the optional parser collaborator without mutable setup state."""
        return self.context.class_parser

    def generate_header(
        self,
        class_info: ClassInfo,
        typedefs: dict[str, str] | None = None,
        cu_offset: int | None = None,
        include_metadata: bool = True,
    ) -> str:
        return self._engine.generate_header(class_info, typedefs, cu_offset, include_metadata)

    def generate_single_class_header(
        self,
        class_info: ClassInfo,
        class_dependencies: dict[str, str] | None = None,
        typedefs: dict[str, str] | None = None,
        include_metadata: bool = True,
    ) -> str:
        return self._engine.generate_single_class_header(
            class_info, class_dependencies, typedefs, include_metadata
        )

    def generate_single_file_hierarchy_header(
        self,
        class_infos: dict[str, ClassInfo],
        hierarchy_order: list[str],
        target_class: str,
        typedefs: dict[str, str] | None = None,
        include_metadata: bool = True,
        resolve_forward_declarations: bool = True,
        guard_suffix: str = "_HIERARCHY_H",
        dependency_headers: dict[str, str] | None = None,
        base_type_infos: dict[str, ClassInfo] | None = None,
    ) -> str:
        return self._engine.generate_single_file_hierarchy_header(
            class_infos,
            hierarchy_order,
            target_class,
            typedefs,
            include_metadata,
            resolve_forward_declarations,
            guard_suffix,
            dependency_headers,
            base_type_infos,
        )

    def external_dependency_headers(
        self,
        class_infos: dict[str, ClassInfo],
        rendered_class_names: set[str],
        header_names: dict[str, str],
        typedefs: dict[str, str] | None = None,
    ) -> dict[str, str]:
        return self._engine.external_dependency_headers(
            class_infos, rendered_class_names, header_names, typedefs
        )

    def stable_topological_order(
        self, dependencies: dict[str, set[str]], hierarchy_order: list[str]
    ) -> list[str]:
        """Expose the deterministic ordering primitive for focused tests."""
        return self._engine.stable_topological_order(dependencies, hierarchy_order)

    @staticmethod
    def _template_forward_declaration(type_name: str) -> str | None:
        return HeaderRenderingEngine._template_forward_declaration(type_name)

    @staticmethod
    def _template_argument_forward_declarations(
        expression: str, typedef_names: set[str]
    ) -> set[str]:
        return HeaderRenderingEngine._template_argument_forward_declarations(
            expression, typedef_names
        )
