"""Composed implementation of deterministic C++ header rendering."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import MethodType
from typing import cast

from ....models.dwarf import ClassInfo
from ....ports.class_parser import ClassParserPort
from ....ports.dwarf_lookup import DwarfLookupPort
from ..header_aggregate_rendering import HeaderAggregateRenderingService
from ..header_forward_declarations import HeaderForwardDeclarationService
from ..header_hierarchy import HierarchyHeaderGenerationService
from ..header_member_rendering import HeaderMemberRenderingService
from ..header_method_rendering import HeaderMethodRenderingService
from ..header_nested_rendering import HeaderNestedRenderingService
from ..header_ordering import HeaderOrderingService
from ..header_single import SingleHeaderGenerationService
from ..header_type_planning import HeaderTypePlanningService
from .context import HeaderRenderContext


@dataclass(slots=True)
class HeaderRenderingComponents:
    """The focused algorithms that make up one renderer instance.

    The component list is deliberately explicit.  The algorithms are kept as
    small method containers for now, but their collaboration is assembled by
    ``_HeaderRenderingHost`` instead of by a multiple-inheritance MRO.
    """

    single: SingleHeaderGenerationService
    hierarchy: HierarchyHeaderGenerationService
    type_planning: HeaderTypePlanningService
    ordering: HeaderOrderingService
    forward_declarations: HeaderForwardDeclarationService
    members: HeaderMemberRenderingService
    nested: HeaderNestedRenderingService
    aggregates: HeaderAggregateRenderingService
    methods: HeaderMethodRenderingService

    @classmethod
    def create(cls) -> HeaderRenderingComponents:
        """Construct the stateless rendering collaborators in one place."""
        return cls(
            single=SingleHeaderGenerationService(),
            hierarchy=HierarchyHeaderGenerationService(),
            type_planning=HeaderTypePlanningService(),
            ordering=HeaderOrderingService(),
            forward_declarations=HeaderForwardDeclarationService(),
            members=HeaderMemberRenderingService(),
            nested=HeaderNestedRenderingService(),
            aggregates=HeaderAggregateRenderingService(),
            methods=HeaderMethodRenderingService(),
        )


class _HeaderRenderingHost:
    """Runtime host shared by the composed algorithm collaborators.

    Existing algorithms call one another through their operation names.  A
    host keeps that implementation detail private while giving every call a
    single, per-renderer state object.  Only methods declared by the explicit
    component list are bound; unknown operations fail during construction.
    """

    def __init__(self, context: HeaderRenderContext, components: HeaderRenderingComponents) -> None:
        self.dwarf_index: DwarfLookupPort = context.dwarf_index
        self.class_parser: ClassParserPort | None = context.class_parser
        self._base_type_names: dict[int, str] = {}
        self._known_render_type_names: set[str] = set()
        self._forward_declaration_kind_cache: dict[str, str | None] = {}
        self._bindings: dict[str, Callable[..., object]] = {}
        self._bind_components(components)

    def _bind_components(self, components: HeaderRenderingComponents) -> None:
        for component in (
            components.single,
            components.hierarchy,
            components.type_planning,
            components.ordering,
            components.forward_declarations,
            components.members,
            components.nested,
            components.aggregates,
            components.methods,
        ):
            for name, descriptor in vars(type(component)).items():
                if not callable(descriptor) and not isinstance(
                    descriptor, (staticmethod, classmethod)
                ):
                    continue
                if name in self._bindings:
                    raise RuntimeError(f"duplicate header rendering operation: {name}")
                if isinstance(descriptor, staticmethod):
                    bound: Callable[..., object] = descriptor.__func__
                elif isinstance(descriptor, classmethod):
                    bound = MethodType(descriptor.__func__, self)
                else:
                    bound = MethodType(descriptor, self)
                self._bindings[name] = bound
                setattr(self, name, bound)

    def invoke(self, operation: str, *args: object, **kwargs: object) -> object:
        """Invoke a declared operation without exposing collaborator classes."""
        try:
            bound = self._bindings[operation]
        except KeyError as error:
            raise RuntimeError(f"unknown header rendering operation: {operation}") from error
        return bound(*args, **kwargs)


class HeaderRenderingEngine:
    """Typed boundary over explicitly composed rendering collaborators."""

    def __init__(self, context: HeaderRenderContext) -> None:
        self._host = _HeaderRenderingHost(context, HeaderRenderingComponents.create())

    def generate_header(
        self,
        class_info: ClassInfo,
        typedefs: dict[str, str] | None = None,
        cu_offset: int | None = None,
        include_metadata: bool = True,
    ) -> str:
        return cast(
            str,
            self._host.invoke("generate_header", class_info, typedefs, cu_offset, include_metadata),
        )

    def generate_single_class_header(
        self,
        class_info: ClassInfo,
        class_dependencies: dict[str, str] | None = None,
        typedefs: dict[str, str] | None = None,
        include_metadata: bool = True,
    ) -> str:
        return cast(
            str,
            self._host.invoke(
                "generate_single_class_header",
                class_info,
                class_dependencies,
                typedefs,
                include_metadata,
            ),
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
        return cast(
            str,
            self._host.invoke(
                "generate_single_file_hierarchy_header",
                class_infos,
                hierarchy_order,
                target_class,
                typedefs,
                include_metadata,
                resolve_forward_declarations,
                guard_suffix,
                dependency_headers,
                base_type_infos,
            ),
        )

    def external_dependency_headers(
        self,
        class_infos: dict[str, ClassInfo],
        rendered_class_names: set[str],
        header_names: dict[str, str],
        typedefs: dict[str, str] | None = None,
    ) -> dict[str, str]:
        return cast(
            dict[str, str],
            self._host.invoke(
                "external_dependency_headers",
                class_infos,
                rendered_class_names,
                header_names,
                typedefs,
            ),
        )

    def stable_topological_order(
        self, dependencies: dict[str, set[str]], hierarchy_order: list[str]
    ) -> list[str]:
        """Expose the deterministic ordering primitive for focused tests."""
        return cast(
            list[str], self._host.invoke("_stable_topological_order", dependencies, hierarchy_order)
        )

    @staticmethod
    def _template_forward_declaration(type_name: str) -> str | None:
        return HeaderTypePlanningService._template_forward_declaration(type_name)

    @staticmethod
    def _template_argument_forward_declarations(
        expression: str, typedef_names: set[str]
    ) -> set[str]:
        return HeaderTypePlanningService._template_argument_forward_declarations(
            expression, typedef_names
        )
