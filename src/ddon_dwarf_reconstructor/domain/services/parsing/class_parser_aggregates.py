"""Compatibility exports for aggregate parser operations."""

from .class_parser_aggregate_types import ClassParserAggregateTypesMixin
from .class_parser_class_info import ClassParserClassInfoMixin


class ClassParserAggregatesMixin(ClassParserClassInfoMixin, ClassParserAggregateTypesMixin):
    """Compatibility aggregate-parser mixin."""
