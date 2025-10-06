"""Utilities module initialization."""

from .elf_patches import patch_pyelftools_for_ps4
from .quick_search import quick_search_by_name

__all__ = [
    "patch_pyelftools_for_ps4",
    "quick_search_by_name"
]
