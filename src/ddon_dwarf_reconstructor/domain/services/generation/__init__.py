#!/usr/bin/env python3

"""Generation services for C++ header creation."""

from .dependency_extractor import DependencyExtractor
from .file_registry import FileRegistry
from .hierarchy_builder import HierarchyBuilder
from .packing_analyzer import calculate_packing_info
from .rendering import HeaderRenderContext, HeaderRenderer, TypeExpressionPolicy
from .special_header_renderer import SpecialHeaderRenderer

__all__ = [
    "DependencyExtractor",
    "FileRegistry",
    "HeaderRenderContext",
    "HeaderRenderer",
    "HierarchyBuilder",
    "TypeExpressionPolicy",
    "calculate_packing_info",
    "SpecialHeaderRenderer",
]
