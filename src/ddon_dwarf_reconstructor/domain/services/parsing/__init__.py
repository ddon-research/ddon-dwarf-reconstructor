#!/usr/bin/env python3

"""Parsing services for DWARF debug information."""

from .class_parser import ClassParser
from .type_resolver import LazyTypeResolver

__all__ = [
    "ClassParser",
    "LazyTypeResolver",
]
