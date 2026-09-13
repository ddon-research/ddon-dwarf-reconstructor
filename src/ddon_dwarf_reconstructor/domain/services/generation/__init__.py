#!/usr/bin/env python3

"""Generation services for C++ header creation."""

from .dependency_extractor import DependencyExtractor
from .file_registry import FileRegistry
from .header_dependency_plan import HeaderDependencyPlan
from .hierarchy_builder import HierarchyBuilder
from .method_definition_rendering import MethodDefinitionRenderingService
from .packing_analyzer import calculate_packing_info
from .rendering import HeaderRenderContext, HeaderRenderer, TypeExpressionPolicy
from .special_header_renderer import SpecialHeaderRenderer

__all__ = [
    "DependencyExtractor",
    "FileRegistry",
    "HeaderDependencyPlan",
    "HeaderRenderContext",
    "HeaderRenderer",
    "HierarchyBuilder",
    "MethodDefinitionRenderingService",
    "SpecialHeaderRenderer",
    "TypeExpressionPolicy",
    "calculate_packing_info",
]
