#!/usr/bin/env python3

"""C++ header generation from DWARF ClassInfo structures - ENHANCED VERSION.

This module generates C++ header files from parsed ClassInfo objects,
handling formatting, forward declarations, and proper C++ syntax with
correct array declaration handling.
"""

from typing import TYPE_CHECKING

from ....core.observability import get_logger
from ...ports.class_parser import ClassParserPort
from ...ports.dwarf_index import DwarfIndexPort
from .header_aggregate_rendering import HeaderAggregateRenderingMixin
from .header_forward_declarations import HeaderForwardDeclarationMixin
from .header_generator_context import HeaderGeneratorContext
from .header_hierarchy import HierarchyHeaderGenerationMixin
from .header_member_rendering import HeaderMemberRenderingMixin
from .header_method_rendering import HeaderMethodRenderingMixin
from .header_ordering import HeaderOrderingMixin
from .header_single import SingleHeaderGenerationMixin
from .header_type_planning import HeaderTypePlanningMixin

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class HeaderGenerator(
    SingleHeaderGenerationMixin,
    HierarchyHeaderGenerationMixin,
    HeaderTypePlanningMixin,
    HeaderOrderingMixin,
    HeaderForwardDeclarationMixin,
    HeaderMemberRenderingMixin,
    HeaderAggregateRenderingMixin,
    HeaderMethodRenderingMixin,
    HeaderGeneratorContext,
):
    """Generates C++ headers from ClassInfo objects.

    This class handles:
    - C++ header formatting with include guards
    - Forward declarations (using offset-based validation)
    - Class definitions with proper inheritance
    - Member and method declarations with correct array syntax
    - Enum, struct, and union definitions
    - Metadata comments
    """

    def __init__(
        self, dwarf_index: DwarfIndexPort, class_parser: ClassParserPort | None = None
    ) -> None:
        """Initialize header generator with DWARF index.

        Args:
            dwarf_index: DWARF index for offset-based type validation
            class_parser: Optional class parser for tracking timed-out symbols
        """
        self.dwarf_index = dwarf_index
        self.class_parser = class_parser
