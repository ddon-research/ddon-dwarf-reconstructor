"""Focused operations extracted from the public class-parser façade."""

from __future__ import annotations

import re
import time

from ....core.dwarf import DwarfEntry, decode_dwarf_string
from ....core.observability import get_logger
from ...models.dwarf import (
    MethodInfo,
    ParameterInfo,
)
from .class_parser_context import ClassParserContext
from .method_evidence import merge_parameter_names
from .type_chain_traverser import TypeChainTraverser

logger = get_logger(__name__)


class ClassParserMethodsMixin:
    def parse_method(self: ClassParserContext, method_die: DwarfEntry) -> MethodInfo | None:
        """Parse a class method using pyelftools."""
        name_attr = method_die.attributes.get("DW_AT_name")
        if name_attr is None:
            return None
        method_name = decode_dwarf_string(name_attr.value)
        return_type = self.type_resolver.resolve_type_name(method_die)
        return_type_offset = TypeChainTraverser.get_terminal_type_offset(method_die)
        is_virtual, vtable_index = self._virtual_method_info(method_die)
        parent_name = self._parent_name(method_die)
        parameters = self._parse_method_parameters(method_die)
        is_declaration = method_die.attributes.get("DW_AT_declaration") is not None
        if self.resolve_param_names and is_declaration and parameters:
            self._resolve_parameter_names_from_implementation(method_die, method_name, parameters)
        return MethodInfo(
            name=method_name,
            return_type=return_type,
            return_type_offset=return_type_offset,
            parameters=parameters,
            is_virtual=is_virtual,
            vtable_index=vtable_index,
            is_constructor=method_name == parent_name,
            is_destructor=method_name.startswith("~"),
            access=self._get_accessibility(method_die),
            is_static="DW_AT_static" in method_die.attributes,
            is_const="DW_AT_const" in method_die.attributes,
            is_volatile="DW_AT_volatile" in method_die.attributes,
            ref_qualifier=(
                "&&"
                if "DW_AT_rvalue_reference" in method_die.attributes
                else "&"
                if "DW_AT_reference" in method_die.attributes
                else None
            ),
            is_noexcept=self._has_noexcept_evidence(method_die),
            is_noreturn="DW_AT_noreturn" in method_die.attributes,
            is_pure_virtual="DW_AT_pure" in method_die.attributes,
            is_deleted="DW_AT_deleted" in method_die.attributes,
            is_defaulted="DW_AT_defaulted" in method_die.attributes,
            is_declaration=is_declaration,
        )

    def _virtual_method_info(
        self: ClassParserContext, method_die: DwarfEntry
    ) -> tuple[bool, int | None]:
        virtuality_attr = method_die.attributes.get("DW_AT_virtuality")
        is_virtual = virtuality_attr is not None and bool(getattr(virtuality_attr, "value", True))
        if not is_virtual:
            return False, None
        vtable_attr = method_die.attributes.get("DW_AT_vtable_elem_location")
        return True, self._parse_vtable_index(vtable_attr) if vtable_attr is not None else None

    @staticmethod
    def _parent_name(method_die: DwarfEntry) -> str:
        parent_die = method_die.get_parent()
        if parent_die is None or "DW_AT_name" not in parent_die.attributes:
            return ""
        value = parent_die.attributes["DW_AT_name"].value
        return decode_dwarf_string(value)

    @staticmethod
    def _has_noexcept_evidence(method_die: DwarfEntry) -> bool:
        return any(
            attribute in method_die.attributes
            for attribute in ("DW_AT_noexcept", "DW_AT_GNU_nothrow", "DW_AT_GNU_noexcept")
        )

    def _parse_method_parameters(
        self: ClassParserContext, method_die: DwarfEntry
    ) -> list[ParameterInfo]:
        parameters: list[ParameterInfo] = []
        param_index = 0
        for child in method_die.iter_children():
            if child.tag != "DW_TAG_formal_parameter":
                continue
            is_artificial = child.attributes.get("DW_AT_artificial") is not None
            parameter = self.parse_parameter(child, param_index if not is_artificial else 0)
            if parameter is not None:
                parameters.append(parameter)
            if not is_artificial:
                param_index += 1
        return parameters

    @staticmethod
    def _parse_vtable_index(attribute: object) -> int | None:
        """Decode a simple ``DW_OP_constu`` vtable location expression."""
        value: object = getattr(attribute, "value", attribute)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            match = re.search(r"DW_OP_constu\s+(0[xX][0-9a-fA-F]+|[0-9]+)", value)
            if match is None:
                return None
            token = match.group(1)
            return int(token, 16) if token.lower().startswith("0x") else int(token)
        raw = ClassParserMethodsMixin._vtable_raw_bytes(value)
        if raw is None or not raw or raw[0] != 0x10:
            return None
        return ClassParserMethodsMixin._decode_vtable_uleb128(raw[1:])

    @staticmethod
    def _vtable_raw_bytes(value: object) -> list[int] | None:
        if isinstance(value, (bytes, bytearray)):
            return list(value)
        if isinstance(value, (list, tuple)) and all(isinstance(item, int) for item in value):
            return list(value)
        return None

    @staticmethod
    def _decode_vtable_uleb128(raw: list[int]) -> int | None:
        result = 0
        shift = 0
        for byte in raw:
            result |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return result
            shift += 7
        return None

    def parse_parameter(
        self: ClassParserContext, param_die: DwarfEntry, param_index: int = 0
    ) -> ParameterInfo | None:
        """Parse a function parameter using pyelftools.

        Args:
            param_die: DwarfEntry representing the parameter
            param_index: Zero-based parameter position for auto-incrementing unnamed params

        Returns:
            ParameterInfo object
        """
        # Check if artificial (like 'this' pointer)
        is_artificial = param_die.attributes.get("DW_AT_artificial") is not None

        # Get parameter name with auto-incrementing fallback
        name_attr = param_die.attributes.get("DW_AT_name")
        # Auto-increment unnamed parameters to avoid C++ syntax errors
        # (param1, param2, param3, ...) instead of all being "param"
        param_name = (
            decode_dwarf_string(name_attr.value)
            if name_attr is not None
            else f"param{param_index + 1}"
        )

        # Get parameter type (for display)
        param_type = self.type_resolver.resolve_type_name(param_die)

        # Capture terminal type offset for dependency resolution
        type_offset = TypeChainTraverser.get_terminal_type_offset(param_die)
        if type_offset is not None:
            logger.debug(
                f"Captured type offset 0x{type_offset:x} for parameter '{param_name}': "
                f"'{param_type}'"
            )

        # Get default value if present
        default_value = None
        const_attr = param_die.attributes.get("DW_AT_default_value")
        if const_attr is not None:
            default_value = str(const_attr.value)

        # Mark artificial parameters for filtering
        if is_artificial:
            param_name = "__artificial__"

        return ParameterInfo(
            name=param_name,
            type_name=param_type,
            type_offset=type_offset,  # Store terminal type offset
            default_value=default_value,
        )

    def _resolve_parameter_names_from_implementation(
        self: ClassParserContext,
        method_die: DwarfEntry,
        method_name: str,
        parameters: list[ParameterInfo],
    ) -> None:
        """Search for method implementation and extract parameter names.

        Searches DWARF for a DW_TAG_subprogram with DW_AT_specification pointing
        to this method declaration. If found, extracts parameter names from the
        implementation's formal_parameter DIEs and updates the declaration's parameters.

        Args:
            method_die: Method declaration DIE
            method_name: Name of the method for logging
            parameters: List of ParameterInfo objects to update (modified in place)
        """
        start_time = time.time()
        decl_offset = method_die.offset

        # Check cache first
        if decl_offset in self._implementation_cache:
            cached_result = self._implementation_cache[decl_offset]
            if cached_result is None:
                logger.debug(f"Cache hit: No implementation found for {method_name}")
                return
            _cu, impl_die = cached_result
            merge_parameter_names(impl_die, parameters, method_name)
            elapsed = time.time() - start_time
            logger.debug(f"Cache hit: Found implementation for {method_name} in {elapsed:.3f}s")
            return

        # Search for implementation
        impl_result = self._find_method_implementation(decl_offset, method_name)

        # Cache the result (even if None)
        self._implementation_cache[decl_offset] = impl_result

        if impl_result is None:
            elapsed = time.time() - start_time
            logger.debug(f"No implementation found for {method_name} (searched {elapsed:.3f}s)")
            return

        _cu, impl_die = impl_result
        merge_parameter_names(impl_die, parameters, method_name)
        elapsed = time.time() - start_time
        logger.info(
            f"Resolved parameter names for {method_name} from implementation "
            f"(found in {elapsed:.3f}s)"
        )
