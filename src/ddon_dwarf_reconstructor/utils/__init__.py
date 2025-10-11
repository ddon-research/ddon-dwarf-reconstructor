"""Utilities module initialization."""

from .elf_patches import patch_pyelftools_for_ps4

__all__ = [
    "patch_pyelftools_for_ps4",
]
