"""Follow-up implementation and assembly discovery after header generation."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import TypeGuard, cast

from ...core.dwarf import DwarfCompilationUnit, DwarfEntry, dwarf_reference_offset
from ...core.observability import get_logger, log_event
from ...domain.models.analytical_dwarf import QueryResult, QueryStatus
from ...domain.models.disassembly import (
    OrbisDisassemblyReport,
    OrbisRelocationEntry,
)
from ...domain.models.disassembly_scope import DisassemblyRequest
from ...domain.models.dwarf import ClassInfo, MethodInfo
from ...domain.models.implementation_evidence import (
    ImplementationDiscoveryReport,
    ImplementationRelation,
    ImplementationStatus,
    MethodAssemblyEvidence,
    MethodImplementationCandidate,
)
from ...domain.ports.disassembly import DisassemblyProducerPort
from ...domain.services.generation.method_definition_rendering import (
    MethodDefinitionRenderingService,
)
from ..generation.runtime import GenerationRuntime
from .dwarf_header_generation import HeaderGenerationService
from .dwarf_implementation_association import attach_disassembly as _attach_disassembly
from .dwarf_implementation_association import (
    build_disassembly_request as _build_disassembly_request,
)
from .dwarf_implementation_association import source_sha256 as _source_sha256
from .dwarf_implementation_context import attach_analytical_context
from .dwarf_implementation_ranges import code_ranges_for_die as _code_ranges
from .dwarf_implementation_reporting import implementation_report as _implementation_report
from .generation_contracts import HeaderBundle, SymbolExtractionResult

logger = get_logger(__name__)


class ImplementationDiscoveryService:
    """Rediscover method bodies without changing the canonical header path."""

    @staticmethod
    def discover(
        context: GenerationRuntime,
        root_symbol: str,
        header_bundle: HeaderBundle,
        *,
        orbis_objdump_path: Path | None = None,
    ) -> ImplementationDiscoveryReport:
        """Build an additive implementation report for one completed header bundle."""
        try:
            class_infos = ImplementationDiscoveryService._discover_classes(context, root_symbol)
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            logger.warning("Implementation rediscovery failed for %s", root_symbol, exc_info=error)
            return _unavailable_report(root_symbol, header_bundle, error)

        seeds = _discover_methods(context, class_infos)
        request = _build_disassembly_request(context, root_symbol, seeds)
        disassembly, disassembly_error = ImplementationDiscoveryService._load_disassembly(
            context,
            request,
            orbis_objdump_path,
        )
        methods = tuple(
            _attach_relocation_ids(
                _attach_disassembly(seed, disassembly, disassembly_error),
                disassembly,
            )
            for seed in seeds
        )
        methods = attach_analytical_context(context, methods)
        status = _report_status(methods)
        _log_completion(root_symbol, header_bundle, methods, status)
        report = _implementation_report(
            root_symbol,
            header_bundle,
            status,
            methods,
            disassembly,
            disassembly_error,
            disassembly.elf_sha256 if disassembly else _source_sha256(context),
        )
        report = _bind_analytical_identity(report, context)
        return replace(
            report,
            disassembly_scope_hash=request.scope_hash,
            disassembly_scope_policy=request.selection_policy,
            disassembly_target_manifest=request.targets,
        )

    @staticmethod
    def discover_symbols(
        context: GenerationRuntime,
        roots: tuple[str, ...],
        symbols: SymbolExtractionResult,
        *,
        orbis_objdump_path: Path | None = None,
    ) -> ImplementationDiscoveryReport:
        """Discover one deduplicated method union for a symbol request."""
        del roots
        header_bundle = symbols.header_bundle
        root_symbol = "symbols"
        try:
            seeds = _discover_methods(context, symbols.class_infos)
            request = _build_disassembly_request(context, root_symbol, seeds)
            disassembly, disassembly_error = ImplementationDiscoveryService._load_disassembly(
                context,
                request,
                orbis_objdump_path,
            )
            methods = tuple(
                _attach_relocation_ids(
                    _attach_disassembly(seed, disassembly, disassembly_error),
                    disassembly,
                )
                for seed in seeds
            )
            methods = attach_analytical_context(context, methods)
            report = _implementation_report(
                root_symbol,
                header_bundle,
                _report_status(methods),
                methods,
                disassembly,
                disassembly_error,
                disassembly.elf_sha256 if disassembly else _source_sha256(context),
            )
            report = _bind_analytical_identity(report, context)
            return replace(
                report,
                disassembly_scope_hash=request.scope_hash,
                disassembly_scope_policy=request.selection_policy,
                disassembly_target_manifest=request.targets,
            )
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            logger.warning("Symbol implementation discovery failed", exc_info=error)
            return _unavailable_report(root_symbol, header_bundle, error)

    @staticmethod
    def _discover_classes(context: GenerationRuntime, root_symbol: str) -> Mapping[str, ClassInfo]:
        # Follow the exact structural closure that was published in the header.
        # Expanding method-signature dependencies here would discover methods from
        # helper classes that are not part of the generated header contract.
        cached = context.header_hierarchies.get((root_symbol, 10, False))
        if cached:
            log_event(
                logger,
                logging.DEBUG,
                "implementation_hierarchy_reused",
                symbol=root_symbol,
                class_count=len(cached),
            )
            return cached
        HeaderGenerationService._expand_typedef_search(context, full_hierarchy=True)
        class_infos, _ = HeaderGenerationService._build_hierarchy_with_timing(
            context,
            root_symbol,
            max_depth=10,
            include_method_signatures=False,
        )
        return class_infos

    @staticmethod
    def _iter_methods(
        class_infos: Mapping[str, ClassInfo],
    ) -> Iterable[tuple[ClassInfo, MethodInfo]]:
        seen: set[tuple[int | None, int | None, str]] = set()
        for class_name in sorted(class_infos):
            class_info = class_infos[class_name]
            for info in _walk_class_infos(class_info):
                owner = info.qualified_name or info.name
                for method in info.methods:
                    key = (info.cu_offset, method.die_offset, owner)
                    if method.die_offset is not None and key in seen:
                        continue
                    if method.die_offset is not None:
                        seen.add(key)
                    yield info, method

    @staticmethod
    def _load_disassembly(
        context: GenerationRuntime,
        request: DisassemblyRequest,
        orbis_objdump_path: Path | None,
    ) -> tuple[OrbisDisassemblyReport | None, str | None]:
        if orbis_objdump_path is None:
            return None, "Orbis disassembly was not requested"
        factory = context.disassembly_factory
        if factory is None:
            return None, "Orbis disassembly producer is unavailable"
        try:
            producer: DisassemblyProducerPort = factory(orbis_objdump_path)
            return producer.produce(context.elf_path, request), None
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            logger.warning(
                "Orbis disassembly unavailable for %s", request.root_symbol, exc_info=error
            )
            return None, f"Orbis disassembly unavailable: {error}"

    @staticmethod
    def _discover_method(
        context: GenerationRuntime,
        class_info: ClassInfo,
        method: MethodInfo,
    ) -> MethodAssemblyEvidence:
        owner = class_info.qualified_name or class_info.name
        owner_class_key = _class_identity_key(class_info)
        signature = _method_signature(method)
        declaration_offset = method.die_offset
        if declaration_offset is None:
            return _evidence_without_declaration(
                owner, method, signature, owner_class_key=owner_class_key
            )

        query = _method_candidates(context, class_info, method)
        if query.status is QueryStatus.UNAVAILABLE:
            return _evidence_with_status(
                owner,
                method,
                signature,
                ImplementationStatus.UNAVAILABLE,
                ImplementationStatus.UNAVAILABLE,
                diagnostics=query.diagnostics,
                owner_class_key=owner_class_key,
            )
        candidates = _candidate_evidence(context, method, query)
        implementation_status = _implementation_status(query, candidates)
        return _method_evidence(
            class_info,
            method,
            signature,
            declaration_offset,
            implementation_status,
            candidates,
            query.diagnostics,
        )


def _walk_class_infos(class_info: ClassInfo) -> Iterable[ClassInfo]:
    yield class_info
    for nested in sorted(
        class_info.nested_classes, key=lambda item: item.qualified_name or item.name
    ):
        yield from _walk_class_infos(nested)


def _unavailable_report(
    root_symbol: str, header_bundle: HeaderBundle, error: Exception
) -> ImplementationDiscoveryReport:
    return ImplementationDiscoveryReport(
        root_symbol,
        header_bundle.sha256,
        ImplementationStatus.UNAVAILABLE,
        (),
        diagnostics=(f"implementation rediscovery unavailable: {error}",),
    )


def _discover_methods(
    context: GenerationRuntime,
    class_infos: Mapping[str, ClassInfo],
) -> tuple[MethodAssemblyEvidence, ...]:
    return tuple(
        ImplementationDiscoveryService._discover_method(
            context,
            class_info,
            method,
        )
        for class_info, method in ImplementationDiscoveryService._iter_methods(class_infos)
    )


def _log_completion(
    root_symbol: str,
    header_bundle: HeaderBundle,
    methods: tuple[MethodAssemblyEvidence, ...],
    status: ImplementationStatus,
) -> None:
    log_event(
        logger,
        logging.INFO,
        "implementation_discovery_completed",
        symbol=root_symbol,
        method_count=len(methods),
        matched_count=sum(item.assembly_status is ImplementationStatus.MATCHED for item in methods),
        status=status.value,
        header_bundle_sha256=header_bundle.sha256,
    )


def _attach_relocation_ids(
    method: MethodAssemblyEvidence,
    disassembly: OrbisDisassemblyReport | None,
) -> MethodAssemblyEvidence:
    """Keep method links as IDs while the report owns relocation payloads once."""
    if disassembly is None or not disassembly.relocation_entries:
        return method
    ids = set(method.relocation_ids)
    ids.update(_method_relocation_ids(method, disassembly.relocation_entries))
    ids.update(_instruction_relocation_ids(method))
    return replace(method, relocation_ids=tuple(sorted(ids)))


def _method_relocation_ids(
    method: MethodAssemblyEvidence,
    entries: tuple[OrbisRelocationEntry, ...],
) -> set[str]:
    addresses = {item.address for item in method.instructions}
    return {
        entry.relocation_id
        for entry in entries
        if entry.offset in addresses or _entry_has_instruction_address(entry, addresses)
    }


def _entry_has_instruction_address(entry: OrbisRelocationEntry, addresses: set[int]) -> bool:
    return any(address in addresses for address in entry.instruction_addresses)


def _instruction_relocation_ids(method: MethodAssemblyEvidence) -> set[str]:
    return {
        reference.relocation_id
        for instruction in method.instructions
        for reference in instruction.references
        if reference.relocation_id is not None
    }


def _method_candidates(
    context: GenerationRuntime, class_info: ClassInfo, method: MethodInfo
) -> QueryResult:
    parser = context.class_parser
    if not method.is_declaration:
        direct = _direct_method_pair(context, method)
        return QueryResult(
            QueryStatus.COMPLETE if direct else QueryStatus.NOT_FOUND, (direct,) if direct else ()
        )
    if method.die_offset is None:
        return QueryResult(QueryStatus.UNAVAILABLE, diagnostics=("method has no DIE offset",))
    return parser.find_method_implementation_candidates_indexed(method.die_offset, method.name)


def _candidate_evidence(
    context: GenerationRuntime,
    method: MethodInfo,
    query: QueryResult,
) -> tuple[MethodImplementationCandidate, ...]:
    candidates = (_make_candidate(context, method, item) for item in query.items if _is_pair(item))
    return tuple(candidate for candidate in candidates if candidate is not None)


def _implementation_status(
    query: QueryResult,
    candidates: tuple[MethodImplementationCandidate, ...],
) -> ImplementationStatus:
    if query.status is QueryStatus.PARTIAL:
        return ImplementationStatus.PARTIAL
    if not query.items:
        return ImplementationStatus.NOT_OBSERVED
    if not candidates:
        return ImplementationStatus.PARTIAL
    if len(candidates) > 1:
        return ImplementationStatus.AMBIGUOUS
    if not candidates[0].code_ranges:
        return (
            ImplementationStatus.PARTIAL
            if _incomplete_range_evidence(candidates[0].diagnostics)
            else ImplementationStatus.UNSUPPORTED
        )
    if any(candidate.diagnostics for candidate in candidates):
        return ImplementationStatus.PARTIAL
    return ImplementationStatus.MATCHED


def _method_evidence(
    class_info: ClassInfo,
    method: MethodInfo,
    signature: str,
    declaration_offset: int,
    implementation_status: ImplementationStatus,
    candidates: tuple[MethodImplementationCandidate, ...],
    query_diagnostics: tuple[str, ...],
) -> MethodAssemblyEvidence:
    diagnostics = tuple(item for candidate in candidates for item in candidate.diagnostics)
    diagnostics += query_diagnostics
    owner = class_info.qualified_name or class_info.name
    selected = candidates[0] if len(candidates) == 1 else None
    return MethodAssemblyEvidence(
        owner=owner,
        method_name=method.name,
        signature=signature,
        declaration_die_offset=declaration_offset,
        declaration_cu_offset=method.cu_offset,
        implementation_status=implementation_status,
        assembly_status=ImplementationStatus.NOT_OBSERVED,
        candidates=candidates,
        selected_implementation_die_offset=(
            selected.implementation_die_offset if selected else None
        ),
        diagnostics=diagnostics,
        definition_signature=MethodDefinitionRenderingService.render(owner, method),
        is_deleted=method.is_deleted,
        is_defaulted=method.is_defaulted,
        is_pure_virtual=method.is_pure_virtual,
        owner_class_key=_class_identity_key(class_info),
    )


def _direct_method_pair(
    context: GenerationRuntime, method: MethodInfo
) -> tuple[DwarfCompilationUnit, DwarfEntry] | None:
    if method.die_offset is None:
        return None
    lookup = context.dwarf_info.get_DIE_from_refaddr
    die = cast(DwarfEntry | None, lookup(method.die_offset))
    cu = cast(DwarfCompilationUnit | None, die.cu) if die is not None else None
    return (
        (cu, die)
        if die is not None and die.offset == method.die_offset and cu is not None
        else None
    )


def _class_identity_key(class_info: ClassInfo) -> str:
    """Match implementation evidence to the canonical symbol graph key."""
    return "|".join(
        (
            class_info.qualified_name or class_info.name,
            "none" if class_info.cu_offset is None else str(class_info.cu_offset),
            "none" if class_info.die_offset is None else str(class_info.die_offset),
        )
    )


def _is_pair(value: object) -> TypeGuard[tuple[DwarfCompilationUnit, DwarfEntry]]:
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(getattr(value[0], "cu_offset", None), int)
        and isinstance(getattr(value[1], "offset", None), int)
        and getattr(value[1], "tag", None) is not None
    )


def _make_candidate(
    context: GenerationRuntime,
    method: MethodInfo,
    item: object,
) -> MethodImplementationCandidate | None:
    if not _is_pair(item):
        return None
    cu, die = item
    implementation_offset = die.offset
    if not isinstance(implementation_offset, int) or method.die_offset is None:
        return None
    relation = _implementation_relation(die, method.die_offset)
    ranges, range_diagnostics = _code_ranges(context, cu, die)
    return MethodImplementationCandidate(
        declaration_die_offset=method.die_offset,
        implementation_die_offset=implementation_offset,
        declaration_cu_offset=method.cu_offset,
        implementation_cu_offset=cu.cu_offset,
        relation=relation,
        name=_attribute_text(die, "DW_AT_name"),
        linkage_name=_attribute_text(die, "DW_AT_linkage_name")
        or _attribute_text(die, "DW_AT_MIPS_linkage_name"),
        code_ranges=ranges,
        is_inline=_attribute_bool(die, "DW_AT_inline"),
        diagnostics=range_diagnostics,
    )


def _implementation_relation(die: DwarfEntry, declaration_offset: int) -> ImplementationRelation:
    for attribute_name, relation in (
        ("DW_AT_specification", ImplementationRelation.SPECIFICATION),
        ("DW_AT_abstract_origin", ImplementationRelation.ABSTRACT_ORIGIN),
    ):
        attribute = die.attributes.get(attribute_name)
        if attribute is None:
            continue
        resolved = dwarf_reference_offset(die, attribute_name)
        raw = attribute.value
        if resolved == declaration_offset or raw == declaration_offset:
            return relation
    return ImplementationRelation.DIRECT


def _incomplete_range_evidence(diagnostics: Iterable[str]) -> bool:
    markers = ("unknown", "unavailable", "partial", "not_found", "timed_out")
    return any(marker in diagnostic.lower() for diagnostic in diagnostics for marker in markers)


def _attribute_text(die: DwarfEntry, name: str) -> str | None:
    attribute = die.attributes.get(name)
    if attribute is None:
        return None
    value = attribute.value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value) if value is not None else None


def _attribute_bool(die: DwarfEntry, name: str) -> bool | None:
    attribute = die.attributes.get(name)
    if attribute is None:
        return None
    value = attribute.value
    return bool(value) if isinstance(value, (bool, int)) else None


def _method_signature(method: MethodInfo) -> str:
    return MethodDefinitionRenderingService.render_signature(method)


def _evidence_without_declaration(
    owner: str,
    method: MethodInfo,
    signature: str,
    *,
    owner_class_key: str | None = None,
) -> MethodAssemblyEvidence:
    return MethodAssemblyEvidence(
        owner,
        method.name,
        signature,
        None,
        method.cu_offset,
        ImplementationStatus.UNSUPPORTED,
        ImplementationStatus.UNSUPPORTED,
        diagnostics=("method has no source DIE identity",),
        owner_class_key=owner_class_key,
    )


def _evidence_with_status(
    owner: str,
    method: MethodInfo,
    signature: str,
    implementation_status: ImplementationStatus,
    assembly_status: ImplementationStatus,
    *,
    diagnostics: Iterable[str] = (),
    owner_class_key: str | None = None,
) -> MethodAssemblyEvidence:
    return MethodAssemblyEvidence(
        owner,
        method.name,
        signature,
        method.die_offset,
        method.cu_offset,
        implementation_status,
        assembly_status,
        diagnostics=tuple(diagnostics),
        owner_class_key=owner_class_key,
    )


def _report_status(methods: tuple[MethodAssemblyEvidence, ...]) -> ImplementationStatus:
    if not methods or all(
        item.assembly_status is ImplementationStatus.NOT_OBSERVED for item in methods
    ):
        return ImplementationStatus.NOT_OBSERVED
    if all(item.assembly_status is ImplementationStatus.MATCHED for item in methods):
        return ImplementationStatus.MATCHED
    return ImplementationStatus.PARTIAL


def _bind_analytical_identity(
    report: ImplementationDiscoveryReport, context: GenerationRuntime
) -> ImplementationDiscoveryReport:
    """Record the Doris query boundary without opening producer files."""
    query_port = context.class_parser.query_port
    if query_port is None:
        return report
    manifest = getattr(query_port, "manifest", None)
    return replace(
        report,
        analytical_backend="doris",
        analytical_store_manifest_sha256=getattr(query_port, "manifest_sha256", None),
        analytical_store_schema_version=getattr(manifest, "schema_version", None),
    )
