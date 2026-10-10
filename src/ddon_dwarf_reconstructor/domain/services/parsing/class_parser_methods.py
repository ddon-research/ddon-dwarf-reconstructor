"""Focused operations extracted from the public class-parser façade."""

from __future__ import annotations

import re
import time

from ....core.dwarf import DwarfEntry, decode_dwarf_string
from ....core.observability import get_logger
from ...models.dwarf import (
    MethodInfo,
    ParameterInfo,
    TemplateTypeParam,
    TemplateValueParam,
)
from .class_parser_context import ClassParserContext
from .method_evidence import merge_parameter_names
from .type_scope import die_key, flag

logger = get_logger(__name__)


class ClassParserMethodsMixin:
    def parse_method(self: ClassParserContext, method_die: DwarfEntry) -> MethodInfo | None:
        """Parse a class method using pyelftools."""
        name_attr = method_die.attributes.get("DW_AT_name")
        if name_attr is None:
            return None
        method_name = decode_dwarf_string(name_attr.value)
        return_type = self.type_resolver.resolve_type_name(method_die)
        return_type_offset = self.type_chain_traverser.get_terminal_type_offset(method_die)
        declared_return_type_offset = self.type_chain_traverser.get_declared_type_offset(method_die)
        is_virtual, vtable_index = self._virtual_method_info(method_die)
        parent_name = self._parent_name(method_die)
        parent_die = method_die.get_parent()
        cu = getattr(method_die, "cu", None)
        parameters, template_parameters = self._parse_method_children(method_die)
        implicit_const, implicit_volatile, implicit_ref = self._implicit_object_qualifiers(
            parameters
        )
        is_declaration = flag(method_die, "DW_AT_declaration")
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
            is_static=flag(method_die, "DW_AT_static"),
            is_const=flag(method_die, "DW_AT_const") or implicit_const,
            is_volatile=flag(method_die, "DW_AT_volatile") or implicit_volatile,
            ref_qualifier=(
                "&&"
                if flag(method_die, "DW_AT_rvalue_reference")
                else "&"
                if flag(method_die, "DW_AT_reference")
                else implicit_ref
            ),
            is_noexcept=self._has_noexcept_evidence(method_die),
            is_noreturn=flag(method_die, "DW_AT_noreturn"),
            is_pure_virtual=flag(method_die, "DW_AT_pure"),
            is_deleted=flag(method_die, "DW_AT_deleted"),
            is_defaulted=flag(method_die, "DW_AT_defaulted"),
            is_declaration=is_declaration,
            declared_return_type_offset=declared_return_type_offset,
            die_offset=method_die.offset,
            cu_offset=getattr(cu, "cu_offset", None),
            owner_die_offset=getattr(parent_die, "offset", None),
            linkage_name=self._linkage_name(method_die),
            return_type_reference=self.type_resolver.resolve_reference(method_die),
            template_parameters=template_parameters,
        )

    @staticmethod
    def _linkage_name(method_die: DwarfEntry) -> str | None:
        for attribute_name in ("DW_AT_linkage_name", "DW_AT_MIPS_linkage_name"):
            attribute = method_die.attributes.get(attribute_name)
            if attribute is not None:
                return decode_dwarf_string(attribute.value)
        return None

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
            flag(method_die, attribute)
            for attribute in ("DW_AT_noexcept", "DW_AT_GNU_nothrow", "DW_AT_GNU_noexcept")
        )

    def _parse_method_children(
        self: ClassParserContext, method_die: DwarfEntry
    ) -> tuple[list[ParameterInfo], tuple[TemplateTypeParam | TemplateValueParam, ...]]:
        parameters: list[ParameterInfo] = []
        template_parameters: list[TemplateTypeParam | TemplateValueParam] = []
        param_index = 0
        object_parameter = self._object_parameter_die(method_die)
        for child in method_die.iter_children():
            if child.tag in {"DW_TAG_template_type_param", "DW_TAG_template_value_param"}:
                parameter = self._parse_method_template_child(child)
                if parameter is not None:
                    template_parameters.append(parameter)
                continue
            if child.tag != "DW_TAG_formal_parameter":
                continue
            is_artificial = self._is_implicit_object_parameter(child, object_parameter)
            parameter = self.parse_parameter(child, param_index if not is_artificial else 0)
            if parameter is not None:
                if is_artificial and not parameter.is_artificial:
                    parameter.is_artificial = True
                    parameter.name = "__artificial__"
                parameters.append(parameter)
            if not is_artificial:
                param_index += 1
        return parameters, tuple(template_parameters)

    def _parse_method_template_child(
        self: ClassParserContext, child: DwarfEntry
    ) -> TemplateTypeParam | TemplateValueParam | None:
        if child.tag == "DW_TAG_template_type_param":
            return self.parse_template_type_param(child)
        return self.parse_template_value_param(child)

    @staticmethod
    def _object_parameter_die(method_die: DwarfEntry) -> DwarfEntry | None:
        """Resolve DWARF's explicit object-pointer reference when available."""
        attributes = getattr(method_die, "attributes", {})
        if "DW_AT_object_pointer" not in attributes:
            return None
        try:
            return method_die.get_DIE_from_attribute("DW_AT_object_pointer")
        except AttributeError, KeyError, RuntimeError, TypeError, ValueError:
            return None

    @staticmethod
    def _is_implicit_object_parameter(
        parameter_die: DwarfEntry, object_parameter: DwarfEntry | None
    ) -> bool:
        if flag(parameter_die, "DW_AT_artificial"):
            return True
        if object_parameter is None:
            return False
        return parameter_die is object_parameter or (
            die_key(object_parameter)[1] is not None
            and die_key(parameter_die) == die_key(object_parameter)
        )

    @staticmethod
    def _implicit_object_qualifiers(
        parameters: list[ParameterInfo],
    ) -> tuple[bool, bool, str | None]:
        """Recover cv/ref qualifiers encoded only on DWARF's artificial ``this``.

        Some producers omit ``DW_AT_const``/reference attributes on a method
        declaration and instead qualify the artificial object parameter.  It
        must remain in the evidence list for provenance, but it is never a
        source-level parameter (``real_parameters`` filters it during render).
        """
        implicit = next((parameter for parameter in parameters if parameter.is_artificial), None)
        if implicit is None:
            return False, False, None
        type_name = " ".join(implicit.type_name.strip().split())
        # Qualifiers attached to the pointed-to object describe the implicit
        # object parameter.  A top-level ``T* const`` qualifier belongs to the
        # parameter itself and must not turn the member function into a const
        # member.  Restrict cv detection to the type prefix before indirection.
        object_prefix = re.split(r"[*&]", type_name, maxsplit=1)[0]
        is_const = bool(re.search(r"\bconst\b", object_prefix))
        is_volatile = bool(re.search(r"\bvolatile\b", object_prefix))
        ref_qualifier: str | None = None
        if re.search(r"&&\s*$", type_name):
            ref_qualifier = "&&"
        elif re.search(r"[^*]&\s*$", type_name):
            ref_qualifier = "&"
        return is_const, is_volatile, ref_qualifier

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
        is_artificial = flag(param_die, "DW_AT_artificial")

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
        type_offset = self.type_chain_traverser.get_terminal_type_offset(param_die)
        declared_type_offset = self.type_chain_traverser.get_declared_type_offset(param_die)
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
            declared_type_offset=declared_type_offset,
            die_offset=param_die.offset,
            cu_offset=getattr(getattr(param_die, "cu", None), "cu_offset", None),
            is_artificial=is_artificial,
            type_reference=self.type_resolver.resolve_reference(param_die),
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
