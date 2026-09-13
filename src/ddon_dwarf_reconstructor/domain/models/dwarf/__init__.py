#!/usr/bin/env python3

"""DWARF parsing domain models."""

from .class_info import ClassInfo
from .enum_info import EnumeratorInfo, EnumInfo
from .member_info import MemberInfo
from .method_info import MethodInfo
from .parameter_info import ParameterInfo, real_parameters
from .struct_info import StructInfo
from .tag_constants import (
    FORWARD_DECLARABLE_TYPES,
    NAMED_TERMINAL_TYPES,
    PRIMITIVE_TYPE_NAMES,
    TYPE_QUALIFIER_TAGS,
)
from .template_param_info import TemplateTypeParam, TemplateValueParam
from .type_reference import TypeDeclarator, TypeReference
from .union_info import UnionInfo

__all__ = [
    "FORWARD_DECLARABLE_TYPES",
    "NAMED_TERMINAL_TYPES",
    "PRIMITIVE_TYPE_NAMES",
    "TYPE_QUALIFIER_TAGS",
    "ClassInfo",
    "EnumInfo",
    "EnumeratorInfo",
    "MemberInfo",
    "MethodInfo",
    "ParameterInfo",
    "StructInfo",
    "TemplateTypeParam",
    "TemplateValueParam",
    "TypeDeclarator",
    "TypeReference",
    "UnionInfo",
    "real_parameters",
]
